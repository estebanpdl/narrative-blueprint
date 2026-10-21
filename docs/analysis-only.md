# Analysis-only diagnostic

Use `nblue embeddings analyze` to inspect a **small CSV of existing vectors**
without generating embeddings, loading credentials, or contacting a provider.
It validates the selected input, runs the uncorrected legacy similarity graph,
and writes explicitly labelled diagnostic JSON files. No API keys, `.env`, or
MongoDB setup are needed for this mode; the Python dependencies must be installed.

This is not scalable full-corpus analysis. The legacy graph collapses exact
duplicate texts and drops isolates. Its batch filtering is uncorrected and
bridge edges can affect more than one community's statistics. The diagnostic's
500-record ceiling prevents crossing the legacy 1,000-record batch boundary;
it does not validate the algorithm on larger inputs. Results do not establish
narrative validity, coordination, intent, or population prevalence.

## Quick start with synthetic vectors

Run from the repository root, using its Python environment:

```bash
python main.py embeddings --analysis-only --analysis-source tests/fixtures/diagnostic/vectors.csv --declared-space "synthetic/fixture-v1" --allow-legacy-source --output results/diagnostic-example
```

The tracked fixture contains four occurrences, three exact unique texts, and
three-dimensional synthetic vectors. Expect one legacy community representing
two unique texts, and `Output status: diagnostic_complete`. The duplicate
occurrences remain in `selection.json`; the isolated text has no community.
Use a new output directory on each run, including when retrying failed work.

## Provenance note and required acknowledgement

`--declared-space` is optional and takes a **value**, not just a switch. A recipe describes how
the vectors were generated: provider/model, task type, dimension, model revision,
and preprocessing where known. For example:

```text
--declared-space "gemini-embedding-001 / CLUSTERING / original text"
```

Use a label that describes your actual common recipe. Do not copy the example
as a claim about unrelated vectors. Keep unknown details explicit, for example
`"imported sample / model and task reported in CSV / preprocessing unknown"`.
The label is free text recorded in `declared_space`; it neither configures a
provider nor verifies provenance. Matching labels and dimensions alone do not
prove that vectors belong to a compatible embedding space.
When omitted, `declared_space` is null; an explicitly blank value is refused.
The note does not affect scores, communities or source metadata checks.

`--allow-legacy-source` is a switch with **no value**. Here, "legacy" means a
CSV without an expected-input manifest or generation ledger. Even a CSV with
model/provider/task columns cannot establish whether original generation
completed or which inputs are missing. The switch acknowledges that unknown
coverage and unverified provenance. It is required on every diagnostic run.

## Flag reference

The following options apply to analysis-only. None of the limits select or
truncate data: exceeding one refuses the whole diagnostic before graph/output.

| Flag | Value and meaning | Default | Ceiling or constraint |
|---|---|---|---|
| `--analysis-only` | Legacy flat switch; use `embeddings analyze` instead | Off | Compatibility syntax only |
| `--source CSV` (alias `--analysis-source`) | Local UTF-8 CSV path | None | Required; CSV only |
| `--declared-space LABEL` | Quoted recipe note | null | Optional; nonblank when supplied; unverified |
| `--allow-legacy-source` | Acknowledge unknown coverage/provenance | Off | Required; takes no value |
| `--analysis-dir DIRECTORY` (aliases `-o`, `--output`) | Directory for diagnostic JSON | None | Required; must not already exist |
| `--threshold SCORE` | Keep cosine scores greater than or equal to this value | 0.75 | Finite; `0 < SCORE <= 1` |
| `--max-records N` | CSV data records | 100 | 500 |
| `--max-dimension N` | Numbers in each vector | 3072 | 16384 |
| `--max-source-bytes BYTES` | Size of the entire source file | 4194304 (4 MiB) | 16777216 (16 MiB) |
| `--max-pairs N` | Possible pairs before threshold filtering | 4950 | 124750 |
| `--max-working-bytes BYTES` | Estimated working memory | 67108864 (64 MiB) | 268435456 (256 MiB) |
| `-h, --help` | Print command help and exit | Off | No analysis |

All five resource limits are positive integers. All must pass together; raising
the row limit alone does not raise pair or memory limits. For `N` records and
dimension `d`, possible pairs are `N*(N-1)/2`. The working-byte admission estimate
is `16*source_bytes + 128*N*d + 32*N*N + 8192*possible_pairs`. It is not an enforced
process RSS or execution-time ceiling. Raising the threshold does not reduce
the admission estimate. A file below 16 MiB with fewer than 500 records may
still be refused by the other limits.

Generation flags conflict with analysis-only: `--narrative-path`, `--model`,
`--gemini-task-type`, `--embeddings-output` (alias `--embedding-output`),
`--mongo-db-name`, `--mongo-collection-name`, and `--skip-analysis`.
`--output` is the analysis directory; `--embeddings-output` is a destination
for newly generated vectors and is not used here.

## Input CSV

Required header names are exactly `uuid,text,embedding` (column order may vary).
The encoding is UTF-8, optionally with a BOM. Use normal CSV quoting for commas,
quotes, and multiline text; vectors are JSON numeric arrays inside CSV cells:

