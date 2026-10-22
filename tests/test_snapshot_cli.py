"""Snapshot command dispatch remains local and separate from the graph adapter."""

import json
import sys
from pathlib import Path
import shlex
import subprocess

import pytest

from narrative_blueprint.cli.main import main


def test_snapshot_cli_synthetic_example(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text('uuid,text,embedding,provider,model_name\n001,synthetic,"[3,4]",Fake,fixture\n')
    main(["embeddings", "snapshot", "--source", str(path), "--snapshot-dir", str(tmp_path / "out"), "--allow-legacy-source"])
    result = json.loads((tmp_path / "out/snapshot.json").read_text())
    assert result["counts"]["valid"] == 1


@pytest.mark.parametrize("extra", [["--model", "text-embedding-3-small"], ["--threshold", "0.5"], ["--max-records", "0"], ["--declared-space", " "]])
def test_snapshot_rejects_bad_options_before_output(tmp_path, extra):
    with pytest.raises(SystemExit) as exc:
        main(["embeddings", "snapshot", "--source", "unused.csv", "--snapshot-dir", str(tmp_path / "out"), "--allow-legacy-source", *extra])
    assert exc.value.code == 2 and not (tmp_path / "out").exists()


def test_new_command_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["embeddings", "snapshot", "--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "--generation-ledger" in help_text and "--max-disk-bytes" in help_text


def test_documented_snapshot_runs_with_provider_imports_blocked(tmp_path):
    root = Path(__file__).resolve().parents[1]
    guide = (root / "docs/snapshot-validation.md").read_text(encoding="utf-8")
    command = shlex.split(guide.split("```bash\n", 1)[1].split("```", 1)[0])
    command[command.index("--source") + 1] = str(root / command[command.index("--source") + 1])
    command[command.index("--snapshot-dir") + 1] = str(tmp_path / "out")
    result = subprocess.run([sys.executable, str(root / "tests/offline_cli.py"), *command[2:]],
                            cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    marker = json.loads((tmp_path / "out/snapshot.json").read_text())
    assert marker["counts"]["selected"] == 4 and marker["counts"]["unique_texts"] == 3
