# Reading corrected analysis outputs

Each analysis creates `run-<UUID>` under `--analysis-dir`. Accept a run **only when
its `manifest.json` exists and has `status: complete`**. The manifest is published
last after table counts, source joins and SHA-256 checksums are verified. Files or
`status.json` alone are not success. A refused, interrupted or failed run can leave
a `.staging-<UUID>` or uncompleted `run-<UUID>` directory. Prior complete runs are
never replaced. There is no automatically overwritten "latest" pointer.
Failed directories can retain full text, occurrence IDs and vectors in scratch
files, in addition to partial exports. Apply the input's privacy/retention rules
to them; they are not value-free diagnostic logs.

| File | Meaning |
| --- | --- |
| `manifest.json` | Method/schema versions, parameters, actual counts and dimension, software/order, effective limits, timings, memory observations, source snapshot reference and checksums, optional-view outcomes and checksums for all evidence files. |
| `assignments.csv` | Exactly one row per valid occurrence: run ID, occurrence ID, original UUID, source ordinal, text hash, community ID and outcome. Row order is the canonical ordered-ID reference. |
| `communities.csv` | Occurrence and unique-text counts, retained internal edge count and mean, and incident bridge count. |
| `edges.csv` | One row per retained unordered pair, both occurrence IDs, actual cosine, both community IDs and `internal`/`bridge` classification. No duplicated text or vectors. |
| `rejections.csv` | One row per excluded snapshot occurrence, source UUID/ordinal, missing/rejected status, stage and reason. Headers are present even with no exclusions. |

Full text and vectors stay in the immutable input snapshot, referenced by path,
manifest hash and file hashes. Keep that snapshot with the evidence if source-level
review is needed. Counts distinguish selected, valid/analyzed, missing, rejected,
unique texts and valid unique texts. Generation coverage is independent of graph
completion. With explicit partial input, valid + missing + rejected = selected;
only valid records receive assignments.

An internal edge has **both endpoints in the same community**.
`mean_internal_edge_similarity` averages only retained internal edges. It is not
the mean over all possible pairs in that community. An empty CSV cell means the
mean is undefined because there are no internal edges.

A bridge connects two different communities and appears once in `edges.csv`.
`incident_bridge_count` counts it once at each endpoint community. Therefore the
sum of that column is twice the global manifest bridge count. It is never included
in either community's internal count or internal mean. For example, two groups
with internal edge weights 0.9 and 0.8, connected by one 0.76 bridge, have internal
means 0.9 and 0.8, one incident bridge each, and one bridge globally.

## Optional views

`--excel-view` produces `view.xlsx`, with occurrence ID, source UUID, text, text
hash, community and outcome. String cells are explicitly literal text, including
formula-looking strings and leading-zero UUIDs. Unicode and line breaks are
preserved. Text longer than Excel's 32,767-character cell limit refuses the view
instead of silently shortening it.

`--projector-view` produces `projector-vectors.tsv` and
`projector-metadata.tsv`. Both use the same canonical occurrence prefix and exact
row alignment (metadata adds one header row). Metadata includes IDs and text;
tabs, line breaks and control characters become spaces. Formula-looking metadata
strings receive an apostrophe prefix. Vectors use the same renormalized snapshot
values used for scores. This is a local export; nothing is uploaded.

Both views are capped by `--max-view-rows` and `--max-view-bytes`. The manifest
records actual rows, total nodes, deterministic prefix selection and truncation.
These views do not replace the complete CSV evidence. A view-specific refusal or
file failure is reported separately and partial view files are removed. Global
resource refusals still prevent core publication. Core CSV preserves machine
values; use the literal Excel view for spreadsheet inspection of untrusted text.

Publication uses file flush/fsync, a directory rename and an atomic final marker
replace. It prevents readers treating partial runs as complete. It is not a
transaction across the input/output directories, a cryptographic signature, or a
guarantee of durability after power loss. Keep the snapshot quiescent: checksums
and nonempty journal/WAL checks before and after analysis detect ordinary changes
but do not lock out a hostile concurrent writer.
