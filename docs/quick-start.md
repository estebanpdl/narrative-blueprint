# Quick start

## Install from a checkout

The package declares Python `>=3.14,<3.15`. Use Python 3.14; other runtime
series are outside this package's declared compatibility range.

In your chosen Python 3.14 environment, from the checkout root:

```bash
python -m pip install .
nblue --help
python -m narrative_blueprint --help
```

For development, use `python -m pip install -e .`. These commands install from
local source; they do not imply a published PyPI release. To use an uninstalled
clone, install `requirements.txt` and run `python main.py --help`. The thin clone
launcher prepends that checkout's `src` directory, then calls the shared dispatcher.

Runtime code lives only in `src/narrative_blueprint/`. Model defaults are packaged
resources and do not depend on the current directory. Explicit input, template
and output paths remain relative to the invocation directory. Legacy generation
credentials still come from environment variables and invocation-relative
`config/.env`. Per-user credential storage and auth commands are not provided.
Help and offline diagnostics do not read that file. Prompt templates are explicit
user files; the checkout's `prompt_examples/` supplies examples, not a hidden default.

## Try a provider-free diagnostic

Create `vectors.csv` in an empty working directory with this Python snippet
(save as `make_vectors.py`, then run `python make_vectors.py`):

```python
import csv

with open("vectors.csv", "x", encoding="utf-8", newline="") as stream:
    writer = csv.writer(stream)
    writer.writerow(["uuid", "text", "embedding"])
    writer.writerows([
        ["001", "Synthetic example A", "[1,0,0]"],
        ["002", "Synthetic example A", "[1,0,0]"],
        ["003", "Synthetic example B", "[0.9,0.1,0]"],
        ["004", "Synthetic isolated example", "[0,0,1]"],
    ])
```

Run either installed entry point, using a new output directory each time:

```bash
nblue embeddings analyze --source vectors.csv --allow-legacy-source --analysis-dir diagnostic-new
python -m narrative_blueprint embeddings analyze --source vectors.csv --allow-legacy-source --analysis-dir diagnostic-module
```

No key or provider is needed. Expect four selected occurrences, three unique
texts and one legacy community representing two unique texts. The output directory
contains `selection.json`, `legacy-communities.json` and `diagnostic-status.json`.
Success is `status: diagnostic_complete`; it does not mean corrected analysis or
verified provenance. `declared_space` is null because no note was supplied.

Equivalent old syntax remains supported (from a clone root, adjust the source path):

```bash
python main.py embeddings --analysis-only --analysis-source vectors.csv --allow-legacy-source --output diagnostic-old
```

Old aliases print migration notices with option names only. The optional
`--declared-space "synthetic / three dimensions"` records a note; it changes no
scores or memberships. Never use a label to override mixed source metadata.

Read the [diagnostic guide](analysis-only.md) before using your own vectors,
especially its size ceilings, source identity rules and legacy graph limitations.
