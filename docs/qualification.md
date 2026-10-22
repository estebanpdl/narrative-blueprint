# Local workflow qualification

The corrected exhaustive threshold graph remains the production reference.
Qualification measures ingestion, normalized snapshot creation, canonical staging,
all-pair admission/discovery, NetworkX conversion, seeded Louvain, CSV export,
source/output verification and manifest publication. It does not establish
narrative validity, multilingual accuracy or capacity on another machine.

## Reproduce the measurements

From a checkout with its existing dependencies, choose an output directory outside
the repository. Each command starts one fresh worker at a time and removes its
owned temporary data after the measurement. Reports contain aggregate metrics.
`pipeline` without `--cases` runs synthetic profiles only. No provider or network
access is permitted by the harness. Source generation and input-integrity hashing
are outside the reported full-path time; ingestion from that source is inside it.

```bash
python benchmarks/qualify.py calibration --work-root ../qualification-work --report ../qualification-reports/calibration.json
python benchmarks/qualify.py pipeline --work-root ../qualification-work --report ../qualification-reports/pipeline.json
python benchmarks/qualify.py knn --work-root ../qualification-work --report ../qualification-reports/knn.json
```

Use `--cases small wide` to select named profiles. To measure a permitted local
CSV read-only, explicitly select `--cases local-sample --source /path/to/embeddings.csv`.
That profile has documented larger analysis limits; it never changes defaults or
the threshold. All sample-derived snapshots, mappings and exports are temporary;
the harness verifies source byte equality without retaining its hash. The normal
CLI retains outputs for analyst review instead.

Workers set OpenBLAS/OMP/MKL threads to one and record effective thread pools,
versions, interpreter and platform. A background sampler observes working set,
private bytes and owned disk files every 50 ms. OS process peaks supplement
sampling, which can miss short-lived allocations. Windows peak committed bytes
use PeakPagefileUsage, labelled `peak_private_bytes`; they are not peak resident
memory. POSIX supplies peak RSS and null private-memory metrics. Process peaks
can include imports or earlier stages; per-stage baselines and sampled peaks are
reported separately. Disk sampling includes synthetic inputs but excludes an
external local source. Disk peaks count visible owned files only; unlinked OS or
SQLite sort temporaries and filesystem cache are not measured. Index construction
has a separate conservative disk reserve. Timings include measurement overhead and are single runs,
not statistical performance estimates.

## Graph-memory calibration

Measured on 2026-10-22 on Windows, CPython 3.14.2, NumPy 2.4.0 and NetworkX 3.6.1. The calibration
inserts fresh integer/float edge objects as SQLite conversion does, uses weight
0.9 and Louvain seed 42/resolution 1, and includes isolates and coarsening. MiB
means 1,048,576 bytes. Values below are growth above the pre-graph process baseline;
the larger of working-set and private/committed growth is shown.

| Shape | Nodes | Edges | Conversion growth MiB | Graph + Louvain peak growth MiB |
|---|---:|---:|---:|---:|
| Isolates | 10,000 | 0 | 2.22 | 5.43 |
| Sparse random forward links | 3,000 | 59,790 | 22.73 | 45.39 |
| Disjoint groups of 100 | 3,000 | 148,500 | 55.39 | 115.17 |
| Complete | 500 | 124,750 | 40.46 | 81.14 |
| Complete | 1,000 | 499,500 | 165.95 | 330.11 |
| Complete | 1,500 | 1,124,250 | 405.89 | 828.08 |

The admitted conversion estimate is `65536 + 1024*N + 512*E`; additional clustering
workspace is `8388608 + 2048*N + 768*E`. Combined, they reserve about 1.25 KiB per
edge plus node/fixed terms. Across these measurements, conversion admission is at
least 1.35 times observed growth and total admission at least 1.6 times observed
peak growth. This replaces the previous uncalibrated 4 KiB/edge total, without
changing any configured limit. The process baseline and record/cache reserves
are additional. New runtimes, graph representations or graph shapes need renewed
qualification. Admission and cooperative observations are not OS quotas; Louvain
can exceed a time or memory allowance before returning to a check.

## Measured synthetic profiles

These examples use seed 42 and threshold 0.75. Ordinary text payloads are 64 bytes;
the large-record case uses 32,768-byte text. The maximum generated JSON record
ranges from 870 bytes in the small profile to 63,706 bytes in the wide profile;
the large-record case reaches 34,237 bytes. Dimensions below are the actual
snapshot dimensions. All complete runs published exactly one completion marker.

