"""Exercise admission, identity, legacy limitations and publication failures."""

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from narrative_blueprint.analysis.diagnostic import DiagnosticAnalysis, run_diagnostic
from narrative_blueprint.cli.analysis_options import LIMITS, validate_embeddings_args
from narrative_blueprint.cli.parser import create_main_parser
from narrative_blueprint.runners.embeddings_runner import handle_embeddings


FIXTURES = Path(__file__).parent / "fixtures" / "diagnostic"


def arguments(tmp_path, source="vectors.csv", **overrides):
    args = {
        "analysis_only": True,
        "analysis_source": str(FIXTURES / source),
        "declared_space": "synthetic/fixture-v1",
        "allow_legacy_source": True,
        "output": str(tmp_path / "result"),
        "threshold": 0.75,
    }
    args.update(overrides)
    return args


def write_source(tmp_path, rows, fields=("uuid", "text", "embedding")):
    source = tmp_path / "input.csv"
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows(rows)
    return str(source)


def test_selection_keeps_occurrences_but_reports_legacy_loss(tmp_path):
    status = run_diagnostic(arguments(tmp_path))
    output = tmp_path / "result"
    selection = json.loads((output / "selection.json").read_text(encoding="utf-8"))
    assert [row["source_uuid"] for row in selection] == ["001", "002", "003", "004"]
    assert len({row["occurrence_id"] for row in selection}) == 4
    assert selection[0]["text_hash"] == selection[1]["text_hash"]
    assert status["counts"]["selected_occurrences"] == 4
    assert status["counts"]["unique_texts"] == 3
    assert status["counts"]["legacy_represented_unique_texts"] == 2
    assert status["counts"]["legacy_communities"] == 1
    assert status["generation_completeness"] == "unknown"
    assert status["corrected_analysis_complete"] is False
    assert status["provenance_verified"] is False
    assert status["status"] == "diagnostic_complete"
    assert not (output / "manifest.json").exists()
    for name, digest in status["outputs"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
    second = arguments(tmp_path, output=str(tmp_path / "second"))
    run_diagnostic(second)
    assert json.loads((tmp_path / "second" / "selection.json").read_text(encoding="utf-8")) == selection


@pytest.mark.parametrize("source,count", [("empty.csv", 0), ("no-edges.csv", 2)])
def test_empty_and_no_edges_have_current_diagnostic_outputs(tmp_path, source, count):
    result = run_diagnostic(arguments(tmp_path, source))
    assert result["counts"]["selected_occurrences"] == count
    assert result["counts"]["legacy_communities"] == 0
    assert json.loads((tmp_path / "result" / "legacy-communities.json").read_text()) == []


def test_singleton_and_multiline_text_remain_in_selection(tmp_path):
    source = write_source(tmp_path, [("0001", "=SUM(1,2)\nEspañol\ttexto", "[1, 0]")])
    result = run_diagnostic(arguments(tmp_path, analysis_source=source))
    selection = json.loads((tmp_path / "result" / "selection.json").read_text(encoding="utf-8"))
    assert selection[0]["text"] == "=SUM(1,2)\nEspañol\ttexto"
    assert selection[0]["source_uuid"] == "0001"
    assert result["counts"]["legacy_communities"] == 0


@pytest.mark.parametrize("field,value", [
    ("max_records", 3), ("max_dimension", 2), ("max_source_bytes", 10),
    ("max_pairs", 5), ("max_working_bytes", 1),
])
def test_caps_refuse_before_graph_or_output(tmp_path, monkeypatch, field, value):
    graph = Mock(side_effect=AssertionError("Graph must not run"))
    monkeypatch.setattr(DiagnosticAnalysis, "run_similarity_analysis", graph)
    with pytest.raises(ValueError, match=field):
        handle_embeddings(arguments(tmp_path, **{field: value}))
    graph.assert_not_called()
    assert not (tmp_path / "result").exists()


def test_exact_limits_are_admitted(tmp_path):
    first = run_diagnostic(arguments(tmp_path))
    exact = {
        "max_records": 4, "max_dimension": 3,
        "max_source_bytes": first["source"]["bytes"], "max_pairs": 6,
        "max_working_bytes": first["source"]["estimated_working_bytes"],
        "output": str(tmp_path / "exact"),
    }
    assert run_diagnostic(arguments(tmp_path, **exact))["status"] == "diagnostic_complete"


@pytest.mark.parametrize("field", list(LIMITS))
@pytest.mark.parametrize("boundary", ["zero", "above"])
def test_invalid_limit_values(tmp_path, field, boundary):
    value = 0 if boundary == "zero" else LIMITS[field][1] + 1
    with pytest.raises(ValueError, match=field.replace("_", "-")):
        handle_embeddings(arguments(tmp_path, **{field: value}))


@pytest.mark.parametrize("vector", ["[]", "[0,0]", "[NaN,1]", "[Infinity,1]",
                                   "[true,1]", '["1",2]', "[[1],2]", "{}",
                                   "[1e200,1]", "[1e-200,0]", "bad"])
def test_invalid_vectors_refuse_entire_run(tmp_path, vector):
    source = write_source(tmp_path, [("001", "text", vector)])
    with pytest.raises(ValueError, match="Row 1"):
        handle_embeddings(arguments(tmp_path, analysis_source=source))
    assert not (tmp_path / "result").exists()


@pytest.mark.parametrize("rows,match", [
    ([("001", "one", "[1,0]"), ("001", "two", "[1,0]")], "repeated uuid"),
    ([("001", "one", "[1,0]"), ("002", "two", "[1]")], "dimension"),
    ([("", "one", "[1,0]")], "nonempty"),
    ([("001", "", "[1,0]")], "nonempty"),
])
def test_ambiguous_or_invalid_records_refuse(tmp_path, rows, match):
    source = write_source(tmp_path, rows)
    with pytest.raises(ValueError, match=match):
        handle_embeddings(arguments(tmp_path, analysis_source=source))


@pytest.mark.parametrize("second", ["different-model", ""])
def test_mixed_or_partial_space_metadata_refuses(tmp_path, second):
    source = write_source(tmp_path, [
        ("001", "one", "[1,0]", "model"),
        ("002", "two", "[1,0]", second),
    ], fields=("uuid", "text", "embedding", "model_name"))
    with pytest.raises(ValueError, match="model_name"):
        handle_embeddings(arguments(tmp_path, analysis_source=source))


@pytest.mark.parametrize("key,value", [
    ("model", "text-embedding-3-small"), ("narrative_path", "unused.csv"),
    ("gemini_task_type", "CLUSTERING"), ("embeddings_output", "unused.csv"),
    ("mongo_db_name", "unused"), ("mongo_collection_name", "unused"),
    ("skip_analysis", True), ("allow_legacy_source", False),
    ("declared_space", ""), ("analysis_source", ""), ("output", ""),
    ("threshold", 0), ("threshold", -1), ("threshold", 1.1),
    ("threshold", float("nan")), ("threshold", float("inf")),
])
def test_conflicts_and_missing_declarations_fail_before_source_read(tmp_path, key, value):
    args = arguments(tmp_path, analysis_source="absent.csv")
    args[key] = value
    with pytest.raises(ValueError):
        handle_embeddings(args)
    assert not (tmp_path / "result").exists()


def test_compute_requires_input_and_rejects_diagnostic_options():
    with pytest.raises(ValueError, match="narrative-path"):
        validate_embeddings_args({})
    with pytest.raises(ValueError, match="require --analysis-only"):
        validate_embeddings_args({"narrative_path": "unused", "max_records": 2})


def test_existing_output_is_not_overwritten(tmp_path):
    run_diagnostic(arguments(tmp_path))
    status = (tmp_path / "result" / "diagnostic-status.json").read_bytes()
    with pytest.raises(ValueError, match="new directory"):
        run_diagnostic(arguments(tmp_path))
    assert (tmp_path / "result" / "diagnostic-status.json").read_bytes() == status


def test_graph_failure_cannot_publish_success(tmp_path, monkeypatch):
    monkeypatch.setattr(DiagnosticAnalysis, "run_similarity_analysis",
                        Mock(side_effect=RuntimeError("synthetic failure")))
    with pytest.raises(RuntimeError, match="synthetic failure"):
        run_diagnostic(arguments(tmp_path))
    status = json.loads((tmp_path / "result" / "diagnostic-status.json").read_text())
    assert status["status"] == "failed"
    assert not (tmp_path / "result" / "manifest.json").exists()


def test_output_failure_cannot_publish_success(tmp_path, monkeypatch):
    import narrative_blueprint.analysis.diagnostic as diagnostic
    from main import main
    original = diagnostic._write_json

    def fail_community_output(path, value):
        if path.name == "legacy-communities.json":
            raise OSError("synthetic disk failure")
        original(path, value)

    monkeypatch.setattr(diagnostic, "_write_json", fail_community_output)
    with pytest.raises(OSError, match="synthetic disk failure"):
        main([
            "embeddings", "--analysis-only", "--analysis-source", str(FIXTURES / "vectors.csv"),
            "--declared-space", "synthetic/fixture-v1", "--allow-legacy-source",
            "--output", str(tmp_path / "result"),
        ])
    status = json.loads((tmp_path / "result" / "diagnostic-status.json").read_text())
    assert status["status"] == "failed"
    assert "legacy-communities.json" not in status["outputs"]


def test_interruption_cannot_publish_success(tmp_path, monkeypatch):
    monkeypatch.setattr(DiagnosticAnalysis, "run_similarity_analysis",
                        Mock(side_effect=KeyboardInterrupt))
    with pytest.raises(KeyboardInterrupt):
        run_diagnostic(arguments(tmp_path))
    assert not (tmp_path / "result" / "diagnostic-status.json").exists()


@pytest.mark.parametrize("tail", [[], ["--skip-analysis"]])
def test_compute_dispatch_uses_lazy_fake_provider(tmp_path, monkeypatch, tail):
    import narrative_blueprint.embeddings as embeddings
    import narrative_blueprint.analysis as analysis
    import narrative_blueprint.runners.embeddings_runner as runner
    model, storage, pipeline = Mock(), Mock(), Mock()
    monkeypatch.setattr(embeddings, "OpenAIEmbeddingModel", model)
    monkeypatch.setattr(runner, "_get_embedding_storage", Mock(return_value=storage))
    monkeypatch.setattr(analysis, "EmbeddingAnalysis", pipeline)
    args = vars(create_main_parser().parse_args([
        "embeddings", "--narrative-path", "synthetic.csv",
        "--embeddings-output", "synthetic-output.csv", "--output", str(tmp_path), *tail,
    ]))
    handle_embeddings(args)
    model.assert_called_once_with(model_name="text-embedding-3-small")
    assert pipeline.call_args.kwargs["args"]["skip_analysis"] == bool(tail)
    pipeline.return_value.run_embedding_analysis.assert_called_once()


@pytest.mark.parametrize("error_type", [PermissionError, ValueError])
def test_compute_runtime_errors_propagate(tmp_path, monkeypatch, capsys, error_type):
    import narrative_blueprint.analysis as analysis
    import narrative_blueprint.embeddings as embeddings
    import narrative_blueprint.runners.embeddings_runner as runner
    from main import main

    failure = error_type("synthetic runtime failure")
    pipeline = Mock()
    pipeline.return_value.run_embedding_analysis.side_effect = failure
    monkeypatch.setattr(embeddings, "OpenAIEmbeddingModel", Mock())
    monkeypatch.setattr(runner, "_get_embedding_storage", Mock())
    monkeypatch.setattr(analysis, "EmbeddingAnalysis", pipeline)
    with pytest.raises(error_type) as raised:
        main([
            "embeddings", "--narrative-path", "synthetic.csv",
            "--embeddings-output", "synthetic-output.csv", "--output", str(tmp_path),
        ])
    assert raised.value is failure
    assert "usage:" not in capsys.readouterr().err
    pipeline.return_value.run_embedding_analysis.assert_called_once()


@pytest.mark.parametrize("tail", [
    ["--max-records", "0"], ["--max-records", "3"], ["--output", "."],
])
def test_diagnostic_refusals_remain_usage_errors(tmp_path, capsys, tail):
    from main import main

    with pytest.raises(SystemExit) as raised:
        main([
            "embeddings", "--analysis-only", "--analysis-source", str(FIXTURES / "vectors.csv"),
            "--declared-space", "synthetic/fixture-v1", "--allow-legacy-source",
            "--output", str(tmp_path / "result"), *tail,
        ])
    assert raised.value.code == 2
    assert "usage:" in capsys.readouterr().err
    assert not (tmp_path / "result").exists()


@pytest.mark.parametrize("cli_args,code", [
    (["--help"], 0), (["embeddings", "--help"], 0), (["blueprint", "--help"], 0),
    (["embeddings", "--analysis-only", "--skip-analysis"], 2),
])
def test_fresh_process_help_and_invalid_dispatch_are_offline(cli_args, code):
    result = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("offline_cli.py")), *cli_args],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == code, result.stdout + result.stderr
    assert "Offline CLI imported" not in result.stderr


def test_fresh_process_fixture_analysis_is_offline(tmp_path):
    result = subprocess.run([
        sys.executable, str(Path(__file__).with_name("offline_cli.py")),
        "embeddings", "--analysis-only", "--analysis-source", str(FIXTURES / "vectors.csv"),
        "--declared-space", "synthetic/fixture-v1", "--allow-legacy-source",
        "--output", str(tmp_path / "fresh"),
    ], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Output status: diagnostic_complete" in result.stdout
