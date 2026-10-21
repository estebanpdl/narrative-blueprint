"""Exercise the synthetic quick start and command-reference examples offline."""

import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

from narrative_blueprint.cli.parser import create_main_parser

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def test_quick_start_creates_documented_diagnostic(tmp_path):
    guide = (DOCS / "quick-start.md").read_text(encoding="utf-8")
    snippet = guide.split("```python\n", 1)[1].split("```", 1)[0]
    script = tmp_path / "make_vectors.py"
    script.write_text(snippet, encoding="utf-8")
    subprocess.run([sys.executable, str(script)], cwd=tmp_path, check=True, timeout=30)
    result = subprocess.run([
        sys.executable, str(ROOT / "tests/offline_cli.py"), "embeddings", "analyze",
        "--source", "vectors.csv", "--allow-legacy-source", "--analysis-dir", "diagnostic-new",
    ], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    status = json.loads((tmp_path / "diagnostic-new/diagnostic-status.json").read_text())
    assert status["status"] == "diagnostic_complete"
    assert status["declared_space"] is None
    assert status["counts"]["selected_occurrences"] == 4
    assert status["counts"]["unique_texts"] == 3
    assert status["counts"]["legacy_communities"] == 1
    assert status["counts"]["legacy_represented_unique_texts"] == 2


def test_command_reference_examples_parse_without_execution():
    parser = create_main_parser()
    count = 0
    for filename in ("blueprint.md", "embeddings-compute.md", "embeddings-analyze.md"):
        text = (DOCS / filename).read_text(encoding="utf-8")
        for block in re.findall(r"```bash\n(.*?)```", text, re.S):
            for line in block.splitlines():
                words = shlex.split(line)
                prefix = 1 if words[0] == "nblue" else 2
                parser.parse_args(words[prefix:])
                count += 1
    assert count == 8


def test_local_document_links_resolve():
    for source in [ROOT / "README.md", *DOCS.glob("*.md")]:
        text = source.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if "://" in target or target.startswith("#"):
                continue
            relative, _, anchor = target.partition("#")
            resolved = source.parent / relative
            assert resolved.is_file(), (source.name, target)
            if anchor and resolved.suffix == ".md":
                headings = re.findall(r"^#+ (.+)$", resolved.read_text(encoding="utf-8"), re.M)
                slugs = [re.sub(r"[^\w -]", "", h.lower()).replace(" ", "-") for h in headings]
                assert anchor in slugs, (source.name, target)
