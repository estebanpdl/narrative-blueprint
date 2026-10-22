"""Synthetic source and snapshot integrity contracts, without provider activity."""

from array import array
from dataclasses import replace
import csv
import json
import math
import sqlite3

import pytest

from narrative_blueprint.corpus.contracts import SnapshotLimits, SnapshotRefused
from narrative_blueprint.corpus.sources import LocalSource
from narrative_blueprint.corpus.snapshot import build_snapshot
from narrative_blueprint.databases import CSVFileManager, SQLiteManager, ParquetFileManager


def record(uuid="001", text="Synthetic text", vector=None, **extra):
    return {"uuid": uuid, "text": text, "embedding": [3, 4] if vector is None else vector,
            "provider": "Fake", "model_name": "fixture", **extra}


def source(tmp_path, records, kind="csv"):
    path = tmp_path / ("vectors." + kind)
    manager = {"csv": CSVFileManager, "sqlite": SQLiteManager, "parquet": ParquetFileManager}[kind](str(path))
    manager.insert_many(records)
    manager.finalize()
    if hasattr(manager, "close"):
        manager.close()
    return path


def snapshot(tmp_path, records, **kwargs):
    path = source(tmp_path, records)
    return build_snapshot(path, tmp_path / "snapshot", allow_legacy_source=True, **kwargs)


@pytest.mark.parametrize("kind", ["csv", "sqlite", "parquet"])
def test_projected_readers_and_normalized_snapshot(tmp_path, monkeypatch, kind):
    # One consistent recipe, including extension fields stored as JSON metadata.
    path = source(tmp_path, [record(model_revision="v1"), record("002", vector=[1e308, 1e308], model_revision="v1")], kind)
    for cls in (CSVFileManager, SQLiteManager, ParquetFileManager):
        monkeypatch.setattr(cls, "get_documents", lambda *a: pytest.fail("full-list read"))
    reader = LocalSource(path, fields=("uuid",))
    with reader.open() as rows:
        assert list(rows) == [{"uuid": "001"}, {"uuid": "002"}]
    result = build_snapshot(path, tmp_path / "out", allow_legacy_source=True)
    assert result["counts"] == dict(selected=2, available=2, valid=2, missing=0,
                                    rejected=0, unique_texts=1, valid_unique_texts=1)
    assert result["reported_space"]["model_revision"] == "v1"
    assert result["generation_coverage"] == "unknown"
    with sqlite3.connect(tmp_path / "out/corpus.sqlite") as db:
        records = list(db.execute("SELECT source_uuid,text_hash,vector FROM records ORDER BY ordinal"))
    assert records[0][0] == "001"
    for _, _, blob in records:
        vector = array("f")
        vector.frombytes(blob)
        assert math.hypot(*vector) == pytest.approx(1, abs=1e-6)
    # Closed source/output handles permit rename on Windows.
    path.rename(path.with_name("closed." + kind))


@pytest.mark.parametrize("vector,reason", [
    ([], "invalid_vector_shape"), ([0, 0], "zero_vector"),
    ([True, 1], "nonnumeric_vector"), ([[1], [2]], "nonnumeric_vector"),
    ([float("inf"), 1], "nonfinite_vector"), ([float("nan"), 1], "nonfinite_vector"),
    ("broken", "invalid_vector_shape"),
])
def test_invalid_vectors_accounted_without_losing_occurrences(tmp_path, vector, reason):
    result = snapshot(tmp_path, [record(vector=vector)])
    assert result["counts"]["rejected"] == 1
    assert result["rejection_reasons"] == {reason: 1}
    assert not result["analysis_ready"]


@pytest.mark.parametrize("change,reason", [
    ({"provider": "Other"}, "mixed_space"), ({"task_type": "CLUSTERING"}, "mixed_space"),
    ({"embedding": [1, 2, 3]}, "mixed_dimension"), ({"uuid": "001"}, "ambiguous_uuid"),
])
def test_conflicts_refuse_without_completion_marker(tmp_path, change, reason):
    with pytest.raises(SnapshotRefused, match=reason):
        snapshot(tmp_path, [record(), {**record("002"), **change}])
    assert not (tmp_path / "snapshot/snapshot.json").exists()
    status = json.loads((tmp_path / "snapshot/status.json").read_text())
    assert status["status"] == "refused"
    assert status["counts"]["selected"] == 2


