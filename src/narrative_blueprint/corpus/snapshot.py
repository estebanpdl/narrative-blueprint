"""Build an auditable snapshot; publish its completion marker only after closure."""

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time

from .contracts import SnapshotLimits, SnapshotRefused, digest, encoded
from .snapshot_store import SnapshotStore, import_ledger
from .sources import LocalSource
from .validation import document_signature, normalized_vector, reported_space


def file_hash(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class Admission:
    def __init__(self, store, ledger):
        self.store, self.ledger = store, ledger
        self.recipe = ledger["recipe"] if ledger else None
        self.dimension = None
        self.managed = True if ledger else None
        self.vector_count = self.duplicate_attempts = 0
        self.unselected_rows = 0
        self.fatal = set()

    def accept(self, row, ordinal):
        db, limits = self.store.db, self.store.limits
        uuid, text = row.get("uuid"), row.get("text")
        identity = row.get("occurrence_id") or None
        if self.ledger and row.get("generation_id") != self.ledger["generation_id"]:
            self.unselected_rows += 1
            return
        if not self.ledger and row.get("generation_id"):
            raise SnapshotRefused("generation_ledger_required", "managed output requires its --generation-ledger")
        if identity is not None and (not isinstance(identity, str) or not identity.strip()):
            raise SnapshotRefused("invalid_occurrence_id")
        managed = identity is not None
        if self.managed is None:
            self.managed = managed
        if managed != self.managed:
            raise SnapshotRefused("mixed_occurrence_identity")
        key = identity or f"row:{ordinal}"
        existing = db.execute("SELECT ordinal,source_uuid,text_hash,vector_hash,status,generation_state,response_hash FROM records WHERE occurrence_id=?", (key,)).fetchone()
        if self.ledger and (existing is None or row.get("generation_id") != self.ledger["generation_id"]):
            raise SnapshotRefused("ledger_selection_mismatch")
        reason = None
        if not isinstance(uuid, str) or not uuid.strip():
            reason = "invalid_uuid"
            uuid = None
        if not isinstance(text, str) or not text.strip():
            reason = reason or "invalid_text"
            text = None
        text_hash = digest(text.encode("utf-8")) if isinstance(text, str) else None
        if not managed and db.execute("SELECT 1 FROM records WHERE source_uuid=? LIMIT 1", (uuid,)).fetchone():
            reason = "ambiguous_uuid"
            self.fatal.add(reason)
        recipe = reported_space(row)
        if self.recipe is None:
            self.recipe = recipe
        if recipe != self.recipe:
            reason = "mixed_space"
            self.fatal.add(reason)
        blob, vector_hash, vector_reason = normalized_vector(row.get("embedding"), limits)
        reason = reason or vector_reason
        if blob is not None:
            dimension = len(blob) // 4
            if self.dimension is None:
                self.dimension = dimension
            if dimension != self.dimension:
                reason = "mixed_dimension"
                self.fatal.add(reason)
        if existing:
            if (uuid, text_hash) != (existing[1], existing[2]):
                raise SnapshotRefused("conflicting_occurrence")
            if existing[4] != "missing":
                if existing[3] != vector_hash or reason:
                    raise SnapshotRefused("conflicting_attempt")
                self.duplicate_attempts += 1
                db.execute("UPDATE records SET attempts=attempts+1 WHERE occurrence_id=?", (key,))
                return
            if self.ledger:
                if existing[5] != "stored":
                    reason = "generation_" + existing[5]
                elif existing[6] != document_signature(row):
                    raise SnapshotRefused("ledger_response_mismatch")
        status = "valid" if reason is None else ("missing" if vector_reason == "missing_vector" else "rejected")
        index = self.vector_count if status == "valid" else None
        if status == "valid":
            self.vector_count += 1
        else:
            blob = None
        self.store.check_disk(extra=len(encoded(row)) * 4 + (len(blob) if blob else 0) + 65536)
        values = (uuid, text, text_hash, status, reason, index, blob, vector_hash,
                  json.dumps(recipe), ordinal, key)
        if existing:
            db.execute('''UPDATE records SET source_uuid=?,text=?,text_hash=?,status=?,reason=?,
                vector_index=?,vector=?,vector_hash=?,recipe=?,source_ordinal=?,attempts=attempts+1
                WHERE occurrence_id=?''', values)
        else:
            db.execute('''INSERT INTO records (source_uuid,text,text_hash,status,reason,vector_index,
                vector,vector_hash,recipe,source_ordinal,occurrence_id,ordinal,attempts)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)''', (*values, ordinal))


def build_snapshot(source, output, *, limits=None, declared_space=None,
                   allow_legacy_source=False, generation_ledger=None, allow_partial=False):
    limits = limits or SnapshotLimits()
    if declared_space is not None and (not isinstance(declared_space, str) or not declared_space.strip()):
        raise SnapshotRefused("invalid_declaration")
    if generation_ledger is None and not allow_legacy_source:
        raise SnapshotRefused("legacy_acknowledgement", "--allow-legacy-source accepts unknown original coverage")
    # Admit schema pages, journal and status publication before creating files.
    limits.check("max_disk_bytes", 65536)
    output = Path(output)
    if output.exists():
        raise SnapshotRefused("output_exists", "choose a new snapshot directory")
    output.mkdir(parents=True)
    start = time.perf_counter()
    store = None
    status = {"schema": "corpus-snapshot-1", "status": "running", "limits": asdict(limits)}
    write_json(output / "status.json", status)
    try:
        store = SnapshotStore(output, limits)
        ledger = import_ledger(store, generation_ledger, allow_partial) if generation_ledger else None
        admission = Admission(store, ledger)
        reader = LocalSource(source, limits)
        with reader.open() as rows:
            for ordinal, row in enumerate(rows, 1):
                admission.accept(row, ordinal)
                if ordinal % limits.max_batch_records == 0:
                    store.commit()
        store.finalize_ids(reader.fingerprint, admission.managed)
        counts = store.counts()
        status.update(counts=counts, available_rows=reader.count,
                      unselected_rows=admission.unselected_rows,
                      duplicate_attempts=admission.duplicate_attempts,
                      rejection_reasons=dict(store.db.execute("SELECT reason,count(*) FROM records WHERE reason IS NOT NULL GROUP BY reason")))
        store.export_rejections()
        if admission.fatal:
            raise SnapshotRefused(sorted(admission.fatal)[0], "selection contains incompatible identities or spaces; inspect rejections.csv")
        coverage = ledger["coverage"] if ledger else "unknown"
        if ledger and (counts["missing"] or counts["rejected"]):
            coverage = "partial"
            if not allow_partial:
                raise SnapshotRefused("incomplete_generation", "missing/rejected selected outcomes; explicit --allow-partial required")
        status.update(
            status="snapshot_complete", source_fingerprint=reader.fingerprint,
            source_format=reader.kind, source_bytes=reader.source_bytes,
            selection="all-source-records" if not ledger else "generation-ledger",
            generation_coverage=coverage, declared_space=declared_space,
            expected_original=ledger["expected"] if ledger else None,
            missing_original=counts["missing"] if ledger else None,
            provenance_verified=False, reported_space=admission.recipe,
            dimension=admission.dimension or 0, vector_dtype="little-endian-float32",
            allow_partial=allow_partial,
            analysis_ready=allow_partial or not (counts["missing"] or counts["rejected"]),
            corrected_analysis_complete=False,
        )
        for key in ("schema", "source_fingerprint", "reported_space", "dimension", "selection"):
            store.db.execute("INSERT INTO metadata VALUES (?,?)", (key, json.dumps(status[key])))
        store.commit()
        store.close()
        store = None
        status["outputs"] = {name: file_hash(output / name) for name in ("corpus.sqlite", "rejections.csv")}
        status["duration_seconds"] = time.perf_counter() - start
        used = sum(p.stat().st_size for p in output.iterdir() if p.is_file())
        limits.check("max_disk_bytes", used + 2 * len(encoded(status)) + 4096)
        write_json(output / "status.json", status)
        # This is the only successful publication marker, never written on refusal.
        write_json(output / "snapshot.json", status)
        return status
    except BaseException as exc:
        if store is not None:
            try:
                status.setdefault("counts", store.counts())
            finally:
                store.close()
        status.update(status="refused" if isinstance(exc, SnapshotRefused) else
                      "interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "failed",
                      reason=getattr(exc, "reason", "storage_failure" if isinstance(exc, (OSError, sqlite3.Error)) else "snapshot_failure"),
                      duration_seconds=time.perf_counter() - start)
        try:
            write_json(output / "status.json", status)
        except OSError:
            pass
        raise
