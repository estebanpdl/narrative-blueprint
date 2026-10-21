"""User-facing guidance and executable documentation for the diagnostic."""

import csv
import subprocess
import sys
from pathlib import Path

import pytest

from analysis.diagnostic_source import read_source
from cli.analysis_options import EmbeddingInputError, effective_limits
from cli.parser import create_main_parser
from main import main


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("option,example", [
    ("--declared-space", 'gemini-embedding-001 / CLUSTERING / original text'),
    ("--analysis-source", '--analysis-source subset.csv'),
    ("--output", '--output results/diagnostic-01'),
    ("-o", '--output results/diagnostic-01'),
])
def test_missing_option_value_has_actionable_example(option, example, capsys):
    with pytest.raises(SystemExit) as raised:
        create_main_parser().parse_args(["embeddings", "--analysis-only", option])
    assert raised.value.code == 2
    message = capsys.readouterr().err
    assert "expected one argument" in message
    assert "expects" in message
    assert example in message


@pytest.mark.parametrize("option,value,example", [
    ("--declared-space", "synthetic/fixture-v1", "CLUSTERING"),
    ("--analysis-source", "unused.csv", "--analysis-source subset.csv"),
    ("--output", "unused-output", "--output results/diagnostic-01"),
    ("--allow-legacy-source", None, "takes no value"),
])
@pytest.mark.parametrize("blank", [False, True])
def test_missing_or_blank_required_option_explains_expected_input(option, value, example, blank, capsys):
    argv = ["embeddings", "--analysis-only"]
    for flag, argument in [
        ("--analysis-source", "unused.csv"),
        ("--declared-space", "synthetic/fixture-v1"),
        ("--output", "unused-output"),
        ("--allow-legacy-source", None),
    ]:
        if flag == option:
            if blank and value is not None:
                argv.extend([flag, " "])
            continue
        argv.append(flag)
        if argument is not None:
            argv.append(argument)
    with pytest.raises(SystemExit) as raised:
        main(argv)
    assert raised.value.code == 2
    message = capsys.readouterr().err
    assert option in message
    assert example in message


def test_bare_recipe_before_next_option_explains_value(capsys):
    with pytest.raises(SystemExit) as raised:
        create_main_parser().parse_args([
            "embeddings", "--analysis-only", "--analysis-source", "unused.csv",
            "--declared-space", "--output", "unused-output",
        ])
    assert raised.value.code == 2
    message = capsys.readouterr().err
    assert "quoted recipe label" in message
    assert "CLUSTERING" in message


def test_blueprint_syntax_error_does_not_get_diagnostic_hint(capsys):
    with pytest.raises(SystemExit):
        create_main_parser().parse_args(["blueprint", "--output"])
    assert "diagnostic-01" not in capsys.readouterr().err


def test_help_explains_values_legacy_and_limits(capsys):
    with pytest.raises(SystemExit) as raised:
        create_main_parser().parse_args(["embeddings", "--help"])
    assert raised.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    for expected in ["--declared-space LABEL", "--analysis-source CSV", "--output DIRECTORY",
                     "CLUSTERING", "expected-input manifest", "no value", "hard ceiling 500",
                     "16 MiB", "does not select first N", "Analysis-only example",
                     "docs/analysis-only.md"]:
        assert expected in help_text


@pytest.mark.parametrize("kind", ["bytes", "records"])
def test_source_refusal_names_ceiling_and_subset_recipe(tmp_path, kind):
    path = tmp_path / "synthetic.csv"
    path.write_text('uuid,text,embedding\n001,one,"[1,0]"\n002,two,"[1,0]"\n')
    limits = effective_limits({"max_source_bytes": 10} if kind == "bytes" else {"max_records": 1})
    with pytest.raises(EmbeddingInputError) as raised:
        read_source(path, limits)
    message = str(raised.value)
    assert "16 MiB (16777216 bytes) and 500 records" in message
    assert "--max-records does not truncate" in message
    assert "docs/analysis-only.md" in message
    assert ("Source size" if kind == "bytes" else "at record 2") in message


def test_recognized_metadata_is_recorded_and_unrelated_columns_are_ignored(tmp_path):
    path = tmp_path / "synthetic.csv"
    path.write_text(
        'uuid,text,embedding,model_name,provider,task_type,extra\n'
        '001,one,"[1,0]",synthetic-model,synthetic-provider,synthetic-task,a\n'
        '002,two,"[1,0]",synthetic-model,synthetic-provider,synthetic-task,b\n'
    )
    documents, source = read_source(path, effective_limits({}))
    assert source["reported_space"]["model_name"] == "synthetic-model"
    assert source["reported_space"]["provider"] == "synthetic-provider"
    assert source["reported_space"]["task_type"] == "synthetic-task"
    assert all("extra" not in document for document in documents)
    assert "extra" not in source["reported_space"]


def test_documented_subset_recipe_preserves_complete_records_and_refuses_overwrite(tmp_path):
    guide = (ROOT / "docs" / "analysis-only.md").read_text(encoding="utf-8")
    recipe = guide.split("```python\n", 1)[1].split("```", 1)[0]
    script = tmp_path / "make_subset.py"
    script.write_text(recipe, encoding="utf-8")
    source, target = tmp_path / "source.csv", tmp_path / "subset.csv"
    rows = [[f"{index:03}", 'synthetic, "quoted"\nmultiline', "[1,0]", "synthetic-model"]
            for index in range(12)]
    with source.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["uuid", "text", "embedding", "model_name"])
        writer.writerows(rows)
    original = source.read_bytes()
    command = [sys.executable, str(script), str(source), str(target)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "Copied 10 records" in result.stdout
    assert "synthetic-model" not in result.stdout
    with target.open(encoding="utf-8", newline="") as stream:
        copied = list(csv.reader(stream))
    assert copied[1:] == rows[:10]
    assert source.read_bytes() == original
    target_before = target.read_bytes()
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert target.read_bytes() == target_before