| Profile | N × d | Edges | Communities | Full path s | Peak working set MiB | Visible owned disk MiB |
|---|---:|---:|---:|---:|---:|---:|
| Small groups | 128 × 32 | 960 | 8 | 6.21 | 168.81 | 0.40 |
| Identical content/vectors | 1,000 × 64 | 499,500 | 1 | 38.97 | 500.50 | 35.12 |
| No edges | 2,500 × 128 | 0 | 2,500 | 54.92 | 190.66 | 11.96 |
| Wide, groups of 50 | 2,500 × 3,072 | 61,250 | 50 | 58.69 | 220.71 | 217.43 |
| Many, sparse | 14,000 × 32 | 27 | 13,973 | 266.77 | 213.30 | 28.14 |
| Large records | 128 × 64 | 960 | 8 | 3.43 | 173.96 | 16.54 |
| SQLite | 512 × 64 | 7,936 | 16 | 4.00 | 176.93 | 2.44 |
| Parquet | 512 × 64 | 7,936 | 16 | 4.71 | 183.97 | 1.47 |
| Small budget | 128 × 32 | 960 | 8 | 10.37 | 177.20 | 0.40 |

All use default limits except the small-budget case: 80,000 tile bytes and
384 MiB process allowance, yielding four-row tiles. Other effective tiles are
128 rows for N=128 and 256 for larger cases. Densities span zero, approximately
0.0000276% for the 14,000-row case, 1.96% for the wide profile and 100% for
identical vectors. The 14,000-row run covers 97,993,000 unordered pairs; it is not
evidence for a dense graph at that size. Source/snapshot formats and densities
are part of each profile, so elapsed times should not be compared by N alone.

| Failure profile (input N × d) | Configured limit / injection | Result | Full path s | Peak working set MiB |
|---|---|---|---:|---:|
| 128 × 32, identical | 100 edges | `max_edges` | 2.21 | 168.28 |
| 15,000 × 8 | Default 100,000,000 comparisons | `max_comparisons` | 311.15 | 178.06 |
| 128 × 32 | 100,000 graph bytes | `max_graph_bytes` | 3.15 | 165.61 |
| 128 × 32 | 131,072 analysis disk bytes | `max_disk_bytes` | 1.44 | 166.77 |
| 128 × 32 | 1,000 export bytes | `max_export_bytes` | 4.23 | 168.89 |
| 128 × 32 | 0.001 analysis seconds | `max_seconds` | 1.93 | 165.86 |
| 16 × 8, 4,096-byte text | 1,024 snapshot record bytes | `max_record_bytes` | 1.71 | 165.37 |
| 128 × 32 | Injected directory-rename failure | `storage_failure` | 5.61 | 169.13 |

All eight failure profiles published zero analysis completion markers. Refusals
remain failures, not sampled/truncated successes. The 15,000-row run completes
ingestion before analysis refuses its 112,492,500 comparisons; its elapsed time is
mostly snapshot creation. The 0.001-second limit applies to analysis, not upstream
snapshot creation. A normal CLI user can retain a completed snapshot and adjust
analysis limits without repeating ingestion. The measurement harness removes its
temporary snapshot even on refusal.

## Complete local CSV measurement

A read-only local CSV with 2,500 valid rows at d=3,072 completed with 3,018,265
edges (96.62% density), 3 communities and no isolates. All 2,500 selected rows were
analyzed, with no missing/rejected rows. These are aggregate structural results;
no source values, IDs, hashes or labels are included here. Source byte equality
was checked and all temporary snapshots/outputs were deleted after measurement.

| Stage / resource | Measured result |
|---|---:|
| Ingestion and snapshot | 40.79 s |
| Snapshot validation/staging, comparison, clustering and publication | 305.60 s |
| Full path | 346.39 s |
| Pair discovery and final unique index | 30.17 s |
| NetworkX conversion | 9.53 s |
| Louvain | 59.99 s |
| Export and verification, including checksums | 191.36 s |
| Peak process working set | 2,094.98 MiB |
| Peak process committed bytes | 2,094.88 MiB |
| Sampled peak owned disk, excluding source | 636.55 MiB |
| Complete evidence exports | 491,728,979 bytes |

Analysis limits for this measurement: `max_edges=3123750` (all possible pairs),
`max_graph_bytes=2147483648`, `max_clustering_bytes=3221225472`,
`max_working_bytes=6442450944`, `max_seconds=1800`; other graph and snapshot limits
were defaults. Threshold 0.75, tolerance 1e-7, seed 42, resolution 1 and effective
tile rows 256 were unchanged. This dense case exceeds the default one-million-edge
cap and its measured working-set peak exceeds the default 2 GiB process allowance.
Successful qualification required explicit configuration, not higher defaults.

An earlier trial still maintaining the scratch pair index on each insertion was
interrupted before clustering, after an observation at 742.92 s elapsed and
39.63 s CPU. It is incomplete evidence, not a successful baseline timing or a
precise speedup ratio. Building the unique index after append-only discovery
removed that observed staging bottleneck. Successful publication still took
substantial time because every retained edge is exported and verified. The final
run above includes that cost and the same strict threshold rule.

## Choose limits for your data

1. Build a snapshot first. Read its actual valid N, dimension d, exclusions and
   generation coverage. A completed graph does not turn unknown coverage into
   complete generation.
2. Compare `N*(N-1)/2` with `--max-comparisons`. All-pair arithmetic remains
   quadratic even with vectorized selection. For example, 50,000 rows require
   1,249,975,000 comparisons and refuse the 100,000,000 default.
