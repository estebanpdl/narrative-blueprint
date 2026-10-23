# Narrative Blueprint documentation

Start with the [quick start](quick-start.md) for installation and a synthetic,
provider-free diagnostic. `nblue` and `python -m narrative_blueprint` use the same
dispatcher. An uninstalled source checkout supports `python main.py` after its
dependencies are installed.

| Task | Reference |
|---|---|
| Reproduce the local workflow and review delivered scope and deferrals | [Local workflow scope](local-workflow.md) |
| Generate structured blueprints using a prompt and provider | [blueprint](blueprint.md) |
| Generate/store vectors, optionally followed by legacy analysis | [embeddings compute](embeddings-compute.md) |
| Diagnose a small CSV of existing vectors without a provider | [embeddings analyze](embeddings-analyze.md) |
| Validate CSV/Parquet/SQLite vectors and generation coverage | [snapshot validation](snapshot-validation.md) |
| Analyze all valid occurrences with corrected global threshold edges | [Global similarity](global-similarity.md) |
| Read assignments, communities, bridges and optional views | [Analysis outputs](analysis-outputs.md) |
| Configure graph admission and interpret refusals | [Analysis limits](analysis-limits.md) |
| Inspect full-path measurements and the exact-kNN comparison | [Qualification](qualification.md) |
| Migrate scripts and understand alias conflicts | [CLI compatibility](cli-compatibility.md) |
| Understand diagnostic inputs, outputs, limits and CSV subsetting | [Analysis-only guide](analysis-only.md) |
| Inspect exact identities and implemented versus specified behavior | [Stored-vector contract](embedding-analysis-contract.md) |

Root help: `nblue --help`. Embeddings overview: `nblue embeddings --help`.
Each command accepts `-h/--help`. Help and package import do not load credentials
or construct providers. Blueprint generation and embedding computation are
independent operations; neither calls the other.

The small CSV compatibility diagnostic and combined compute analysis still use
the legacy graph. The separate snapshot analysis route supplies corrected global
occurrence graphs and complete CSV publication. Auth commands, paid provider
budgets and qualification on additional machines remain separate work.
