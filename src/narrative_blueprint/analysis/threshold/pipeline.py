"""Stage isolated runs and publish a validated completion manifest last."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

from narrative_blueprint.corpus.snapshot import write_json
from .contracts import AnalysisRefused, Budget, GraphParameters, process_memory
from .graph import build_graph
from .outputs import validate_tables, write_tables
from .snapshot_input import Scratch, checked_hash, open_snapshot
from .views import write_views


def analyze_snapshot(snapshot, output, *, parameters=None, limits=None, excel=False, projector=False):
    """Return the successful manifest; failures leave only non-success status."""
    parameters = parameters or GraphParameters()
    budget = Budget(limits)
    output = Path(output).resolve()
    snapshot = Path(snapshot).resolve()
    if output == snapshot or snapshot in output.parents:
        raise AnalysisRefused("output_inside_snapshot")
    budget.limits.check("max_disk_bytes", 131072)
    run_id = str(uuid.uuid4())
    output.mkdir(parents=True, exist_ok=True)
    stage = output / (".staging-" + run_id)
    destination = output / ("run-" + run_id)
    stage.mkdir()
    status = {"schema": "threshold-analysis-status-1", "run_id": run_id, "status": "running"}
    scratch = None
    try:
        write_json(stage / "status.json", status)
        with open_snapshot(snapshot, budget) as (db, source, snapshot_hash):
            scratch = Scratch(stage, budget)
            scratch.stage_nodes(db, source)
            result = build_graph(scratch, source, parameters)
            exported_at = time.perf_counter()
            exports, totals = write_tables(scratch, db, run_id, result)
            views = write_views(scratch, exports, result, source["dimension"], excel=excel, projector=projector)
            validate_tables(exports, db, run_id, result)
            for name, metadata in exports.files.items():
                if checked_hash(stage / name, budget) != metadata["sha256"]:
                    raise AnalysisRefused("output_checksum")
            export_seconds = time.perf_counter() - exported_at
            scratch.close()
            scratch = None
        # The snapshot context checks quiescence and checksums again before
        # publication, so changes during computation cannot publish success.
        for name in ("graph.sqlite", "vectors.f32"):
            (stage / name).unlink()
        manifest = {
            "schema": "threshold-analysis-1", "method": "exhaustive-cosine-louvain-1",
            "run_id": run_id, "status": "complete", "corrected_analysis_complete": True,
            "stages": {name: "complete" for name in ("snapshot_validation", "graph", "clustering", "exports_validation")},
            "source_snapshot": {"path": str(snapshot), "manifest_sha256": snapshot_hash,
                                "source_fingerprint": source["source_fingerprint"],
                                "outputs": source["outputs"], "reported_space": source["reported_space"],
                                "provenance_verified": source["provenance_verified"],
                                "declared_space": source["declared_space"]},
            "generation_coverage": source["generation_coverage"], "selection": source["selection"],
            "expected_original": source["expected_original"], "missing_original": source["missing_original"],
            "counts": {**source["counts"], "analyzed": result["nodes"], "edges": result["edges"],
                       "communities": result["communities"], "isolates": result["isolates"], **totals},
            "dimension": source["dimension"], "graph": result, "limits": asdict(budget.limits),
            "numeric_policy": "float64 renormalization and dot products of snapshot float32 vectors; clipped cosine >= positive threshold; tolerance flags boundary pairs without expanding the threshold",
            "ordered_id_reference": "assignments.csv in canonical occurrence ID order",
            "outputs": exports.files, "optional_views": views,
            "timings": {"comparison_seconds": result["comparison_seconds"],
                        "clustering_seconds": result["clustering_seconds"], "export_validation_seconds": export_seconds,
                        "total_seconds": time.perf_counter() - budget.start},
            "memory": {**process_memory(), "observed_run_peak_bytes": budget.peak},
        }
        encoded = json.dumps(manifest, ensure_ascii=False, allow_nan=False).encode("utf-8")
        budget.limits.check("max_export_bytes", exports.bytes + len(encoded) + 8192)
        budget.limits.check("max_disk_bytes", exports.bytes + 2 * len(encoded) + 16384)
        write_json(stage / "status.json", {**status, "status": "validated"})
        budget.tick()
        os.rename(stage, destination)
        stage = destination
        # No pointer or earlier file can advertise success. This atomic marker
        # is the only completion signal, and nothing fallible follows it.
        write_json(destination / "manifest.json", manifest)
        return manifest
    except BaseException as exc:
        refusal = None
        if isinstance(exc, sqlite3.Error) and getattr(exc, "sqlite_errorcode", None) in {sqlite3.SQLITE_FULL, sqlite3.SQLITE_TOOBIG}:
            name = "max_disk_bytes" if exc.sqlite_errorcode == sqlite3.SQLITE_FULL else "max_record_bytes"
            refusal = AnalysisRefused(name, f"SQLite scratch/input limit; increase --{name.replace('_', '-')} or select a smaller snapshot")
        if scratch is not None:
            try:
                scratch.close()
            except Exception:
                exc.add_note("Scratch closure also failed")
        status.update(status="refused" if isinstance(exc, AnalysisRefused) or refusal else
                      "interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "failed",
                      reason=refusal.reason if refusal else getattr(exc, "reason", "storage_failure" if isinstance(exc, (OSError, sqlite3.Error)) else "analysis_failure"),
                      duration_seconds=time.perf_counter() - budget.start)
        try:
            write_json(stage / "status.json", status)
        except OSError:
            pass
        if refusal:
            raise refusal from exc
        raise
