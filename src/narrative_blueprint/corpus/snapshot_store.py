"""Indexed SQLite snapshot staging with bounded cache and disk admission."""

import csv
import json
from pathlib import Path
import shutil
import sqlite3

from .contracts import SnapshotRefused, digest, encoded


class SnapshotStore:
    def __init__(self, directory, limits):
        self.directory, self.limits = Path(directory), limits
        self.path = self.directory / "corpus.sqlite"
        self.db = sqlite3.connect(self.path)
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute(f"PRAGMA cache_size=-{max(1, limits.max_batch_bytes // 4096)}")
        # Reserve half for rollback journal and other outputs. SQLite enforces
        # page admission even if a write expands more than the record estimate.
        pages = max(1, limits.max_disk_bytes // 8192)
        self.db.execute(f"PRAGMA max_page_count={pages}")
        try:
            self.db.executescript('''
                CREATE TABLE records (
                    ordinal INTEGER PRIMARY KEY, occurrence_id TEXT UNIQUE NOT NULL,
                    source_uuid TEXT, text TEXT, text_hash TEXT,
                    status TEXT NOT NULL, reason TEXT, vector_index INTEGER,
                    vector BLOB, vector_hash TEXT, recipe TEXT,
                    generation_state TEXT, response_hash TEXT,
                    source_ordinal INTEGER, attempts INTEGER NOT NULL DEFAULT 0
                );
                CREATE INDEX records_uuid ON records(source_uuid);
                CREATE INDEX records_text_hash ON records(text_hash);
                CREATE INDEX records_status_text ON records(status,text_hash);
                CREATE UNIQUE INDEX records_vector_index ON records(vector_index);
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')
            self.db.commit()
            self.check_disk()
        except BaseException:
            self.db.close()
            raise

    def check_disk(self, extra=0):
        used = sum(item.stat().st_size for item in self.directory.iterdir() if item.is_file())
        self.limits.check("max_disk_bytes", used + extra)
        if shutil.disk_usage(self.directory).free < extra + self.limits.max_record_bytes * 2:
            raise SnapshotRefused("disk_free", "insufficient free space for next record and journal")

    def commit(self):
        self.check_disk()
        self.db.commit()
        self.check_disk()

    def counts(self):
        counts = dict(self.db.execute("SELECT status,count(*) FROM records GROUP BY status"))
        return {
            "selected": sum(counts.values()),
            "available": sum(counts.values()) - counts.get("missing", 0),
            "valid": counts.get("valid", 0), "missing": counts.get("missing", 0),
            "rejected": counts.get("rejected", 0),
            "unique_texts": self.db.execute("SELECT count(DISTINCT text_hash) FROM records WHERE text_hash IS NOT NULL").fetchone()[0],
            "valid_unique_texts": self.db.execute("SELECT count(DISTINCT text_hash) FROM records WHERE status='valid'").fetchone()[0],
        }

    def finalize_ids(self, fingerprint, managed):
        if not managed:
            for ordinal, uuid in self.db.execute("SELECT ordinal,source_uuid FROM records ORDER BY ordinal"):
                occurrence = digest(encoded(["snapshot-occurrence-1", fingerprint, ordinal, uuid]))
                self.db.execute("UPDATE records SET occurrence_id=? WHERE ordinal=?", (occurrence, ordinal))
        self.commit()

    def export_rejections(self):
        with (self.directory / "rejections.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(("occurrence_id", "source_ordinal", "stage", "reason"))
            for occurrence, ordinal, reason in self.db.execute(
                "SELECT occurrence_id,source_ordinal,reason FROM records WHERE status!='valid' ORDER BY ordinal"
            ):
                self.check_disk(extra=1024)
                writer.writerow((occurrence, ordinal, "validation", reason))

    def close(self):
        self.db.close()


def import_ledger(store, path, allow_partial):
    """Copy expectations into indexed staging; never materialize the input ledger."""
    path = Path(path)
    store.limits.check("max_source_bytes", path.stat().st_size)
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        db.execute("BEGIN")
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, store.limits.max_record_bytes)
        meta = dict(db.execute("SELECT key,value FROM metadata WHERE key IN ('schema','status','generation_id','recipe')"))
        if meta.get("schema") != "generation-ledger-1":
            raise SnapshotRefused("ledger_schema")
        coverage = "complete" if meta.get("status") == "complete" else "partial"
        if coverage != "complete" and not allow_partial:
            raise SnapshotRefused("incomplete_generation", "use --allow-partial only to accept recorded exclusions")
        count = 0
        for ordinal, occurrence, uuid, text_hash, state, response_hash in db.execute(
            "SELECT ordinal,occurrence_id,source_uuid,text_hash,state,response_hash FROM outcomes ORDER BY ordinal"
        ):
            count += 1
            store.limits.check("max_records", count)
            store.limits.check("max_record_bytes", len(encoded([occurrence, uuid, text_hash, state, response_hash])))
            if state not in {"pending", "received", "stored_pending_finalize", "stored", "provider_failed", "storage_failed", "not_attempted", "interrupted"}:
                raise SnapshotRefused("ledger_schema")
            if state != "stored" and coverage == "complete":
                raise SnapshotRefused("ledger_inconsistent")
            store.db.execute('''INSERT INTO records
                (ordinal,occurrence_id,source_uuid,text_hash,status,reason,generation_state,response_hash)
                VALUES (?,?,?,?, 'missing', ?,?,?)''',
                (ordinal, occurrence, uuid, text_hash, "missing_vector" if state == "stored" else state, state, response_hash))
            if count % store.limits.max_batch_records == 0:
                store.commit()
        store.commit()
        return {"coverage": coverage, "generation_id": meta.get("generation_id"),
                "recipe": json.loads(meta["recipe"]), "expected": count}
    except SnapshotRefused:
        raise
    except (sqlite3.DatabaseError, ValueError, KeyError) as exc:
        raise SnapshotRefused("ledger_schema") from exc
    finally:
        db.close()
