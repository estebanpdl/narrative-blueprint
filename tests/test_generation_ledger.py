"""Fake provider responses and injected persistence/exhaustion failures."""

import json
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from narrative_blueprint.corpus.contracts import SnapshotRefused
from narrative_blueprint.corpus.snapshot import build_snapshot
from narrative_blueprint.databases import CSVFileManager, SQLiteManager, ParquetFileManager
from narrative_blueprint.embeddings.base import VectorModel
from narrative_blueprint.embeddings.ledger import run_generation, GenerationIncomplete
from narrative_blueprint.embeddings.gemini_embeddings import GeminiEmbeddingModel
from narrative_blueprint.embeddings.openai_embeddings import OpenAIEmbeddingModel


def fake_model(kind="gemini"):
    cls = GeminiEmbeddingModel if kind == "gemini" else OpenAIEmbeddingModel
    model = cls.__new__(cls)
    VectorModel.__init__(model)
    model.model_name = "fixture"
    model.task_type = "CLUSTERING" if kind == "gemini" else None
    model.max_requests_per_min = model.max_tokens_per_min = 1_000_000
    model.estimate_tokens = lambda text: 1
    model.client = Mock()
    response = SimpleNamespace(embeddings=[SimpleNamespace(values=[3., 4.])]) if kind == "gemini" else SimpleNamespace(data=[SimpleNamespace(embedding=[3., 4.], index=0)])
    request = model.client.models.embed_content if kind == "gemini" else model.client.embeddings.create
    request.return_value = response
    return model, request


def outcomes(path):
    with sqlite3.connect(path) as db:
        return list(db.execute("SELECT source_uuid,state,reason FROM outcomes ORDER BY ordinal")), dict(db.execute("SELECT key,value FROM metadata"))


@pytest.mark.parametrize("kind", ["gemini", "openai"])
@pytest.mark.parametrize("store_kind", ["csv", "sqlite", "parquet"])
def test_successful_fake_generation_snapshot_join(tmp_path, kind, store_kind):
    model, request = fake_model(kind)
    vector_path = tmp_path / ("vectors." + store_kind)
    storage = {"csv": CSVFileManager, "sqlite": SQLiteManager, "parquet": ParquetFileManager}[store_kind](str(vector_path))
    path = tmp_path / "ledger.sqlite"
    run_generation(model, storage, ["001"], ["Synthetic"], path)
    if hasattr(storage, "close"):
        storage.close()
    rows, meta = outcomes(path)
    assert rows == [("001", "stored", None)] and meta["status"] == "complete"
    result = build_snapshot(vector_path, tmp_path / "snapshot", generation_ledger=path)
    assert result["generation_coverage"] == "complete"
    assert result["counts"]["valid"] == 1
    assert request.call_count == 1


@pytest.mark.parametrize("kind", ["gemini", "openai"])
def test_successful_response_never_replayed_after_store_failure(tmp_path, kind, monkeypatch):
    model, request = fake_model(kind)
    storage = CSVFileManager(str(tmp_path / "vectors.csv"))
    monkeypatch.setattr(storage, "insert_many", Mock(side_effect=OSError("fake store failure")))
    path = tmp_path / "ledger.sqlite"
    with pytest.raises(OSError):
        run_generation(model, storage, ["001"], ["Synthetic"], path)
    assert request.call_count == 1
    rows, meta = outcomes(path)
    assert rows[0][1:] == ("storage_failed", "store_failure")
    assert meta["status"] == "incomplete"


@pytest.mark.parametrize("kind", ["gemini", "openai"])
def test_exhaustion_propagates_and_records_terminal_outcome(tmp_path, kind, monkeypatch):
    model, request = fake_model(kind)
    if kind == "openai":
        from narrative_blueprint.embeddings import openai_embeddings as module
        class FakeRateLimit(Exception):
            pass
        monkeypatch.setattr(module, "RateLimitError", FakeRateLimit)
        request.side_effect = FakeRateLimit("fake quota")
    else:
        request.side_effect = RuntimeError("fake provider failure")
    monkeypatch.setattr("time.sleep", lambda *a: None)
    storage = CSVFileManager(str(tmp_path / "vectors.csv"))
    path = tmp_path / "ledger.sqlite"
    with pytest.raises(RuntimeError, match="exhausted"):
        run_generation(model, storage, ["001"], ["Synthetic"], path)
    assert request.call_count == 3
    assert outcomes(path)[0][0][1] == "provider_failed"


