"""Complete-path example profiles, including explicit refusals and storage faults."""

from contextlib import ExitStack, closing
import csv
from dataclasses import asdict
import gc
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch

import numpy as np

from narrative_blueprint.analysis.threshold import graph, pipeline
from narrative_blueprint.analysis.threshold.contracts import GraphLimits, GraphParameters
from narrative_blueprint.analysis.threshold.snapshot_input import Scratch
from narrative_blueprint.corpus.contracts import SnapshotLimits, SnapshotRefused
from narrative_blueprint.corpus.snapshot import build_snapshot, file_hash
from .measurement import Measurement, environment


# Examples, not capacity promises. Source generation is outside measured total.
CASES = {
    "small": dict(n=128, d=32, group=16),
    "identical": dict(n=1000, d=64, group=1000),
    "no-edges": dict(n=2500, d=128, group=0),
    "wide": dict(n=2500, d=3072, group=50),
    "many": dict(n=14000, d=32, group=0),
    "large-records": dict(n=128, d=64, group=16, text_bytes=32768),
    "sqlite": dict(n=512, d=64, group=32, storage="sqlite"),
    "parquet": dict(n=512, d=64, group=32, storage="parquet"),
    "small-budget": dict(n=128, d=32, group=16, limits=dict(max_tile_bytes=80000, max_working_bytes=384 * 1024**2)),
    "edge-refusal": dict(n=128, d=32, group=128, limits=dict(max_edges=100)),
    "comparison-refusal": dict(n=15000, d=8, group=0),
    "memory-refusal": dict(n=128, d=32, group=16, limits=dict(max_graph_bytes=100000)),
    "disk-refusal": dict(n=128, d=32, group=16, limits=dict(max_disk_bytes=131072)),
    "export-refusal": dict(n=128, d=32, group=16, limits=dict(max_export_bytes=1000)),
    "time-refusal": dict(n=128, d=32, group=16, limits=dict(max_seconds=0.001)),
    "record-refusal": dict(n=16, d=8, group=4, text_bytes=4096, snapshot_limits=dict(max_record_bytes=1024)),
    "publication-fault": dict(n=128, d=32, group=16, fault=True),
    "local-sample": dict(limits=dict(max_edges=3123750, max_graph_bytes=2 * 1024**3,
        max_clustering_bytes=3 * 1024**3, max_working_bytes=6 * 1024**3, max_seconds=1800)),
}


def synthetic_source(root, spec):
    storage = spec.get("storage", "csv")
    path = root / ("synthetic." + storage)
    rng = np.random.default_rng(42)
    n, d, group = spec["n"], spec["d"], spec["group"]
    maximum = 0
    fields = ("uuid", "occurrence_id", "text", "embedding", "provider", "model_name")

    def rows():
        nonlocal maximum
        vector = None
        for i in range(n):
            if not group or i % group == 0:
                vector = rng.normal(size=d)
            text = "synthetic " + (str(i // group) if group else str(i))
            text = text.ljust(spec.get("text_bytes", 64), "x")
            row = dict(zip(fields, (f"{i:08}", f"id-{i:08}", text,
                       json.dumps(vector.tolist()), "synthetic", "qualification")))
            maximum = max(maximum, len(json.dumps(row).encode("utf-8")))
            yield row
    if storage == "csv":
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows())
    elif storage == "sqlite":
        with closing(sqlite3.connect(path)) as db:
            db.execute("CREATE TABLE embeddings (id INTEGER PRIMARY KEY, " + ",".join(f"{name} TEXT" for name in fields) + ")")
            db.executemany("INSERT INTO embeddings VALUES (?,?,?,?,?,?,?)",
                           ((i, *row.values()) for i, row in enumerate(rows())))
            db.commit()
    else:
        import pyarrow as pa
        import pyarrow.parquet as pq
        iterator = iter(rows())
        import itertools
        writer = None
        try:
            while batch := list(itertools.islice(iterator, 64)):
                for row in batch:
                    row["embedding"] = json.loads(row["embedding"])
                table = pa.Table.from_pylist(batch)
                if writer is None:
                    writer = pq.ParquetWriter(path, table.schema)
                writer.write_table(table, row_group_size=64)
        finally:
            if writer is not None:
                writer.close()
    return path, maximum


def run_profile(case, root, source=None):
    spec = CASES[case]
    if case == "local-sample":
        if source is None:
            raise ValueError("local-sample requires --source")
        source = Path(source).resolve()
        maximum = None  # Do not copy or expose source records to measure this.
    else:
        source, maximum = synthetic_source(root, spec)
    before = file_hash(source)
    limits = GraphLimits(**spec.get("limits", {}))
    snapshot_limits = SnapshotLimits(**spec.get("snapshot_limits", {}))
    parameters = GraphParameters()
    result = {"case": case, "profile": spec, "limits": asdict(limits),
              "snapshot_limits": asdict(snapshot_limits), "parameters": asdict(parameters),
              "source_bytes": source.stat().st_size, "max_synthetic_record_json_bytes": maximum,
              "input_rows": spec.get("n"), "input_dimension": spec.get("d"),
              "nodes": None, "dimension": None}
    gc.collect()
    with Measurement(root) as meter, ExitStack() as patches:
        for module, name, label in ((graph, "discover_edges", "comparison"),
                (graph, "cluster_graph", "conversion_and_clustering"),
                (graph.nx.community, "louvain_communities", "louvain"),
                (pipeline, "write_tables", "export"), (pipeline, "validate_tables", "table_validation"),
                (Scratch, "stage_nodes", "snapshot_staging")):
            patches.enter_context(patch.object(module, name, meter.wrap(getattr(module, name), label)))
        if spec.get("fault"):
            patches.enter_context(patch.object(pipeline.os, "rename", side_effect=OSError("synthetic publication failure")))
        with meter.stage("total"):
            try:
                with meter.stage("ingestion_snapshot"):
                    snapshot = build_snapshot(source, root / "snapshot", limits=snapshot_limits, allow_legacy_source=True)
                result.update(nodes=snapshot["counts"]["valid"], dimension=snapshot["dimension"],
                              snapshot_counts=snapshot["counts"])
                with meter.stage("analysis"):
                    manifest = pipeline.analyze_snapshot(root / "snapshot", root / "analysis", limits=limits, parameters=parameters)
                result.update(status="complete", edges=manifest["counts"]["edges"],
                              communities=manifest["counts"]["communities"], counts=manifest["counts"],
                              graph=manifest["graph"], timings=manifest["timings"], memory=manifest["memory"],
                              output_bytes=sum(item["bytes"] for item in manifest["outputs"].values()))
                result["density"] = result["edges"] / max(1, result["nodes"] * (result["nodes"] - 1) / 2)
            except (SnapshotRefused, OSError) as exc:
                result.update(status="refused" if isinstance(exc, SnapshotRefused) else "failed",
                              reason=getattr(exc, "reason", "storage_failure"))
                # Refusal strings contain only option/demand/limit guidance.
                if isinstance(exc, SnapshotRefused):
                    result["refusal"] = str(exc)
            result["completion_markers"] = len(list((root / "analysis").glob("run-*/manifest.json")))
    result.update(stages=meter.stages, sampling_errors=meter.errors, environment=environment(),
                  source_unchanged=file_hash(source) == before)
    if not result["source_unchanged"]:
        raise RuntimeError("Input changed during measurement")
    expected = "failed" if spec.get("fault") else "refused" if case.endswith("-refusal") else "complete"
    result["expected_status"] = expected
    result["expectation_met"] = result["status"] == expected and result["completion_markers"] == (expected == "complete")
    return result