3. Set explicit node/edge, graph, clustering and process limits according to
   available resources. Density determines retained E; identical content can
   retain every pair. Use the formulas above to evaluate a candidate edge ceiling.
   The default one-million-edge cap can refuse a much smaller dense corpus.
4. Let tile dimensions adapt to d and `--max-tile-bytes`. Selection/index buffers
   are included even when every pair passes. Increasing tile size can change
   floating-point boundary rounding; it does not change the declared threshold.
5. Budget source/snapshot, scratch, export, record and elapsed-time limits
   separately. Long records, dense graphs and slow storage have different costs.
   Refusals report the violated limit; do not interpret partial files as success.
6. Accept only `run-*/manifest.json` with `status: complete`, inspect counts and
   limits, and retain the source snapshot with published evidence. Failed staging
   directories can contain full source text and vectors; manage them accordingly.

## Exact-kNN experiment and policy

The benchmark uses existing NumPy operations to score every candidate exactly
under the selected floating-point arithmetic. It keeps the k highest non-self
scores per node with a positive floor of 0.75, orders equal scores by stable
occurrence ID, then applies either union or mutual symmetry. The tested k values
are 5, 20 and 50. Union accepts either directed selection; mutual requires both.
An undirected edge takes the maximum of its selected directional scores if
floating-point arithmetic makes those scores differ.
The selected graph uses the same canonical node/edge order, seed 42, resolution 1
and weighted Louvain. It has no production CLI mode, fallback or new dependency.
The experimental implementation is capped at 5,000 nodes, 4,096 dimensions and
one million directed candidate slots;
its chunked brute-force comparisons are still quadratic.

Reports count missed and extra threshold pairs, density, communities, changed
membership sets and adjusted Rand index (ARI, invariant to community label
numbers). They also repeat selection after input permutation with stable IDs and
with float32 arithmetic instead of the reference's float64 renormalization of
snapshot float32 vectors. Exact computed ties have stable order; nearly equal
scores can change rank with precision. Stable IDs are necessary for order checks;
legacy source-derived IDs can themselves change when the source is reordered.

The following measured slice uses k=20. Full reports also include k=5 and k=50;
k is capped at N-1. Reference threshold edge/community counts are shown in the
profile label. Density is over all possible unordered pairs.

| Profile (N × d; reference E / communities) | Symmetry | kNN E | Density | Missed threshold pairs | Communities | ARI vs reference |
|---|---|---:|---:|---:|---:|---:|
| Groups (500 × 32; 12,250 / 10) | Union | 7,900 | 6.33% | 4,350 | 10 | 1.0000 |
| Groups | Mutual | 2,100 | 1.68% | 10,150 | 300 | 0.2718 |
| Identical (128 × 16; 8,128 / 1) | Union | 2,350 | 28.91% | 5,778 | 1 | 1.0000 |
| Identical | Mutual | 210 | 2.58% | 7,918 | 108 | 0.0000 |
| Circle (400 × 2; 18,400 / 4) | Union | 4,000 | 5.01% | 14,400 | 9 | 0.4157 |
| Circle | Mutual | 4,000 | 5.01% | 14,400 | 9 | 0.4157 |
| Boundary (8 × 2; 26 / 1) | Union | 26 | 92.86% | 0 | 1 | 1.0000 |
| Boundary | Mutual | 26 | 92.86% | 0 | 1 | 1.0000 |

At k=20 the changed-membership counts are respectively 0/500 for grouped
union/mutual, 0/128 for identical union/mutual, 400 for both circle graphs and
zero for the boundary case. Identical points illustrate why mutual kNN with
stable ties can create many isolates. Grouped k=50 recovers all reference edges;
circle k=50 still misses 8,400 pairs and changes every node's membership set,
despite having the same count of four communities as the reference.

All 24 trials had zero extra threshold pairs. Permuting input while retaining
stable IDs changed zero edge sets and gave assignment ARI 1 in every trial.
Float32 arithmetic changed 171 union / 193 mutual circle edges at k=5 and 3 / 9
boundary edges at k=5. On the circle, k=20 kept the same edges but its rounded
weights changed Louvain assignments (ARI 0.7770 vs float64); k=50 also kept the
same edges while assignment ARI fell to 0.6345. The threshold references had
unchanged edge sets and ARI 1 in these four precision checks. This finite set does
not establish general precision invariance. Ties, weights and numeric choices
matter even when edge counts or community counts agree.

kNN selection and clustering timings are recorded separately in the JSON reports.
They exclude ingestion, durable edge staging, publication and verification for
the candidate graph; they are not full-path speedups over threshold analysis.
The comparison uses synthetic geometry only, not a quality evaluation on the
local CSV or a judgment about narrative meaning.

Retain exhaustive threshold and defer adoption of a production kNN policy until
the edge omissions and assignment changes are accepted for the intended use.
Synthetic geometry and resource savings do not establish which graph is more
valid for narrative analysis. ANN and additional dependencies require separate
evaluation. Usability feedback and use-specific narrative validity are not
established by these measurements.