def test_finalize_failure_is_terminal(tmp_path, monkeypatch):
    model, request = fake_model()
    storage = CSVFileManager(str(tmp_path / "vectors.csv"))
    monkeypatch.setattr(storage, "finalize", Mock(side_effect=OSError("fake finalize")))
    path = tmp_path / "ledger.sqlite"
    with pytest.raises(OSError):
        run_generation(model, storage, ["001"], ["Synthetic"], path)
    assert outcomes(path)[0][0][1:] == ("storage_failed", "finalize_failure")
    assert request.call_count == 1
    with pytest.raises(SnapshotRefused, match="incomplete_generation"):
        build_snapshot(tmp_path / "vectors.csv", tmp_path / "no", generation_ledger=path)
    partial = build_snapshot(tmp_path / "vectors.csv", tmp_path / "partial", generation_ledger=path, allow_partial=True)
    assert partial["counts"]["rejected"] == 1 and partial["counts"]["valid"] == 0
    assert partial["generation_coverage"] == "partial"


def test_missing_expected_input_and_legacy_bypass_refused(tmp_path):
    model, request = fake_model()
    storage = CSVFileManager(str(tmp_path / "vectors.csv"))
    ledger = tmp_path / "ledger.sqlite"
    run_generation(model, storage, ["001"], ["Synthetic"], ledger)
    with pytest.raises(SnapshotRefused, match="generation_ledger_required"):
        build_snapshot(tmp_path / "vectors.csv", tmp_path / "bypass", allow_legacy_source=True)
    # Remove a stored output row while retaining the expectation receipt.
    content = (tmp_path / "vectors.csv").read_text().splitlines()[0]
    (tmp_path / "vectors.csv").write_text(content + "\n")
    with pytest.raises(SnapshotRefused, match="incomplete_generation"):
        build_snapshot(tmp_path / "vectors.csv", tmp_path / "missing", generation_ledger=ledger)
    partial = build_snapshot(tmp_path / "vectors.csv", tmp_path / "partial", generation_ledger=ledger, allow_partial=True)
    assert partial["counts"]["selected"] == partial["counts"]["missing"] == 1
    assert partial["counts"]["available"] == 0


def test_silent_provider_shortfall_cannot_succeed(tmp_path):
    model, _ = fake_model()
    model.compute_embeddings = lambda **kw: None
    with pytest.raises(GenerationIncomplete):
        run_generation(model, CSVFileManager(str(tmp_path / "vectors.csv")), ["001"], ["Synthetic"], tmp_path / "ledger.sqlite")
    assert outcomes(tmp_path / "ledger.sqlite")[0][0][1] == "not_attempted"


def test_interruption_terminalizes_pending(tmp_path):
    model, request = fake_model()
    request.side_effect = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        run_generation(model, CSVFileManager(str(tmp_path / "vectors.csv")), ["001"], ["Synthetic"], tmp_path / "ledger.sqlite")
    assert outcomes(tmp_path / "ledger.sqlite")[0][0][1] == "interrupted"


def test_two_runs_select_only_requested_generation(tmp_path):
    model, _ = fake_model()
    storage = CSVFileManager(str(tmp_path / "vectors.csv"))
    for number in range(2):
        run_generation(model, storage, ["001"], ["Synthetic"], tmp_path / f"ledger{number}.sqlite")
    result = build_snapshot(tmp_path / "vectors.csv", tmp_path / "snapshot", generation_ledger=tmp_path / "ledger1.sqlite")
    assert result["counts"]["selected"] == result["counts"]["valid"] == 1
    assert result["unselected_rows"] == 1


