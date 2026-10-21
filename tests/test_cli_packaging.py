"""CLI compatibility, offline dispatch and package resource regressions."""

import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from narrative_blueprint.cli.main import main
from narrative_blueprint.cli.parser import create_main_parser
from narrative_blueprint.resources import load_model_limits

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/diagnostic/vectors.csv"


@pytest.mark.parametrize("prefix,canonical,alias", [
    (["blueprint", "--prompt-template", "prompt.toml"], "--input", "--narrative-path"),
    (["blueprint", "--prompt-template", "prompt.toml", "--input", "text.csv"], "--result-file", "--output"),
    (["embeddings", "compute"], "--input", "--narrative-path"),
    (["embeddings", "compute"], "--vectors-file", "--embeddings-output"),
    (["embeddings", "compute"], "--vectors-file", "--embedding-output"),
    (["embeddings", "compute"], "--analysis-dir", "--output"),
    (["embeddings", "compute"], "--analysis-dir", "-o"),
    (["embeddings", "analyze"], "--source", "--analysis-source"),
    (["embeddings", "analyze"], "--analysis-dir", "--output"),
    (["embeddings", "analyze"], "--analysis-dir", "-o"),
])
def test_alias_parity_equal_duplicates_and_redacted_conflict(prefix, canonical, alias, capsys):
    parser = create_main_parser()
    value = "private-test-path"
    expected = vars(parser.parse_args([*prefix, canonical, value]))
    assert vars(parser.parse_args([*prefix, alias, value])) == expected
    assert vars(parser.parse_args([*prefix, canonical, value, alias, value])) == expected
    assert value not in capsys.readouterr().err
    with pytest.raises(SystemExit) as raised:
        parser.parse_args([*prefix, canonical, value, alias, "other-private-path"])
    assert raised.value.code == 2
    error = capsys.readouterr().err
    assert "conflicting values" in error
    assert value not in error and "other-private-path" not in error


@pytest.mark.parametrize("tail", [[], ["--skip-analysis"]])
def test_old_and_new_compute_share_arguments(tail):
    parser = create_main_parser()
    old = parser.parse_args(["embeddings", "--narrative-path", "text.csv",
                             "--embedding-output", "vectors.csv", "--output", "results", *tail])
    new = parser.parse_args(["embeddings", "compute", "--input", "text.csv",
                             "--vectors-file", "vectors.csv", "--analysis-dir", "results", *tail])
    assert vars(old) == vars(new)


@pytest.mark.parametrize("mode", ["compute", "analyze"])
def test_command_help_owns_only_its_options(mode, capsys):
    with pytest.raises(SystemExit) as raised:
        create_main_parser().parse_args(["embeddings", mode, "--help"])
    assert raised.value.code == 0
    help_text = capsys.readouterr().out
    if mode == "compute":
        assert "--vectors-file" in help_text and "--source" not in help_text
        assert "--declared-space" not in help_text and "--max-records" not in help_text
    else:
        assert "--source" in help_text and "--vectors-file" not in help_text
        assert "--model" not in help_text and "--input" not in help_text


