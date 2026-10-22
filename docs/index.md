# Narrative Blueprint documentation

Start with the [quick start](quick-start.md) for installation and a synthetic,
provider-free diagnostic. `nblue` and `python -m narrative_blueprint` use the same
dispatcher. An uninstalled source checkout supports `python main.py` after its
dependencies are installed.

| Task | Reference |
|---|---|
| Generate structured blueprints using a prompt and provider | [blueprint](blueprint.md) |
| Generate/store vectors, optionally followed by legacy analysis | [embeddings compute](embeddings-compute.md) |
| Diagnose a small CSV of existing vectors without a provider | [embeddings analyze](embeddings-analyze.md) |
| Validate CSV/Parquet/SQLite vectors and generation coverage | [snapshot validation](snapshot-validation.md) |
| Migrate scripts and understand alias conflicts | [CLI compatibility](cli-compatibility.md) |
| Understand diagnostic inputs, outputs, limits and CSV subsetting | [Analysis-only guide](analysis-only.md) |
| Inspect exact identities and implemented versus specified behavior | [Stored-vector contract](embedding-analysis-contract.md) |

Root help: `nblue --help`. Embeddings overview: `nblue embeddings --help`.
Each command accepts `-h/--help`. Help and package import do not load credentials
or construct providers. Blueprint generation and embedding computation are
independent operations; neither calls the other.

The diagnostic still uses the uncorrected legacy graph. Disk-backed snapshot
validation is separate. Corrected occurrence graphs, auth commands and provider
budgets are not shipped.
