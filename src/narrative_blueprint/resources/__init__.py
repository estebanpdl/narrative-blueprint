"""Read immutable packaged defaults independently of the working directory."""

from importlib.resources import files
import json


def load_model_limits():
    return json.loads(files(__package__).joinpath("model_limits.json").read_text(encoding="utf-8"))
