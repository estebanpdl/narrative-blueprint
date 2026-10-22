# Corrected analysis limits and refusals

Limits on `analyze --snapshot-dir` are configurable positive values without fixed
hard ceilings. They are independent of the older CSV diagnostic's small fixed
ceilings. Units are bytes unless stated otherwise; seconds may be fractional.

| Option | Default | Admission |
| --- | ---: | --- |
| `--max-nodes` | 100000 | Actual valid occurrence count. |
| `--max-edges` | 1000000 | Actual retained edges, checked before insertion. |
| `--max-comparisons` | 100000000 | Exact `N*(N-1)/2` candidate comparisons. |
| `--max-tile-rows` | 256 | Upper bound; reduced for dimension and byte allowances. |
| `--max-tile-bytes` | 67108864 | Two blocks, conversion/normalization copies, score tile and scratch reserve. |
| `--max-graph-bytes` | 536870912 | Conservative NetworkX conversion estimate. |
| `--max-clustering-bytes` | 1073741824 | Additional Louvain/coarsening estimate. |
| `--max-working-bytes` | 2147483648 | Baseline process memory plus stage estimates; runtime memory observations. |
| `--max-disk-bytes` | 4294967296 | Per-run scratch, SQLite journal, evidence and publication allowance. |
| `--max-export-bytes` | 1073741824 | All evidence exports, views and completion-manifest reserve. |
| `--max-record-bytes` | 1048576 | Manifest/SQLite record and serialized evidence-row limit. |
| `--max-snapshot-bytes` | 4294967296 | Input snapshot database and rejection file combined. |
| `--max-seconds` | 600 | Elapsed analysis time, including validation. |
| `--max-view-rows` | 1000 | Maximum prefix rows per optional view, explicitly disclosed. |
| `--max-view-bytes` | 16777216 | Exact bytes written per optional view (both Projector files combined). |

Snapshot creation has its own limits; see [snapshot validation](snapshot-validation.md).
Increasing graph limits does not change the selected corpus or embedding policy.

For tile side `b` and dimension `d`, the score-stage estimate is
`48*b*d + 16*b*b + 65536`. It reserves conversion and normalization copies and a
score-sized scratch area. Tile size is reduced until it fits; if a single vector
tile cannot fit, the analysis refuses before allocating it. Vectors are streamed
from a disk file, without a resident whole-corpus array or memory map.

The graph conversion estimate is `65536 + 1024*N + 1024*E` bytes. An additional
three times that amount is reserved for clustering and memberships. The process
estimate also includes its observed baseline, `16*max_record_bytes` and 8 MiB of
fixed working reserve. Estimates deliberately over-admit no unlimited edge growth:
a dense corpus can hit graph/clustering limits before the edge-count cap. Every
retained edge is checked before insertion, and conversion is admitted again before
NetworkX construction. Text and vectors never become graph attributes.

These estimates and checks are admission controls, **not an OS-enforced memory or
CPU quota**. Python/BLAS/library allocations vary by runtime. Windows reports
current/peak process working set and private bytes; POSIX uses process peak RSS.
The process peak can include earlier activity in a long-lived process. Checks run
between stages, blocks and rows; a library call such as Louvain may overshoot the
time limit before returning and being refused. No successful manifest is published
after a detected overrun. Full-path qualification across larger corpora, dimensions
and machines remains separate from correctness testing on small cases.

Disk limits apply to each new run, not the combined size of historical runs.
Free disk space is also checked. Retaining failed staging directories supports
diagnosis but consumes storage; remove an unwanted failed directory only after
checking that it has no completion manifest. Inputs and prior completed runs are
not deleted by the command.

## Refusal categories

Resource refusals name the violated option (`max_nodes`, `max_edges`,
`max_comparisons`, `max_tile_bytes`, `max_graph_bytes`, `max_clustering_bytes`,
`max_working_bytes`, `max_disk_bytes`, `max_export_bytes`, `max_record_bytes`,
`max_snapshot_bytes`, `max_seconds`) with demand, limit and adjustment guidance.
`disk_free` means the filesystem has insufficient free space. No refusal truncates
the graph, raises the threshold, chooses kNN/ANN or silently changes policy.

Input refusals include `snapshot_incomplete`, `snapshot_partial`, `snapshot_schema`,
`snapshot_counts`, `snapshot_vector`, `snapshot_active`, `snapshot_checksum` and
`snapshot_changed`. Rebuild invalid/changed snapshots from a quiescent source;
do not edit their completion marker. `output_inside_snapshot` protects the input.
Parameter/option refusals include `invalid_limit`, `invalid_threshold`,
`invalid_tolerance`, `invalid_resolution`, `invalid_seed`, `required_paths`,
`conflicting_option` and `snapshot_required`.

`output_checksum`, `output_schema`, `output_join`, `output_counts`,
`selection_counts`, `assignment_missing`, `edge_counts`, `comparison_count` and
`scratch_vectors` indicate internal consistency failures, not a successful result.
Storage failures and interrupts leave a failed/interrupted status where writable.
The CLI exits nonzero. View-specific `max_view_bytes` and `excel_cell_length`
refusals are recorded in the successful core manifest if the core remains valid.
