# CLI compatibility

All entry points share the dispatcher: installed `nblue`, installed
`python -m narrative_blueprint`, and clone `python main.py`. The clone launcher
remains supported. Old flat commands and option aliases are supported throughout
0.x and 1.x; removal is no earlier than 2.0.0 and must be announced in release notes.

| Old command or spelling | Canonical form |
|---|---|
| `embeddings ...` | `embeddings compute ...` |
| `embeddings --analysis-only ...` | `embeddings analyze ...` |
| `embeddings --skip-analysis ...` | `embeddings compute --skip-analysis ...` |
| `blueprint --narrative-path FILE` | `blueprint --input FILE` |
| `blueprint --output JSON` | `blueprint --result-file JSON` |
| Embeddings `--narrative-path FILE` | Compute `--input FILE` |
| `--embeddings-output FILE` or `--embedding-output FILE` | Compute `--vectors-file FILE` |
| Embeddings `-o DIRECTORY` or `--output DIRECTORY` | `--analysis-dir DIRECTORY` |
| `--analysis-source CSV` | Analyze `--source CSV` |

Aliases are available on explicit subcommands too. Equal duplicate parsed
values are accepted; unequal values for the same aliased destination are
refused before provider/storage/output setup. Equality is literal string
equality for paths, not filesystem resolution. Deprecated-option notices and
alias-conflict errors contain option names, not their supplied values. Other
syntax/input errors can identify the offending input. Long option abbreviations
are not accepted; use the documented full spelling.

Compute still defaults to compute-plus-analysis; `--skip-analysis` still means
compute/store only. Blueprint local-file precedence over Mongo options remains.
Vector-file/Mongo conflicts, incomplete destinations and invalid mode mixtures
are refused. Analysis-specific flags do not configure generation.

`--declared-space` is now optional on both old and new diagnostic syntax. An
absent note is null, an explicit blank is refused, and supplied text remains
unverified. It does not override source metadata or change computation. The
required `--allow-legacy-source` acknowledgement and metadata consistency checks
remain. This CSV diagnostic does not derive a structured recipe or verify
provenance. The separate [snapshot route](snapshot-validation.md) derives reported
recipe metadata and validates generation receipts; it still cannot establish
unknown legacy generation coverage.

Python imports now live under `narrative_blueprint`, for example
`narrative_blueprint.analysis` and `narrative_blueprint.databases`. Generic
top-level packages such as `analysis` or `models` are not installed or retained
as import aliases. The command compatibility window does not apply to those
old internal import paths. `NarrativeBlueprint` remains lazily importable from
the package root. Model defaults now come from packaged resources rather than
an invocation-directory `config/model_limits.json`; explicit prompt files and
the existing invocation-relative generation `.env` behavior remain separate.