def test_explicit_occurrences_preserve_duplicates_and_collapse_attempts(tmp_path):
    records = [record(occurrence_id="a"), record(occurrence_id="b"), record(occurrence_id="a")]
    result = snapshot(tmp_path, records)
    assert result["counts"]["selected"] == 2
    assert result["counts"]["unique_texts"] == 1
    assert result["duplicate_attempts"] == 1
    assert result["available_rows"] == 3


def test_conflicting_attempt_is_not_a_second_node(tmp_path):
    with pytest.raises(SnapshotRefused, match="conflicting_attempt"):
        snapshot(tmp_path, [record(occurrence_id="a"), record(occurrence_id="a", vector=[4, 3])])


def test_empty_and_missing_vector_counts(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("uuid,text,embedding\n", encoding="utf-8")
    result = build_snapshot(path, tmp_path / "empty", allow_legacy_source=True)
    assert result["counts"]["selected"] == 0
    path.write_text('uuid,text,embedding\n001,synthetic,\n', encoding="utf-8")
    result = build_snapshot(path, tmp_path / "missing", allow_legacy_source=True)
    assert result["counts"]["missing"] == 1
    assert result["counts"]["available"] == 0


def test_stable_identity_declaration_and_source_unchanged(tmp_path):
    path = source(tmp_path, [record(text="=literal\nEspañol, test")])
    before = path.read_bytes()
    first = build_snapshot(path, tmp_path / "a", allow_legacy_source=True, declared_space="note")
    second = build_snapshot(path, tmp_path / "b", allow_legacy_source=True)
    assert first["source_fingerprint"] == second["source_fingerprint"]
    ids = []
    for folder in ("a", "b"):
        with sqlite3.connect(tmp_path / folder / "corpus.sqlite") as db:
            ids.append(db.execute("SELECT occurrence_id FROM records").fetchone()[0])
    assert ids[0] == ids[1]
    assert path.read_bytes() == before
    assert first["declared_space"] == "note" and not first["provenance_verified"]


@pytest.mark.parametrize("name,value", [
    ("max_source_bytes", 10), ("max_records", 1), ("max_record_bytes", 40),
    ("max_disk_bytes", 100),
])
def test_caps_refuse_without_truncating_success(tmp_path, name, value):
    with pytest.raises((SnapshotRefused, sqlite3.DatabaseError)):
        snapshot(tmp_path, [record(), record("002")], limits=replace(SnapshotLimits(), **{name: value}))
    assert not (tmp_path / "snapshot/snapshot.json").exists()


def test_multiline_record_limited_before_decode_and_reader_closed(tmp_path):
    path = tmp_path / "vectors.csv"
    path.write_text('uuid,text,embedding\n001,"' + ('abc\n' * 100) + '","[1,2]"\n')
    old = csv.field_size_limit()
    with pytest.raises(SnapshotRefused, match="max_record_bytes"):
        with LocalSource(path, replace(SnapshotLimits(), max_record_bytes=80)).open() as rows:
            next(rows)
    assert csv.field_size_limit() == old
    path.unlink()


def test_close_after_early_exit(tmp_path):
    path = source(tmp_path, [record(), record("002")])
    old = csv.field_size_limit()
    with LocalSource(path).open() as rows:
        next(rows)
    assert csv.field_size_limit() == old
    path.unlink()


def test_interrupted_snapshot_has_no_success(tmp_path, monkeypatch):
    from narrative_blueprint.corpus.snapshot import Admission
    path = source(tmp_path, [record()])
    monkeypatch.setattr(Admission, "accept", lambda *a: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        build_snapshot(path, tmp_path / "out", allow_legacy_source=True)
    assert not (tmp_path / "out/snapshot.json").exists()
    assert json.loads((tmp_path / "out/status.json").read_text())["status"] == "interrupted"
    path.unlink()


def test_publication_failure_and_existing_output_preserved(tmp_path, monkeypatch):
    from narrative_blueprint.corpus import snapshot as module
    path = source(tmp_path, [record()])
    original = module.write_json
    def fail_marker(path, value):
        if path.name == "snapshot.json":
            raise OSError("fake disk failure")
        original(path, value)
    monkeypatch.setattr(module, "write_json", fail_marker)
    with pytest.raises(OSError):
        build_snapshot(path, tmp_path / "out", allow_legacy_source=True)
    assert not (tmp_path / "out/snapshot.json").exists()
    with pytest.raises(SnapshotRefused, match="output_exists"):
        build_snapshot(path, tmp_path / "out", allow_legacy_source=True)


def test_parquet_row_group_decode_cap(tmp_path):
    path = source(tmp_path, [record(text="x" * 2000)], "parquet")
    with pytest.raises(SnapshotRefused, match="max_batch_bytes"):
        with LocalSource(path, replace(SnapshotLimits(), max_batch_bytes=100)).open() as rows:
            next(rows)


def test_sqlite_projection_does_not_decode_unrequested_payload(tmp_path):
    path = source(tmp_path, [record(text="x" * 2000)], "sqlite")
    with LocalSource(path, replace(SnapshotLimits(), max_record_bytes=100), fields=("uuid",)).open() as rows:
        assert list(rows) == [{"uuid": "001"}]


def test_mongo_filter_projection_order_batch_and_closure():
    from narrative_blueprint.corpus.columnar import mongo_documents
    class Cursor:
        closed = False
        def sort(self, field, order):
            assert (field, order) == ("_id", 1)
            return self
        def batch_size(self, size):
            assert 0 < size <= 128
            return self
        def __iter__(self):
            yield {"uuid": "001"}
            raise RuntimeError("fake cursor error")
        def close(self):
            self.closed = True
    cursor = Cursor()
    class Collection:
        def find(self, query, projection):
            assert query == {"generation_id": "run"}
            assert projection == {"uuid": 1, "metadata": 1, "_id": 0}
            return cursor
    with pytest.raises(RuntimeError):
        with mongo_documents(Collection(), fields=("uuid",), query={"generation_id": "run"}) as rows:
            assert next(rows) == {"uuid": "001"}
            next(rows)
    assert cursor.closed


def test_mongo_configuration_failure_closes_cursor():
    from narrative_blueprint.corpus.columnar import mongo_documents
    from unittest.mock import Mock
    cursor = Mock()
    cursor.sort.side_effect = RuntimeError("sort failed")
    collection = Mock()
    collection.find.return_value = cursor
    with pytest.raises(RuntimeError):
        with mongo_documents(collection):
            pass
    cursor.close.assert_called_once()


def test_wal_source_refused_without_touching_sidecars(tmp_path):
    path = source(tmp_path, [record()], "sqlite")
    wal = path.with_name(path.name + "-wal")
    wal.write_bytes(b"synthetic WAL stand-in")
    with pytest.raises(SnapshotRefused, match="sqlite_wal_active"):
        with LocalSource(path).open() as rows:
            next(rows)
    assert wal.read_bytes() == b"synthetic WAL stand-in"


def test_source_mutation_detected(tmp_path):
    path = source(tmp_path, [record()])
    with pytest.raises(SnapshotRefused, match="source_changed"):
        with LocalSource(path).open() as rows:
            next(rows)
            with path.open("a", newline="") as writer:
                csv.writer(writer).writerow(["002", "Synthetic", "[3,4]", "fixture", "Fake"])
            list(rows)


def test_working_limit_refuses_impossible_buffers():
    with pytest.raises(SnapshotRefused, match="max_working_bytes"):
        SnapshotLimits(max_working_bytes=100)


def test_invalid_identity_is_recorded(tmp_path):
    result = snapshot(tmp_path, [record(uuid="", text=" ")])
    assert result["counts"]["rejected"] == 1
    assert result["rejection_reasons"] == {"invalid_uuid": 1}


def test_dimension_is_budgeted_without_fixed_ceiling(tmp_path):
    result = snapshot(tmp_path, [record(vector=[1.0] * 20000)])
    assert result["dimension"] == 20000 and result["counts"]["valid"] == 1


def test_unknown_legacy_expected_counts_are_null(tmp_path):
    result = snapshot(tmp_path, [record()])
    assert result["expected_original"] is None and result["missing_original"] is None


def test_conflicting_extension_metadata_refuses(tmp_path):
    path = source(tmp_path, [record()], "sqlite")
    with sqlite3.connect(path) as db:
        db.execute('UPDATE embeddings SET metadata=?', (json.dumps({"provider": "Other"}),))
    with pytest.raises(SnapshotRefused, match="conflicting_metadata"):
        build_snapshot(path, tmp_path / "out", allow_legacy_source=True)


def test_disk_budget_admitted_before_output_creation(tmp_path):
    with pytest.raises(SnapshotRefused, match="max_disk_bytes"):
        snapshot(tmp_path, [record()], limits=replace(SnapshotLimits(), max_disk_bytes=1024))
    assert not (tmp_path / "snapshot").exists()
