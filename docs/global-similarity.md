# Corrected global similarity analysis

Build a validated snapshot, then analyze it without provider credentials. From a
source checkout, these complete commands use only the synthetic fixture:

```bash
python main.py embeddings snapshot --source tests/fixtures/diagnostic/vectors.csv --snapshot-dir results/snapshot-01 --allow-legacy-source
python main.py embeddings analyze --snapshot-dir results/snapshot-01 --analysis-dir results/global-analysis --threshold 0.75 --tolerance 0.0000001 --seed 42 --resolution 1 --excel-view --projector-view
```

For an installed package replace `python main.py` with `nblue`. A module invocation
is `python -m narrative_blueprint`. The snapshot directory must be new; the analysis
directory may hold multiple runs. The fixture has four valid occurrences, three
unique texts, three retained edges, two communities and one isolate. These are
synthetic geometry checks, not an evaluation of language or narrative meaning.

The corrected route takes **only a completed snapshot**. It does not reopen the
original source. See [snapshot validation](snapshot-validation.md) for CSV, Parquet,
SQLite, generation receipts and explicit partial selection. A snapshot with missing
or rejected inputs must have been built with `--allow-partial`; analysis preserves
those exclusions. Successful analysis does not establish complete generation:
legacy generation coverage stays unknown.

## Graph method

Every valid occurrence becomes a node, including repeated text and isolates. Nodes
are sorted by occurrence ID using SQLite BINARY ordering. Repeated text shares a
text hash but is not collapsed. The snapshot's source UUID strings, including
leading zeros, remain available in assignments. Source reordering can change
legacy snapshot-derived occurrence IDs; permutation reproducibility requires the
same stable occurrence IDs, not merely equal text.

Two-dimensional tiles visit all `N*(N-1)/2` unordered pairs. Threshold selection
and pair extraction use NumPy masks; a whole tile is admitted before its pairs
are inserted. This batching preserves the strict numeric rule below. There is no preliminary
within-block filter or dense survivor matrix. Scores use float64 renormalization
and dot products of the snapshot's normalized float32 vectors, then clipping to
`[-1, 1]`. An edge is retained exactly when:

`cosine >= threshold`

The threshold defaults to 0.75 and must be in `(0, 1]`. The tolerance defaults to
`1e-7` and must be in `[0, threshold)`. It identifies numeric-boundary comparisons
(`abs(cosine - threshold) <= tolerance`) reported as `graph.boundary_pairs`, and
defines the small-oracle comparison tolerance. It does not expand the threshold;
scores below the threshold remain excluded. Exported weights are actual clipped
scores. Float32 snapshot rounding means these are not bitwise equal
to cosine scores computed from original full-precision input. Tests compare small
independent dense float64 oracles and explicitly exercise threshold boundaries.

Weighted NetworkX Louvain uses seed 42 and resolution 1 by default. Both can be
configured with `--seed` and `--resolution`. The manifest records these values,
NetworkX/NumPy versions and node/edge insertion order. Edges enter Louvain in
canonical `(i,j)` order regardless of tile size. Community IDs are the minimum
canonical node index in each group and are local to a run. Compare memberships
by occurrence ID across runs. A seed supports repeatability under a fixed software
environment; it does not guarantee identical partitions across library versions,
hardware or boundary-score rounding.

Empty, one-node and no-edge graphs bypass Louvain. An isolate has its own community
and `isolated` outcome. A one-node community with a nonzero degree is `singleton`;
other grouped nodes are `assigned`. None of these labels establishes noise,
coordination, shared intent, falsity or prevalence.

## Difference from the legacy diagnostic

The corrected snapshot route replaces the legacy adapter for full analysis. The
older `analyze --source ... --allow-legacy-source` route remains a capped CSV
compatibility diagnostic; it still uses the legacy graph and its JSON schemas.
The combined `embeddings compute` analysis is also legacy; use `--skip-analysis`,
build a snapshot with its receipt, then use the corrected route for new work.
These compatibility paths do not acquire corrected behavior merely by upgrading.

Corrected results intentionally differ: cross-block matches are recovered, every
valid occurrence survives, and bridge edges no longer inflate internal community
statistics. Similarity is still a diagnostic property of the supplied embedding
space. The [qualification experiment](qualification.md) compares exact kNN using
existing NumPy operations; it is a benchmark, not a production analysis mode.
The production default remains exhaustive threshold. kNN omits qualifying pairs;
union symmetry can give nodes degree greater than k, while mutual symmetry can
isolate nodes, especially under ties. No ANN or narrative-validity claim is added.

See [output interpretation](analysis-outputs.md) and [limits and refusals](analysis-limits.md).