```csv
uuid,text,embedding
001,Synthetic example A,"[1.0, 0.0, 0.0]"
002,Synthetic example B,"[0.9, 0.1, 0.0]"
003,Synthetic isolated example,"[0.0, 0.0, 1.0]"
```

- `uuid` and `text` must be nonblank. UUIDs remain strings, including leading
  zeros. Repeated UUIDs refuse the input; distinct UUIDs with identical text
  remain distinct selected occurrences. Resolve retries versus occurrences
  explicitly before import.
- Every vector must be a nonempty, finite, numeric, nonzero JSON array of the
  same dimension. Booleans, strings, nested arrays, NaN and infinity are invalid.
  The legacy numeric path also requires a norm between `1e-100` and `1e100`.
- `model_name`, `provider`, `task_type`, `model_revision`, and `preprocessing`
  are **accepted and checked**, not ignored. Each must contain one consistent
  value across the selected rows or be missing throughout. Mixed values or
  partial missingness refuse the input. They are recorded in
  `diagnostic-status.json` under `source.reported_space`; absent fields are null.
- Other named columns are ignored by the analysis. Duplicate headers and
  inconsistent row widths are refused. A header-only CSV is valid and completes
  with zero selected occurrences and communities.

## Try a larger CSV using a small subset

A roughly 99 MB file exceeds even the 16 MiB hard ceiling. The diagnostic
cannot analyze it directly or stream the first few rows through `--max-records`.
First create a separate small CSV, then pass that file to `--analysis-source`.
Start with 10 records and the default limits. This is an ordered convenience
subset, not random sampling or a representative estimate of the corpus.

Save this standalone Python snippet as `make_subset.py`. It copies the header
and at most 10 complete CSV records, preserving metadata columns and quoted
multiline fields. It does not modify the original or print its values. The
destination must not already exist. It is a copy recipe, not input validation.

```python
import csv
import sys
from itertools import islice
from pathlib import Path

source, destination = map(Path, sys.argv[1:])
csv.field_size_limit(16 * 1024**2)
with source.open(encoding="utf-8-sig", newline="") as src:
    reader = csv.reader(src, strict=True)
    header = next(reader)
    with destination.open("x", encoding="utf-8", newline="") as dst:
        writer = csv.writer(dst)
        writer.writerow(header)
        count = 0
        for row in islice(reader, 10):
            writer.writerow(row)
            count += 1
print(f"Copied {count} records; {destination.stat().st_size} bytes")
```

```bash
python make_subset.py data/embeddings.csv data/embeddings-first10.csv
python main.py embeddings --analysis-only --analysis-source data/embeddings-first10.csv --declared-space "imported sample / model and task reported in CSV / preprocessing unknown" --allow-legacy-source --output results/diagnostic-first10
```

Review what you know about the generation recipe before using that declaration.
The destination's parent directory must exist. If copying fails, the destination
may be incomplete: discard that copy or choose a new path before retrying.
Do not use a physical-line utility such as `head` for CSV with multiline fields.
The new file has its own fingerprint and row ordinals; it does not preserve the
full source's snapshot identity or establish full generation coverage.

If the subset exceeds a default limit, inspect the named limit and reduce the
subset further or explicitly raise that limit within its ceiling. If an
individual vector exceeds 3072 dimensions, for example, increase
`--max-dimension` only to its known dimension, at most 16384. Invalid vectors or
mixed recipes need source correction or explicit compatible selection, not
higher limits. Full-source scalable analysis is not provided by this diagnostic.

## Read the outputs

| File | How to read it |
|---|---|
| `selection.json` | Every admitted occurrence, original UUID, one-based CSV data-record ordinal, exact text, occurrence ID and exact-text hash. Vectors remain in the source file. This file contains source text and identifiers. |
| `legacy-communities.json` | Run-local legacy community indices, unique-text membership hashes, legacy sizes, incident-edge counts and mean similarities. Join text hashes to selection; one hash can identify multiple occurrences. Isolates are absent. Bridge statistics are uncorrected. |
| `diagnostic-status.json` | Completion state, method/schema version, source fingerprint, reported metadata, declared recipe, limits, parameters, library versions, counts, warnings, and checksums for the other two files. |

Check `status == "diagnostic_complete"` before interpreting output. This only
means the labelled diagnostic finished. `corrected_analysis_complete` and
`provenance_verified` remain false, `generation_completeness` stays `"unknown"`,
and missing/generation-failed counts stay null. Empty, singleton, and no-edge
sources can complete with zero communities. Community membership is not a
complete occurrence assignment.

On graph/export failure, status is `failed` if it can be written. Interruptions
or write failures may leave no status file; such a directory is incomplete.
Argument/input refusals exit with code 2 before creating a diagnostic directory.
Runtime failures remain runtime errors. Choose a new output directory for retries.
No corrected `manifest.json`, Excel, or projector output is created in this mode.

See the [stored-vector contract](embedding-analysis-contract.md) for exact identity
rules and the separate, unimplemented corrected-analysis specification.