def test_response_count_mismatch_not_retried(tmp_path):
    model, request = fake_model()
    request.return_value.embeddings = []
    with pytest.raises(ValueError, match="count mismatch"):
        run_generation(model, CSVFileManager(str(tmp_path / "vectors.csv")), ["001"], ["Synthetic"], tmp_path / "ledger.sqlite")
    assert request.call_count == 1
    assert outcomes(tmp_path / "ledger.sqlite")[0][0][1] == "provider_failed"


def test_snapshot_verifies_response_hash(tmp_path):
    model, _ = fake_model()
    path = tmp_path / "vectors.sqlite"
    storage = SQLiteManager(str(path))
    ledger = tmp_path / "ledger.sqlite"
    run_generation(model, storage, ["001"], ["Synthetic"], ledger)
    storage.connection.execute("UPDATE embeddings SET embedding='[4,3]'")
    storage.connection.commit()
    storage.close()
    with pytest.raises(SnapshotRefused, match="ledger_response_mismatch"):
        build_snapshot(path, tmp_path / "out", generation_ledger=ledger)


def test_existing_ledger_not_overwritten(tmp_path):
    model, request = fake_model()
    ledger = tmp_path / "ledger.sqlite"
    ledger.write_bytes(b"prior receipt")
    with pytest.raises(FileExistsError):
        run_generation(model, CSVFileManager(str(tmp_path / "vectors.csv")), ["001"], ["Synthetic"], ledger)
    assert request.call_count == 0 and ledger.read_bytes() == b"prior receipt"


def test_repeated_uuid_is_distinct_with_generation_occurrence_mapping(tmp_path):
    model, request = fake_model()
    request.return_value.embeddings.append(SimpleNamespace(values=[3., 4.]))
    storage = CSVFileManager(str(tmp_path / "vectors.csv"))
    path = tmp_path / "ledger.sqlite"
    run_generation(model, storage, ["001", "001"], ["Synthetic", "Synthetic"], path)
    result = build_snapshot(tmp_path / "vectors.csv", tmp_path / "out", generation_ledger=path)
    assert result["counts"]["selected"] == 2 and result["counts"]["unique_texts"] == 1


def test_prior_batch_preserved_when_later_request_fails(tmp_path, monkeypatch):
    model, request = fake_model()
    model.DOCS_PER_BATCH = 1
    first = request.return_value
    request.side_effect = [first, RuntimeError("fake"), RuntimeError("fake"), RuntimeError("fake")]
    monkeypatch.setattr("time.sleep", lambda *a: None)
    storage = CSVFileManager(str(tmp_path / "vectors.csv"))
    ledger = tmp_path / "ledger.sqlite"
    with pytest.raises(RuntimeError):
        run_generation(model, storage, ["001", "002", "003"], ["Synthetic"] * 3, ledger)
    assert [row[1] for row in outcomes(ledger)[0]] == ["stored", "provider_failed", "not_attempted"]
    result = build_snapshot(tmp_path / "vectors.csv", tmp_path / "partial", generation_ledger=ledger, allow_partial=True)
    assert result["counts"] == dict(selected=3, available=1, valid=1, missing=2, rejected=0,
                                    unique_texts=1, valid_unique_texts=1)


def test_failed_parquet_replacement_preserves_previous_store(tmp_path, monkeypatch):
    from narrative_blueprint.databases import parquet_file
    path = tmp_path / "vectors.parquet"
    storage = ParquetFileManager(str(path))
    storage.insert_one(dict(uuid="old", text="old synthetic", embedding=[1., 0.], provider="Fake", model_name="fixture"))
    storage.finalize()
    prior = path.read_bytes()
    model, request = fake_model()
    monkeypatch.setattr(parquet_file.os, "replace", Mock(side_effect=OSError("fake replace")))
    ledger = tmp_path / "ledger.sqlite"
    with pytest.raises(OSError):
        run_generation(model, storage, ["001"], ["Synthetic"], ledger)
    storage.abort()
    assert path.read_bytes() == prior
    assert request.call_count == 1 and outcomes(ledger)[0][0][1] == "storage_failed"
