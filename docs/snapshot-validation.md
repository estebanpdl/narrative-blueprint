# Validate stored vectors

`embeddings snapshot` reads a local CSV, Parquet or SQLite store without a
provider, credentials or network. It creates a new directory containing a
normalized vector snapshot and source mappings. It does not compute a graph,
communities, similarity scores or annotations.

From a clone (use `nblue` instead of `python main.py` in an installed environment):

```bash
python main.py embeddings snapshot --source tests/fixtures/diagnostic/vectors.csv --snapshot-dir results/snapshot-01 --allow-legacy-source
```

That fixture is synthetic. Read `snapshot.json` for the counts and coverage;
use a new output directory for each invocation. Existing directories are refused.
The source is opened read-only and never repaired, rewritten or copied.

## What is checked

The source must provide `uuid`, `text` and `embedding`. UUIDs and texts must be
nonempty strings. Leading zeros, whitespace within values, Unicode and newlines
are preserved. CSV is UTF-8 (optional BOM), with JSON-array embeddings and unique
column names. Parquet uses numeric list vectors. SQLite uses the existing
`embeddings` table, including an `id` primary key and JSON-text embeddings.
SQLite must be a quiescent, standalone database: active WAL files are refused.
Checkpoint/close or export a WAL source before validation. Avoid modifying any
source while it is read; size/mtime changes and newly active WAL files refuse
publication. These checks are not a lock against a hostile concurrent writer.

The structured recipe comes from `provider`, `model_name`, `model_revision`,
`task_type` and `preprocessing`, including the SQLite/Parquet JSON `metadata`
extension field. Missing fields stay null. Different values, partially missing
fields, conflicting column/extension values or different dimensions refuse the
selection. Equal dimensions alone do not establish a common space. A supplied
`--declared-space "example recipe note"` is optional and unverified; it cannot
replace or override reported fields. Blank declarations are refused.

Each valid vector must be a nonempty, one-dimensional list of finite numbers,
excluding booleans. Zero vectors are rejected. Normalization scales before
computing the norm, so very large and very small finite inputs need not overflow
or underflow. Stored vectors are little-endian float32 unit vectors; conversion
is lossy. There is no fixed dimension ceiling: vector/record/buffer budgets
determine admission. The snapshot records every selected occurrence, including
invalid/missing ones and separate occurrences with identical text.

## Identity and selection

Without a generation receipt, selection is all source records, ordered by CSV
record order, Parquet row-group/row order or SQLite `id`. A limit is a refusal
threshold, never an implicit sample. Text groups use SHA-256 of exact UTF-8 text.
The source fingerprint hashes the versioned format/field header and
length-prefixed canonical projected records. It is a **logical projection hash**,
not a hash of all physical file bytes. Whitespace in JSON vector cells can change
this hash. Unselected columns are not part of it.

Legacy occurrence IDs hash compact, sorted-key UTF-8 JSON of
`["snapshot-occurrence-1", source_fingerprint, ordinal, source_uuid]`.
Ordinals are one-based data-record positions. Identical reruns preserve IDs;
changing the projection or record order changes them. The older small CSV
diagnostic has its own identity version and is not interchangeable with this one.

Legacy repeated UUIDs refuse as `ambiguous_uuid`: they might be occurrences or
retries. Explicit `occurrence_id` values must be present throughout the selected
source. Distinct occurrence IDs may share a UUID/text. Repeated identical valid
attempts for an explicit occurrence collapse into one selected node, retaining
an attempt count. Changed text/UUID/vector for that occurrence refuses; normalized
direction equality alone does not excuse a changed raw numeric vector.

With `--generation-ledger`, selection is the receipt's expected occurrences for
its `generation_id`. Other generations/legacy rows are counted as unselected;
they cannot fill missing expected inputs. Matching rows must join on occurrence
ID, UUID, exact-text hash, recipe and response hash. Unexpected occurrences in
the selected generation refuse. Managed output requires its receipt and cannot
bypass that requirement with `--allow-legacy-source`.

## Counts and publication

