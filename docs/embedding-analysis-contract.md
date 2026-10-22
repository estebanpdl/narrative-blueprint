# Stored-vector analysis contract

Contract version: `occurrence-threshold-1`.

This contract separates the implemented small-input diagnostic adapter from
the corrected analysis format specified below. The corrected graph, immutable
disk-backed snapshot, generation ledger and complete CSV publication are not
implemented by the diagnostic command. The separate
[snapshot operation](snapshot-validation.md) now implements disk-backed validation
and a generation receipt with its own versioned identity/selection schema.
Corrected graphs and graph-table publication remain specified below.

## Implemented diagnostic entry

```text
python main.py embeddings --analysis-only --analysis-source vectors.csv --declared-space example/recipe-v1 --allow-legacy-source --output new-diagnostic-directory
```

Analysis-only reads one explicitly selected local UTF-8 CSV, in source row
order, with `uuid`, `text` and JSON-array `embedding` columns. CSV is the only
diagnostic source format. MongoDB, SQLite, Parquet and generation input formats
are not sources for this adapter. No provider module, provider constructor,
credential loader, `.env` file or network connection is needed. Existing
compute-plus-analysis and `--skip-analysis` compute-only behavior remain
available, with the same storage formats and default model. Compute now requires
a complete outcome receipt before downstream work and selects the current
generation. Those paths retain their existing graph resource/correctness limitations.

Generation options (`--input`/`--narrative-path`, `--model`, `--gemini-task-type`,
`--vectors-file`/`--embeddings-output`, MongoDB options and `--skip-analysis`)
conflict with `embeddings analyze` or legacy `--analysis-only`, even when an
explicitly supplied model equals the compute default. Diagnostic-only options
belong to analyze (or legacy `--analysis-only`) and fail on compute.
`--threshold` must be finite and in `(0, 1]`.

Every source UUID is a nonempty string, including leading zeros; no numeric
conversion, trimming or Unicode normalization is applied. Each CSV record is a
selected occurrence. Repeated UUIDs are rejected, including identical repeated
rows: without an occurrence/attempt ledger they cannot be distinguished from
retries. Resolve these collisions explicitly before import; do not silently
turn a retry into a new occurrence. Distinct UUIDs with identical exact text
remain distinct selected occurrences.

The source SHA-256 covers the exact file bytes. A deterministic occurrence ID
is SHA-256 of the UTF-8 JSON array `[source_sha256, record_ordinal, source_uuid]`
serialized with Python's default JSON separators and `ensure_ascii=False`.
The ordinal is one-based and counts CSV data records, not physical lines.
The duplicate-group reference is SHA-256 of the unmodified UTF-8 text.
Byte-identical reruns preserve IDs; changing or reordering the selected source
creates a new snapshot identity. These IDs do not assert cross-source identity.

All vectors must be nonempty numeric arrays of one dimension, finite and
nonzero. Booleans, strings and nested arrays are not numbers for this contract.
The compatibility adapter additionally refuses norms outside `[1e-100, 1e100]`
to avoid legacy float64 underflow/overflow. Invalid records refuse the whole
diagnostic; there is no silent exclusion or partial success.

Optional reported provenance columns are `provider`, `model_name`,
`model_revision`, `task_type` and `preprocessing`. Each must be consistently
present with the same value, or absent throughout; mixed or partially missing
values refuse the source. Missing metadata remains null. Matching dimensions
and matching reported labels cannot verify an embedding space.
`--declared-space` optionally records the user's unverified recipe note without
replacing reported metadata, changing computation or marking provenance verified.
When absent, `declared_space` is null; an explicitly blank value is refused.
Both `nblue embeddings analyze` and legacy flat syntax use this same policy.

Legacy CSV has no expected-input manifest. `--allow-legacy-source` explicitly
accepts unknown original generation completeness and provenance. Available
rows never imply successful full generation. There is no implicit selection
from a previous generation destination, and no provider activity to fill gaps.
CSV containing `generation_id` is refused by this diagnostic: use the snapshot
command with its generation receipt to validate known coverage instead.

