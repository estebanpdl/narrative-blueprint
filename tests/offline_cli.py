"""Run the real CLI in a fresh process with offline tripwires installed."""

import builtins
from pathlib import Path
import sys

import pytest

from offline_guard import install_guard


def run():
    patch = pytest.MonkeyPatch()
    install_guard(patch)
    original_import = builtins.__import__
    blocked = ("openai", "google.genai", "dotenv", "models",
               "embeddings.openai_embeddings", "embeddings.gemini_embeddings",
               "databases.mongo", "runners.blueprint_runner")

    def guarded_import(name, *args, **kwargs):
        if any(name == item or name.startswith(item + ".") for item in blocked):
            raise AssertionError(f"Offline CLI imported forbidden module: {name}")
        return original_import(name, *args, **kwargs)

    patch.setattr(builtins, "__import__", guarded_import)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from main import main
    main(sys.argv[1:])


if __name__ == "__main__":
    run()