| Field | Meaning |
|---|---|
| `selected` | Distinct selected occurrences, including receipt expectations with no stored row |
| `available` | Selected occurrences with present vector payloads, including rejected payloads |
| `valid` | Accepted occurrences with normalized vectors |
| `missing` | Expected/selected occurrences without available vector payloads |
| `rejected` | Selected occurrences excluded by identity, vector, recipe or generation validation |
| `unique_texts` | Distinct known exact-text hashes across selected occurrences |
| `valid_unique_texts` | Distinct text hashes among valid occurrences |
| `available_rows` | Raw source records scanned, including repeated attempts and unselected generations |
| `duplicate_attempts` / `unselected_rows` | Collapsed valid attempts / rows outside the receipt selection |

`selected = valid + missing + rejected`; `available = valid + rejected`.
For legacy stores, `generation_coverage` stays `unknown`, even if every available
row validates. `missing=0` only describes selected records; missing original
generation inputs cannot be inferred. `--allow-legacy-source` acknowledges this.
`expected_original` and `missing_original` stay null for legacy stores; with a
receipt they describe its explicit selected generation.

Malformed, zero or nonfinite vectors are recorded as per-occurrence exclusions.
Validation can finish with exclusions; `analysis_ready` is false unless
`--allow-partial` explicitly accepts them. Mixed spaces/dimensions and ambiguous
or conflicting identities refuse the entire snapshot. Known incomplete generation
refuses by default. Partial mode preserves all exclusions and `partial` coverage;
it never claims corrected graph completion or verified provenance.

| Output | Contract |
|---|---|
| `corpus.sqlite` | `records` indexed by ordinal, occurrence ID, source UUID, text hash and vector index; exact text, normalized BLOB, recipe, source ordinal, attempt count, status/reason and generation state/hash; `metadata` holds schema/source/space selection |
| `rejections.csv` | Occurrence ID, source ordinal, stage and reason for each missing/rejected occurrence; machine-readable CSV, not a spreadsheet view |
| `status.json` | Running, refused, failed, interrupted or completed validation; counts when available, value-free refusal categories and timing |
| `snapshot.json` | Sole successful publication marker (`corpus-snapshot-1`, `snapshot_complete`), with effective limits, source/recipe/selection, counts, coverage and SHA-256 checksums of core outputs |

Treat published files as immutable. Consumers must require `snapshot.json`,
verify its output checksums, open SQLite read-only and respect coverage and
`analysis_ready`. A status file alone is not a successful snapshot. Completion
is published last, after the database and CSV are closed. An interruption or
disk failure can leave staging files and a stale `running` status, without a
completion marker. There is no automatic resume or adoption of such files.
Remove that specific incomplete output or choose another directory; prior
complete runs and source stores are preserved. Loss of storage can prevent even
the failure status from being written.

## Limits and refusals

All values are positive integers, configurable without fixed hardware ceilings.

| Flag | Default | Checked boundary |
|---|---:|---|
| `--max-source-bytes` | 1073741824 | Physical source/receipt file size; CSV consumed bytes |
| `--max-records` | 1000000 | Source records scanned and receipt expectations |
| `--max-record-bytes` | 1048576 | CSV logical record before parsing; selected SQLite cell lengths before fetching; Arrow row before Python conversion; canonical projected record |
| `--max-batch-records` | 128 | Maximum database/Arrow fetch size and commit interval |
| `--max-batch-bytes` | 33554432 | Projected record, normalization workspace estimate, projected Parquet row-group uncompressed bytes and Arrow batch |
| `--max-working-bytes` | 268435456 | Admission requires `4*max_batch_bytes + 16*max_record_bytes` within this allowance |
| `--max-disk-bytes` | 4294967296 | Snapshot files, rollback journal and publication allowance; SQLite also reserves half this budget for its main database |

At least 65536 disk bytes must be admitted for schema/journal/status overhead
before any output is created. Actual records and indexes require additional space.

