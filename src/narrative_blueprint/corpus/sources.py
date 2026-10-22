"""Projected local readers; all handles belong to the enclosing context."""

from contextlib import contextmanager
import csv
import hashlib
import json
from pathlib import Path
import sqlite3

from .contracts import FIELDS, SnapshotLimits, SnapshotRefused, encoded, project


class LimitedLines:
    """Bound a CSV logical record before csv builds a row, including multiline cells."""

    def __init__(self, stream, limits):
        self.stream, self.limits = stream, limits
        self.record_bytes = self.total_bytes = 0
        self.sha = hashlib.sha256()

    def __iter__(self):
        return self

    def __next__(self):
        raw = self.stream.readline(self.limits.max_record_bytes - self.record_bytes + 1)
        if not raw:
            raise StopIteration
        self.record_bytes += len(raw)
        self.total_bytes += len(raw)
        self.limits.check("max_record_bytes", self.record_bytes)
        self.limits.check("max_source_bytes", self.total_bytes)
        self.sha.update(raw)
        try:
            return raw.decode("utf-8-sig" if self.total_bytes == len(raw) else "utf-8")
        except UnicodeDecodeError as exc:
            raise SnapshotRefused("invalid_utf8") from exc


def csv_rows(path, fields, limits):
    with path.open("rb") as stream:
        lines = LimitedLines(stream, limits)
        previous = csv.field_size_limit()
        csv.field_size_limit(limits.max_record_bytes)
        try:
            reader = csv.reader(lines, strict=True)
            header = next(reader, [])
            if len(header) != len(set(header)) or not {"uuid", "text", "embedding"} <= set(header):
                raise SnapshotRefused("source_schema", "unique uuid, text and embedding columns required")
            positions = {name: header.index(name) for name in (*fields, "metadata") if name in header}
            while True:
                lines.record_bytes = 0
                row = next(reader, None)
                if row is None:
                    break
                if len(row) != len(header):
                    raise SnapshotRefused("source_schema", "CSV column count mismatch")
                yield project({name: row[index] for name, index in positions.items()}, fields)
        except (csv.Error, RecursionError) as exc:
            raise SnapshotRefused("malformed_csv") from exc
        finally:
            csv.field_size_limit(previous)


def sqlite_rows(path, fields, limits):
    wal = path.with_name(path.name + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise SnapshotRefused("sqlite_wal_active", "checkpoint/close or export the source before validation")
    # Immutable mode prevents journal/SHM creation; only quiescent standalone
    # databases are admitted, with source change checks on completion.
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        columns = {r[1]: r for r in connection.execute('PRAGMA table_info("embeddings")')}
        if not {"id", "uuid", "text", "embedding"} <= columns.keys() or not columns["id"][5]:
            raise SnapshotRefused("source_schema", "embeddings requires an id primary key and uuid/text/embedding")
        selected = [field for field in (*fields, "metadata") if field in columns]
        names = ",".join(f'"{field}"' for field in selected)
        size = "+".join(f'coalesce(length(CAST("{field}" AS BLOB)),0)' for field in selected)
        # Inspect scalar lengths before SQLite copies a large TEXT/BLOB into Python.
        largest = connection.execute(f'SELECT max({size}) FROM embeddings').fetchone()[0] or 0
        limits.check("max_record_bytes", largest)
        batch_size = min(limits.max_batch_records, max(1, limits.max_batch_bytes // max(1, 8 * largest)))
        cursor = connection.execute(f'SELECT {names} FROM embeddings ORDER BY id')
        try:
            while batch := cursor.fetchmany(batch_size):
                for row in batch:
                    yield project(dict(zip(selected, row)), fields)
        finally:
            cursor.close()
    except sqlite3.DatabaseError as exc:
        raise SnapshotRefused("sqlite_source", "read-only schema/read failure") from exc
    finally:
        connection.close()


class LocalSource:
    """Single-pass selection of all records in physical/id order."""

    def __init__(self, path, limits=None, fields=FIELDS):
        self.path = Path(path)
        self.limits = limits or SnapshotLimits()
        self.fields = tuple(fields)
        if not set(self.fields) <= set(FIELDS):
            raise SnapshotRefused("projection", "unsupported field")
        self.fingerprint = None
        self.count = 0

    @contextmanager
    def open(self):
        path, limits = self.path, self.limits
        if not path.is_file():
            raise SnapshotRefused("source_missing", "a regular source file is required")
        before = path.stat()
        limits.check("max_source_bytes", before.st_size)
        extension = path.suffix.lower()
        if extension == ".csv":
            iterator = csv_rows(path, self.fields, limits)
        elif extension in (".sqlite", ".sqlite3", ".db"):
            iterator = sqlite_rows(path, self.fields, limits)
        elif extension == ".parquet":
            from .columnar import parquet_rows
            iterator = parquet_rows(path, self.fields, limits)
        else:
            raise SnapshotRefused("source_format", "use CSV, Parquet or SQLite")
        self.kind = extension.lstrip(".")
        self.source_bytes = before.st_size
        self.count = 0
        hasher = hashlib.sha256(encoded(["projected-source-1", self.kind, self.fields]))

        def records():
            for row in iterator:
                self.count += 1
                limits.check("max_records", self.count)
                try:
                    payload = encoded(row)
                except (ValueError, TypeError, RecursionError) as exc:
                    raise SnapshotRefused("source_encoding") from exc
                limits.check("max_record_bytes", len(payload))
                limits.check("max_batch_bytes", len(payload))
                hasher.update(len(payload).to_bytes(8, "big"))
                hasher.update(payload)
                yield row
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise SnapshotRefused("source_changed")
            wal = path.with_name(path.name + "-wal")
            if extension in (".sqlite", ".sqlite3", ".db") and wal.exists() and wal.stat().st_size:
                raise SnapshotRefused("source_changed")
            self.fingerprint = hasher.hexdigest()

        stream = records()
        try:
            yield stream
        finally:
            stream.close()
            iterator.close()


@contextmanager
def local_documents(path, *, fields=FIELDS, limits=None):
    """Storage API adapter that does not initialize a writable manager."""
    with LocalSource(path, fields=fields, limits=limits).open() as rows:
        yield rows
