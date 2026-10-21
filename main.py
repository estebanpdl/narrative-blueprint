"""Source-checkout launcher for the shared CLI."""

from pathlib import Path
import sys

# Prefer this checkout even if another version is installed.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from narrative_blueprint.cli.main import main

if __name__ == "__main__":
    main(prog="python main.py")
