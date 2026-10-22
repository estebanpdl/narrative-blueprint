"""Read a completed snapshot and stage canonical numeric nodes on disk."""

from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

import numpy as np

from .contracts import AnalysisRefused


def checked_hash(path, budget):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            budget.tick()
            hasher.update(chunk)
    return hasher.hexdigest()


def check_sidecars(path):
    for suffix in ("-wal", "-journal"):
        sidecar = Path(str(path) + suffix)
        if sidecar.exists() and sidecar.stat().st_size:
            raise AnalysisRefused("snapshot_active", "snapshot must be quiescent")


@contextmanager
def open_snapshot(directory, budget):
    directory = Path(directory).resolve()
    marker = directory / "snapshot.json"
    budget.limits.check("max_record_bytes", marker.stat().st_size)
    marker_bytes = marker.read_bytes()
    try:
        manifest = json.loads(marker_bytes)
        if manifest["schema"] != "corpus-snapshot-1" or manifest["status"] != "snapshot_complete":
            raise AnalysisRefused("snapshot_incomplete")
        if not manifest["analysis_ready"]:
            raise AnalysisRefused("snapshot_partial", "rebuild with explicit --allow-partial to accept exclusions")
        if manifest["vector_dtype"] != "little-endian-float32":
            raise AnalysisRefused("snapshot_schema")
        count, dimension = manifest["counts"]["valid"], manifest["dimension"]
        if type(count) is not int or count < 0 or type(dimension) is not int or dimension < 0 or (count and not dimension):
            raise AnalysisRefused("snapshot_schema")
        budget.admit(count, dimension)
        paths = [directory / name for name in ("corpus.sqlite", "rejections.csv")]
        budget.limits.check("max_snapshot_bytes", sum(p.stat().st_size for p in paths))
        check_sidecars(paths[0])
        for path in paths:
            if checked_hash(path, budget) != manifest["outputs"][path.name]:
                raise AnalysisRefused("snapshot_checksum")
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, AnalysisRefused):
            raise
        raise AnalysisRefused("snapshot_schema") from exc
    db = sqlite3.connect(paths[0].as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, budget.limits.max_record_bytes)
        db.execute("PRAGMA cache_size=-2048")
        db.execute("PRAGMA temp_store=FILE")
        actual = dict(db.execute("SELECT status,count(*) FROM records GROUP BY status"))
        if any(actual.get(key, 0) != manifest["counts"][key] for key in ("valid", "missing", "rejected")) or sum(actual.values()) != manifest["counts"]["selected"]:
            raise AnalysisRefused("snapshot_counts")
        yield db, manifest, hashlib.sha256(marker_bytes).hexdigest()
        check_sidecars(paths[0])
        if marker.read_bytes() != marker_bytes:
            raise AnalysisRefused("snapshot_changed")
        for path in paths:
            if checked_hash(path, budget) != manifest["outputs"][path.name]:
                raise AnalysisRefused("snapshot_changed")
    finally:
        db.close()


class Scratch:
    """One bounded SQLite cache plus an ordered vector file, never a memmap."""

    def __init__(self, directory, budget):
        self.directory, self.budget = Path(directory), budget
        budget.limits.check("max_disk_bytes", 65536)
        self.path = self.directory / "graph.sqlite"
        self.vectors = self.directory / "vectors.f32"
        self.db = sqlite3.connect(self.path)
        self.db.execute("PRAGMA cache_size=-2048")
        self.db.execute("PRAGMA temp_store=FILE")
        self.db.execute(f"PRAGMA max_page_count={max(1, budget.limits.max_disk_bytes // 8192)}")
        try:
            self.db.executescript('''
                CREATE TABLE nodes (node INTEGER PRIMARY KEY, occurrence_id TEXT UNIQUE,
                    source_uuid TEXT, text_hash TEXT, text TEXT, source_ordinal INTEGER,
                    community INTEGER, outcome TEXT);
                CREATE TABLE edges (i INTEGER, j INTEGER, weight REAL);
            ''')
        except BaseException:
            self.db.close()
            raise

    def disk(self, extra=0):
        used = sum(p.stat().st_size for p in self.directory.iterdir() if p.is_file())
        self.budget.limits.check("max_disk_bytes", used + extra)
        if shutil.disk_usage(self.directory).free < extra + 65536:
            raise AnalysisRefused("disk_free")
        self.budget.tick()

    def stage_nodes(self, snapshot, manifest):
        n, d = manifest["counts"]["valid"], manifest["dimension"]
        self.disk(n * (4 * d + 512) + 65536)
        count = 0
        with self.vectors.open("xb") as stream:
            rows = snapshot.execute('''SELECT occurrence_id,source_uuid,text_hash,text,
                source_ordinal,vector,status FROM records ORDER BY occurrence_id''')
            for occurrence, uuid, text_hash, text, ordinal, blob, status in rows:
                if status != "valid":
                    continue
                node = count
                self.disk(len(blob) + 8 * sum(len(v.encode("utf-8")) for v in (occurrence, uuid, text_hash, text)) + 16384)
                if len(blob) != d * 4:
                    raise AnalysisRefused("snapshot_vector")
                vector = np.frombuffer(blob, dtype="<f4")
                if not np.isfinite(vector).all() or abs(float(np.linalg.norm(vector.astype(np.float64))) - 1) > 1e-5:
                    raise AnalysisRefused("snapshot_vector")
                stream.write(blob)
                self.db.execute("INSERT INTO nodes VALUES (?,?,?,?,?,?,NULL,NULL)",
                                (node, occurrence, uuid, text_hash, text, ordinal))
                count += 1
                if count % 128 == 0:
                    self.db.commit()
        if count != n:
            raise AnalysisRefused("snapshot_counts")
        self.db.commit()
        self.disk()

    def close(self):
        self.db.close()