SQLite fetch sizes shrink using observed row lengths. Parquet can refuse a large
compressed row group even when it has few rows: rewriting a **separate** source
with smaller row groups can reduce decoding demand. It does not silently convert
the input. CSV and normalization process one record at a time. Metadata and
duplicate/identity lookups stay indexed on disk; no whole-store list API is used.

The working allowance is conservative buffer admission, **not an enforced process
RSS quota**. Interpreter/library overhead, Arrow decompression and allocator
behavior still need measurement on the actual machine. Disk checks are not a
reservation against other processes. Graph/time/edge limits and whole-workflow
capacity are not qualified by this validation operation.

Refusal categories include limit names (with demand, limit and adjustment
guidance), `disk_free`, `source_missing`, `source_format`, `source_schema`,
`invalid_utf8`, `malformed_csv`, `source_changed`, `sqlite_wal_active`,
`sqlite_source`, `invalid_metadata`, `conflicting_metadata`, `mixed_space`,
`mixed_dimension`, `ambiguous_uuid`, `mixed_occurrence_identity`,
`invalid_occurrence_id`, `conflicting_occurrence`, `conflicting_attempt`,
`legacy_acknowledgement`, `invalid_declaration`, `generation_ledger_required`,
`ledger_schema`, `ledger_inconsistent`, `ledger_selection_mismatch`,
`ledger_response_mismatch`, `incomplete_generation` and `output_exists`.
Invalid rows use `invalid_uuid`, `invalid_text`, `missing_vector`,
`malformed_vector`, `invalid_vector_shape`, `nonnumeric_vector`,
`nonfinite_vector`, `zero_vector` or `generation_<state>`. Storage/I/O errors
propagate, leave no completion marker and normally record `storage_failure`.
Do not treat a refusal as permission to remove limits blindly.

## Generation outcome receipt

`embeddings compute` now writes a new SQLite receipt, by default a unique
`generation-<uuid>.sqlite` beside the local vector destination (beside the
analysis/input path for Mongo). `--generation-ledger FILE` sets an explicit new
path. Existing receipts are never overwritten. The printed path identifies the
receipt for later validation:

```bash
python main.py embeddings snapshot --source vectors.csv --generation-ledger generation-example.sqlite --snapshot-dir results/validated-generation
```

This command needs existing outputs; it does not generate them or call a provider.
To inspect known partial output, add `--allow-partial` explicitly.

Receipt schema `generation-ledger-1` has `metadata` for schema, generation ID,
recipe and run status, and one ordered `outcomes` row per input occurrence.
Terminal states are `stored`, `provider_failed`, `storage_failed`,
`not_attempted` and `interrupted`. `pending`, `received` and
`stored_pending_finalize` are intermediate; a hard crash may retain them, and
that receipt is incomplete. UUID/text hashes preserve identity without copying
texts/vectors into the receipt. Responses are marked received before writing;
stored status is confirmed only after backend finalization.

Provider retry exhaustion and storage/finalization errors propagate. A successful
provider response is never replayed because persistence failed. A partially
written failed batch is conservatively storage-failed, even if some rows exist.
Earlier confirmed batches remain usable under explicit partial selection.
Abrupt ledger/disk failure can prevent terminalization; absence of a complete
receipt is never success. Automatic cross-run resume/replay is not implemented.

Combined compute/legacy analysis proceeds only after a complete receipt and
selects only the current generation's rows. The small legacy CSV diagnostic
refuses managed outputs; use snapshot validation with their receipt. The legacy
graph's mathematical/resource limits remain unchanged.

Generation input still uses the existing in-memory CSV/JSON/Excel loader.
`--max-input-bytes` defaults to 268435456 before loading, and
`--max-input-records` to 1000000 after loading. Compressed Excel/JSON expansion
is not bounded by those file/row caps; select/convert smaller inputs first.
This is not a streaming generation or paid-call budget implementation.

Storage readers also expose context-managed projected `iter_documents` APIs.
The injected Mongo reader has fake-contract coverage for projection, filter,
stable `_id` ordering, batch hints and cursor closure. Live Mongo snapshot
consistency, driver/BSON buffering and scale are unqualified; the snapshot CLI
accepts local sources only.
