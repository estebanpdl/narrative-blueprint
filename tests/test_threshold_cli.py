"""Corrected analysis dispatch, rejection and executable offline examples."""

import json
from pathlib import Path
import shlex
import subprocess
import sys

import pytest

from narrative_blueprint.cli.main import main
from test_threshold_graph import make_snapshot


def test_cli_corrected_snapshot_route(tmp_path):
    snapshot = make_snapshot(tmp_path / "input", [[1, 0], [1, 0]])
    main(["embeddings", "analyze", "--snapshot-dir", str(snapshot), "--analysis-dir", str(tmp_path / "out"), "--max-tile-rows", "1"])
    marker = next((tmp_path / "out").rglob("manifest.json"))
    assert json.loads(marker.read_text())["counts"]["edges"] == 1


@pytest.mark.parametrize("options", [["--source", "unused.csv"], ["--allow-legacy-source"], ["--declared-space", "note"],
    ["--max-nodes", "0"], ["--tolerance", "1"], ["--resolution", "0"], ["--max-seconds", "nan"],
    ["--model", "text-embedding-3-small"], ["--max-pairs", "100"]])
def test_conflicts_refuse_before_creating_output(tmp_path, options):
    with pytest.raises(SystemExit) as exc:
        main(["embeddings", "analyze", "--snapshot-dir", "unused", "--analysis-dir", str(tmp_path / "out"), *options])
    assert exc.value.code == 2 and not (tmp_path / "out").exists()


def test_graph_options_do_not_silently_apply_to_legacy_diagnostic(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["embeddings", "analyze", "--source", "unused.csv", "--allow-legacy-source", "--analysis-dir", str(tmp_path / "out"), "--seed", "3"])
    assert exc.value.code == 2 and not (tmp_path / "out").exists()


def test_documented_full_commands_in_fresh_guarded_processes(tmp_path):
    root = Path(__file__).resolve().parents[1]
    guide = (root / "docs/global-similarity.md").read_text(encoding="utf-8")
    commands = guide.split("```bash\n", 1)[1].split("```", 1)[0].strip().splitlines()
    for index, line in enumerate(commands):
        command = shlex.split(line)
        command[command.index("--snapshot-dir") + 1] = str(tmp_path / "snapshot")
        if "--source" in command:
            command[command.index("--source") + 1] = str(root / command[command.index("--source") + 1])
        if "--analysis-dir" in command:
            command[command.index("--analysis-dir") + 1] = str(tmp_path / "analysis")
        completed = subprocess.run([sys.executable, str(root / "tests/offline_cli.py"), *command[2:]],
                                   cwd=tmp_path, capture_output=True, text=True, timeout=90)
        assert completed.returncode == 0, completed.stderr
    marker = next((tmp_path / "analysis").rglob("manifest.json"))
    result = json.loads(marker.read_text())
    assert result["counts"]["analyzed"] == 4 and result["counts"]["edges"] == 3
    assert result["counts"]["communities"] == 2 and result["counts"]["isolates"] == 1