## Diagnostic admission and outputs

| Option | Default | Hard ceiling |
|---|---:|---:|
| `--max-records` | 100 | 500 |
| `--max-dimension` | 3072 | 16384 |
| `--max-source-bytes` | 4194304 | 16777216 |
| `--max-pairs` | 4950 | 124750 |
| `--max-working-bytes` | 67108864 | 268435456 |

All limits are positive integers. Callers can lower them or raise them only
within these diagnostic ceilings. The bounded source read checks file size and
reads at most the byte limit plus one before decoding. Record and dimension
limits are checked while decoding the capped source; pair and work estimates
are checked before graph construction. Admission assumes all `N*(N-1)/2` pairs
may be retained, regardless of the requested threshold. It never raises a
threshold, truncates a graph, or changes methods to make an input fit.

The working estimate in bytes is
`16*source_bytes + 128*N*d + 32*N*N + 8192*possible_pairs`. It reserves space
for decoded data, vector/matrix copies and two legacy graph passes. It is a
conservative admission model, **not a measured or enforced RSS ceiling**; library
imports, allocator/BLAS behavior and execution time remain machine dependent.
The source is materialized within its byte cap. This adapter is not a scalable
reader, a process sandbox, or the bounded snapshot pipeline. Larger workloads
must be refused rather than treated as qualified.

The legacy two-pass implementation uses float64 sklearn cosine, `score >=
threshold` without tolerance, and NetworkX weighted Louvain with seed 42 and
resolution 1. The diagnostic preserves its filtering, duplicate-text collapse,
isolate loss and incident-edge statistics. The 500-record ceiling prevents
cross-batch inputs (the legacy batch size is 1000); this does not establish
correct behavior across batches. Empty, singleton and no-edge sources finish
with empty community results.

A new output directory is required; prior directories are never overwritten.
Only these outputs are implemented:

| File | Meaning |
|---|---|
| `selection.json` | Every admitted occurrence, source UUID, row, exact text, occurrence ID and text hash. Vectors remain in the fingerprinted source. |
| `legacy-communities.json` | Legacy community indices, size, text hashes, incident-edge count and mean. Text hashes link groups of occurrences, not complete node assignments. Bridge edges can affect multiple groups and their means. |
| `diagnostic-status.json` | `diagnostic-1` schema, `legacy-two-pass-1` method, source fingerprint and reported/declarative provenance, effective limits, parameters, library versions, selected/unique counts, output checksums and warnings. Written last on success with `status=diagnostic_complete`. |

Missing/generation-failed counts remain null, and generation completeness is
`unknown`. `corrected_analysis_complete` and `provenance_verified` are false.
If graph/export work fails, status is `failed` when it can be written. A crash
or output failure may leave an incomplete directory without a status file.
Neither case is successful. These outputs never include a corrected
`manifest.json`. A zero exit code means the labelled diagnostic completed, not
that full generation or corrected graph analysis succeeded. JSON preserves
Unicode/newlines and literal text without spreadsheet formula evaluation.
Projector and Excel views are intentionally absent from this adapter.

## Corrected occurrence analysis specification

The following behavior is specified for a different method version; it is
**not** claimed by `legacy-two-pass-1`.

- Selection identifies one immutable source snapshot and one embedding recipe
  (provider, model, revision where known, task type, dimension and preprocessing).
  Unknown legacy fields remain unknown and declared-space imports remain
  declarations. Deterministic source-relative IDs and exact-text hashes follow
  the identity rules above. Cross-source merging requires a separate mapping.
- Every valid occurrence is a node, including duplicates and isolates.
  Repeated embedding attempts for one occurrence/recipe do not add nodes.
  Conflicting results refuse selection until resolved by an explicit policy.
