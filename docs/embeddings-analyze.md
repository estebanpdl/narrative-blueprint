# nblue embeddings analyze

Read one small local UTF-8 CSV of existing vectors and produce diagnostic JSON.
No provider, credential loader or Mongo connection is used. The graph remains
the uncorrected legacy algorithm; [limitations and outputs](analysis-only.md)
must accompany interpretation.

| Group | Option | Default / constraint |
|---|---|---|
| Input | `--source CSV` (alias `--analysis-source`) | Required; columns `uuid`, `text`, `embedding` |
| Analysis output | `--analysis-dir DIRECTORY` (aliases `-o`, `--output`) | Required new directory |
| Analysis output | `--threshold SCORE` | `0.75`; finite and in `(0,1]` |
| Provenance | `--declared-space LABEL` | Optional unverified note; absent becomes null; explicit blank is refused |
| Provenance | `--allow-legacy-source` | Required switch, no value; acknowledge unknown completeness/provenance |
| Limits | `--max-records N` | 100, hard ceiling 500 |
| Limits | `--max-dimension N` | 3072, hard ceiling 16384 |
| Limits | `--max-source-bytes BYTES` | 4194304 (4 MiB), hard ceiling 16777216 (16 MiB) |
| Limits | `--max-pairs N` | 4950, hard ceiling 124750 |
| Limits | `--max-working-bytes BYTES` | 67108864 (64 MiB), hard ceiling 268435456 (256 MiB); estimated, not an RSS cap |
| Help | `-h`, `--help` | No analysis |

All limits are positive integers and refuse excess rather than truncate. The
source must pass them all. The [CSV subset recipe](analysis-only.md#try-a-larger-csv-using-a-small-subset)
helps create a separate smaller source. The optional label does not change
scores or metadata validation. Consistently reported provider/model/task fields
remain separate from the label; conflicting or partially missing fields refuse
the source. Missing metadata and original generation completeness stay unknown.

From a checkout with dependencies, the tracked synthetic fixture works with
either spelling (choose a fresh output path):

```bash
python main.py embeddings analyze --source tests/fixtures/diagnostic/vectors.csv --allow-legacy-source --analysis-dir results/new-example
python main.py embeddings --analysis-only --analysis-source tests/fixtures/diagnostic/vectors.csv --allow-legacy-source --output results/old-example
```

Use `nblue` in place of `python main.py` after installation. Generation input,
provider selection, vector destination, Mongo names and `--skip-analysis` are
rejected in analyze. The legacy `--analysis-only` switch belongs to flat
compatibility syntax; do not combine it with explicit compute/analyze modes.