@pytest.mark.parametrize("arguments", [
    ["embeddings", "analyze", "--model", "text-embedding-3-small"],
    ["embeddings", "analyze", "--input", "secret-input.csv"],
    ["embeddings", "analyze", "--vectors-file", "unused.csv"],
    ["embeddings", "analyze", "--skip-analysis"],
    ["embeddings", "compute", "--source", "unused.csv"],
    ["embeddings", "compute", "--max-records", "2"],
    ["embeddings", "compute", "--analysis-only"],
    ["embeddings", "compute", "--input", "unused.csv", "--skip-analysis",
     "--vectors-file", "unused.csv", "--mongo-db-name", "unused"],
    ["embeddings", "compute", "--input", "unused.csv", "--skip-analysis"],
    ["embeddings", "--analysis-only", "--skip-analysis"],
    ["blueprint", "--input", "unused.csv", "--prompt-template", "unused.toml"],
])
def test_invalid_commands_refuse_before_provider_import_in_fresh_process(arguments):
    result = subprocess.run([sys.executable, str(ROOT / "tests/offline_cli.py"), *arguments],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "Offline CLI imported" not in result.stderr


def test_optional_note_preserves_graph_and_source_metadata(tmp_path):
    statuses = []
    for name, note in [("omitted", []), ("supplied", ["--declared-space", "foo"])]:
        output = tmp_path / name
        main(["embeddings", "analyze", "--source", str(FIXTURE), "--allow-legacy-source",
              "--analysis-dir", str(output), *note])
        statuses.append(json.loads((output / "diagnostic-status.json").read_text()))
    assert statuses[0]["declared_space"] is None
    assert statuses[1]["declared_space"] == "foo"
    for key in ("source", "counts", "parameters", "outputs"):
        assert statuses[0][key] == statuses[1][key]
    assert not any(status["provenance_verified"] for status in statuses)


def test_blank_note_refuses_before_source_read(tmp_path, capsys):
    with pytest.raises(SystemExit) as raised:
        main(["embeddings", "analyze", "--source", "absent.csv", "--allow-legacy-source",
              "--analysis-dir", str(tmp_path / "new"), "--declared-space", " "])
    assert raised.value.code == 2
    assert "--declared-space must be nonblank" in capsys.readouterr().err
    assert not (tmp_path / "new").exists()


def test_packaged_defaults_ignore_cwd_and_provider_factory_uses_them(tmp_path, monkeypatch):
    from narrative_blueprint import models
    from narrative_blueprint.models.model import LanguageModel

    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "config/model_limits.json").write_text("not JSON")
    limits = load_model_limits()
    assert "gpt-4o-mini" in limits["openai"]
    assert LanguageModel.get_model_limits(None) == limits
    client = Mock()
    monkeypatch.setitem(models._PROVIDER_CLASS_MAP, "openai", client)
    assert models.get_llm_engine("gpt-4o-mini") is client.return_value
    client.assert_called_once_with("gpt-4o-mini")


def test_blueprint_dispatch_retains_local_destination_precedence(tmp_path, monkeypatch):
    from narrative_blueprint.runners import blueprint_runner as runner
    engine, storage, pipeline = Mock(), Mock(), Mock()
    monkeypatch.setattr(runner, "get_llm_engine", engine)
    monkeypatch.setattr(runner, "JSONFileManager", storage)
    monkeypatch.setattr(runner, "MongoDBManager", Mock(side_effect=AssertionError("Mongo selected")))
    monkeypatch.setattr(runner, "NarrativeBlueprint", pipeline)
    main(["blueprint", "--input", "text.csv", "--prompt-template", "prompt.toml",
          "--result-file", "result.json", "--mongo-db-name", "unused"])
    storage.assert_called_once_with(output_path="result.json")
    pipeline.return_value.run_blueprint_analysis.assert_called_once()


@pytest.mark.parametrize("tail", [[], ["--skip-analysis"]])
def test_canonical_compute_dispatch_retains_combined_and_skip_behavior(monkeypatch, tail):
    from narrative_blueprint import analysis, embeddings
    from narrative_blueprint.runners import embeddings_runner as runner
    model, pipeline = Mock(), Mock()
    monkeypatch.setattr(embeddings, "OpenAIEmbeddingModel", model)
    monkeypatch.setattr(runner, "_get_embedding_storage", Mock())
    monkeypatch.setattr(analysis, "EmbeddingAnalysis", pipeline)
    main(["embeddings", "compute", "--input", "text.csv", "--vectors-file", "vectors.csv",
          "--analysis-dir", "results", *tail])
    model.assert_called_once_with(model_name="text-embedding-3-small")
    assert pipeline.call_args.kwargs["args"]["skip_analysis"] == bool(tail)
    pipeline.return_value.run_embedding_analysis.assert_called_once()