- An expected-input ledger records expected/selected, available, stored,
  missing, rejected and failed occurrences and terminal stage states.
  Known incomplete generation refuses downstream analysis by default.
  Explicit partial analysis must retain all exclusions and incomplete coverage.
  Legacy unknown coverage cannot be upgraded to complete.
- Normalize valid vectors to float32 in bounded batches; enumerate all global
  `i < j` pairs exactly once using bounded tiles. A threshold is positive and
  at most one. Retain a computed float32 cosine when `score >= threshold`,
  without epsilon expansion. Compare small-input scores with a float64 oracle
  using absolute tolerance `1e-6`; decisions within `1e-6` of the threshold
  are numeric-boundary cases and must be reported/tested rather than described
  as bitwise-equivalent to float64. No nearest-neighbor substitution is allowed.
- Seeded, weighted NetworkX Louvain uses seed 42 and resolution 1. Record
  package version, ordered IDs and parameters; numeric community labels are
  run-local. Compare memberships using occurrence IDs. Empty/no-edge graphs
  are handled directly. Degree-zero nodes receive `isolated`; nonisolated
  one-node communities receive `singleton`; other members receive `assigned`.
  None of these outcomes means semantic noise or analytical validity.
- Internal edges require both endpoints in the community. Bridges are counted
  separately, once per incident community and once globally in the edge table.
  `mean_internal_edge_similarity` averages retained internal edges only; it is
  null when none exist. Occurrence and exact unique-text counts are separate.
- Resource admission covers read/decode bytes, individual records, normalization,
  score tiles/scratch, graph conversion/Louvain, export/disk and runtime. Limits
  are explicit/configurable across N, dimension and hardware. If one record or
  stage cannot fit, refuse with demand, limit and adjustment guidance. Do not
  silently truncate, change threshold or switch graph algorithms.

## Corrected output and completion specification

| Output | Required fields/semantics |
|---|---|
| `manifest.json` | Schema/method version; source snapshot/recipe and ordered-ID reference; per-stage status; selection, valid, missing, rejected, analyzed and edge counts; parameters/effective limits; timings and output checksums. Separate generation coverage from graph success. |
| `assignments.csv` | Run ID, occurrence ID, source UUID, text/duplicate-group reference, community ID and `assigned`/`singleton`/`isolated`. Exactly one row per analyzed occurrence. |
| `communities.csv` | Community ID, occurrence/unique-text counts, retained internal-edge count/mean and bridge count. |
| `edges.csv` | Endpoint occurrence IDs, cosine, both community IDs and `internal`/`bridge` classification. Each retained pair exactly once. |
| `rejections.csv` | Source identity where available, stage and exclusion/failure reason. Missing/generation-failed inputs remain in the ledger even without a vector. |
| Optional Excel/Projector | Bounded source-linked views with explicit limits, count and truncation/sampling status; never the only complete evidence output. |

Stage output in a new directory. Validate counts, checksums and joins before
publishing a successful completion manifest/pointer last. Individual file
renames do not provide multi-file atomicity. Empty/no-edge success still
publishes current tables. Refused, capped, failed or interrupted work cannot
publish a successful completion marker. Optional-view failure is disclosed
separately and does not invalidate complete core tables. Prior complete runs
remain identifiable by their own manifests.

Stage states are `pending`, `running`, `complete`, `refused`, `failed` and
`interrupted`; coverage is separately `complete`, `partial` or `unknown`.
Only validated core outputs can give a graph stage `complete`, even when
explicitly accepted source coverage is partial or unknown. Generation success
cannot be inferred from that graph-stage state. Missing terminal state after
a crash is incomplete, never implicit success.

Correcting global pair coverage, duplicate occurrences, isolates, assignments
and bridge statistics intentionally changes legacy results. Output schema and
method versions must distinguish them; old workbooks must not be silently
relabeled. Occurrence units remain a revisitable analytical default, not proof
that each row is a distinct narrative. Interpretation, EN/ES evaluation,
claims/frames/stance and any inference of coordination or falsity require
separate methodology and evidence.
