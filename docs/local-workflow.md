# Local workflow scope

The locally qualified workflow covers stored-vector diagnostics, snapshot
validation, corrected global similarity analysis and bounded output publication.
The corrected exhaustive threshold graph is the reference for new analysis.
Exact kNN remains an experiment; there is no production kNN mode or automatic
fallback. Threshold 0.75 and resource defaults are unchanged; `--threshold`
remains an explicit user option. This is a local source increment, not a public
release or completion of every narrative-analysis capability.

## Run the offline workflow

From a source checkout with its dependencies installed, use new output paths:

```bash
python main.py embeddings analyze --source tests/fixtures/diagnostic/vectors.csv --allow-legacy-source --analysis-dir results/local-diagnostic
python main.py embeddings snapshot --source tests/fixtures/diagnostic/vectors.csv --snapshot-dir results/local-snapshot --allow-legacy-source
python main.py embeddings analyze --snapshot-dir results/local-snapshot --analysis-dir results/local-analysis --threshold 0.75 --tolerance 0.0000001 --seed 42 --resolution 1 --excel-view --projector-view
```

The first command is the retained **legacy diagnostic**: four selected occurrences,
three unique texts and one community representing two unique texts. It collapses
duplicate text and omits the isolate from its graph. The snapshot preserves four
valid occurrences and three unique texts. Corrected analysis produces three edges,
two communities and one isolate. Its completion manifest is inside
`results/local-analysis/run-<id>/`; without that manifest the run is incomplete.
Legacy generation coverage remains unknown.

For installed use, replace `python main.py` with `nblue` or
`python -m narrative_blueprint`, and give paths appropriate to the current
directory. See [quick start](quick-start.md) for installation and a self-contained
fixture outside a checkout. Prompt examples and benchmark scripts are checkout
files, not installed package resources.

For resource experiments, these checkout-only commands reproduce the existing
aggregate reports; they are optional and take longer than the tiny example:

```bash
python benchmarks/qualify.py calibration --work-root ../qualification-work --report ../qualification-reports/calibration.json
python benchmarks/qualify.py pipeline --work-root ../qualification-work --report ../qualification-reports/pipeline.json
python benchmarks/qualify.py knn --work-root ../qualification-work --report ../qualification-reports/knn.json
```

The harness runs sequential offline workers. The pipeline command above selects
synthetic profiles only. [Qualification](qualification.md) explains measurement
boundaries, explicit local-sample selection and the experimental kNN comparison.
These commands do not generate embeddings or call a provider.

## Read outputs and recover safely

Use [snapshot validation](snapshot-validation.md) for selection, rejection and
receipt checks, then [analysis outputs](analysis-outputs.md) for CSV joins.
Assignment rows map occurrence IDs to source UUIDs, text hashes and communities;
full text stays in the referenced input snapshot. Repeated texts remain distinct
occurrences. Edge endpoints join to assignments. Community summaries
separate internal edges from incident bridge counts; a global bridge is counted
once in the global total and can be incident to two communities.

Only a completed, verified snapshot feeds corrected analysis. Missing or rejected
inputs require explicit partial selection. A source change, active SQLite
journal/WAL, incompatible recipe or resource refusal is not a successful result.
Refusals keep their reason and effective demand/limit; they never raise the
threshold or silently choose another graph.

Prior completed analysis runs survive failed publication. Incomplete staging
may retain full source text and vectors; inspect its status and choose a new
destination or remove only the unwanted incomplete run. Inputs must be quiescent.
Cooperative admission checks are not OS memory/CPU quotas. SQLite index-sort
temporaries may use system TEMP outside the scratch volume's disk accounting.
[Limits and refusals](analysis-limits.md) documents the exact defaults.

## Evidence and support boundary

The recorded engineering evidence is from Windows 11, CPython 3.14.2,
NumPy 2.4.0, NetworkX 3.6.1 and scikit-learn 1.8.0. The package declares
`>=3.14,<3.15`; dependencies in `requirements.txt` are unpinned. Another resolved
environment needs its own checks. A seed does not guarantee identical partitions
across runtimes, hardware or numeric-boundary rounding.

Existing evidence includes guarded synthetic diagnostics, Windows wheel/editable/
clone/foreign-directory entry checks, snapshot and receipt contracts, independent
dense-oracle graph comparisons, output joins and publication-fault checks.
[Qualification](qualification.md) records six memory calibrations, 17 synthetic
full-path profiles and a permitted local sample. Those observations establish
bounded local behavior, not arbitrary-corpus capacity.

The 2,500-occurrence, 3,072-dimension sample retained 3,018,265 edges, three
communities and no isolates at 0.75. Its measurement used 3,123,750 maximum edges,
2 GiB graph, 3 GiB additional clustering, 6 GiB working allowance and 1,800 seconds;
all other analysis limits stayed at defaults. It exceeds the default edge cap
and observed 2 GiB working allowance. Retaining 96.6% of possible pairs motivates
methodology review; it does not establish narrative quality.

Provider/model names in examples are locally configured identifiers, not claims
of current account access, availability or paid-call qualification. Blueprint and
embedding generation remain independent provider operations. The supplied neutral
templates are provisional; see [template compatibility](blueprint.md#template-compatibility)
for changed fields, old outputs and UUID-only resume limitations.

## Deferred capabilities

- Full provider budgets, retry/resume policy, per-user authentication and live
  account/provider qualification; generation still uses invocation-relative
  `config/.env` or environment variables.
- Broader research questions, analysis units, configurable neutral profiles,
  versioned schemas, recipe-aware blueprint resume and old-output adapters.
- Topic terms and representative selection, topic-label defaults and optional
  paid labels.
- Evidence-grounded semantic annotation, reviewed spans and bilingual human
  evaluation, including real-corpus construct validity.
- Score-percentile and threshold-sweep diagnostics; these are separate work and
  are not available in this increment.
- Production kNN, ANN, Leiden, HDBSCAN, UMAP and full BERTopic.
- Live MongoDB and other-platform qualification; Mongo reader evidence is fake
  contract coverage only. No current wheel rebuild is implied by earlier
  packaging checks.
- Unbounded Excel/Projector exports, collection and a user interface. Current
  optional views remain bounded.
- Automatic conclusions about coordination, truth or attribution.

Later interpretation/provider releases need qualification for their own scope.
The current examples and local measurements do not supply that evidence.
