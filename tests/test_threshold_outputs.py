"""Auditable tables, safe optional views and manifest-last failure semantics."""

import csv
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import openpyxl
import pytest

from narrative_blueprint.analysis.threshold import pipeline
from narrative_blueprint.analysis.threshold.contracts import AnalysisRefused, Budget, GraphLimits
from narrative_blueprint.analysis.threshold.outputs import Exports, validate_tables, write_tables
from narrative_blueprint.analysis.threshold.pipeline import analyze_snapshot
from narrative_blueprint.analysis.threshold.snapshot_input import Scratch, open_snapshot
from test_threshold_graph import make_snapshot


def rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def run_directory(root, manifest):
    return root / ("run-" + manifest["run_id"])


def test_hand_calculated_internal_and_bridge_accounting(tmp_path):
    snapshot = make_snapshot(tmp_path / "input", [[1, 0]] * 5, texts=["same", "same", "different", "four", "alone"])
    work = tmp_path / "work"
    work.mkdir()
    with open_snapshot(snapshot, Budget()) as (db, source, _):
        scratch = Scratch(work, Budget())
        try:
            scratch.stage_nodes(db, source)
            for node, community in enumerate([0, 0, 2, 2, 4]):
                scratch.db.execute("UPDATE nodes SET community=?,outcome=? WHERE node=?",
                                   (community, "isolated" if node == 4 else "assigned", node))
            scratch.db.executemany("INSERT INTO edges VALUES (?,?,?)", [(0, 1, 0.9), (1, 2, 0.76), (2, 3, 0.8)])
            result = {"nodes": 5, "edges": 3, "communities": 3}
            exports, totals = write_tables(scratch, db, "test-run", result)
            validate_tables(exports, db, "test-run", result)
        finally:
            scratch.close()
    assert totals == {"internal_edges": 2, "bridge_edges": 1}
    communities = rows(work / "communities.csv")
    assert [(row["occurrence_count"], row["unique_text_count"]) for row in communities] == [("2", "1"), ("2", "2"), ("1", "1")]
    assert [row["mean_internal_edge_similarity"] for row in communities] == ["0.9", "0.8", ""]
    assert [row["incident_bridge_count"] for row in communities] == ["1", "1", "0"]
    edges = rows(work / "edges.csv")
    assert [row["classification"] for row in edges] == ["internal", "bridge", "internal"]


@pytest.mark.parametrize("vectors,edges,communities", [([], 0, 0), ([[1, 0]], 0, 1),
    ([[1, 0], [0, 1]], 0, 2), ([[1, 0], [1, 0], [0, 1]], 1, 2)])
def test_complete_tables_checksums_and_current_empty_outputs(tmp_path, vectors, edges, communities):
    snapshot = make_snapshot(tmp_path / "input", vectors)
    root = tmp_path / "analysis"
    result = analyze_snapshot(snapshot, root)
    directory = run_directory(root, result)
    saved = json.loads((directory / "manifest.json").read_text())
    assert saved == result
    assert saved["counts"]["analyzed"] == len(vectors)
    assert saved["counts"]["edges"] == edges and saved["counts"]["communities"] == communities
    for name, meta in result["outputs"].items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == meta["sha256"]
        assert len(rows(directory / name)) == meta["rows"]
    assert not (directory / "graph.sqlite").exists() and not (directory / "vectors.f32").exists()
    assert saved["generation_coverage"] == "unknown"


def test_literal_excel_unicode_newlines_and_projector_alignment(tmp_path):
    texts = ["=1+1\nLínea\t中文", "+cmd", "@SUM(A1)", "-other"]
    snapshot = make_snapshot(tmp_path / "input", [[1, 0]] * 4, texts=texts)
    root = tmp_path / "analysis"
    result = analyze_snapshot(snapshot, root, excel=True, projector=True, limits=GraphLimits(max_view_rows=3))
    directory = run_directory(root, result)
    workbook = openpyxl.load_workbook(directory / "view.xlsx", data_only=False)
    sheet = workbook.active
    assert sheet["B2"].value == "0000" and sheet["B2"].data_type == "s"
    assert sheet["C2"].value == texts[0] and sheet["C2"].data_type == "s"
    assert sheet["C3"].data_type == sheet["C4"].data_type == "s"
    workbook.close()
    metadata = (directory / "projector-metadata.tsv").read_text(encoding="utf-8").splitlines()
    vectors = (directory / "projector-vectors.tsv").read_text().splitlines()
    assert len(metadata) == 4 and len(vectors) == 3
    assert metadata[1].split("\t") == ["occurrence-0000", "0000", "'=1+1 Línea 中文"]
    assert [line.split("\t")[0] for line in metadata[1:]] == [row["occurrence_id"] for row in rows(directory / "assignments.csv")[:3]]
    assert all(view["truncated"] and view["rows"] == 3 for view in result["optional_views"].values())


def test_optional_view_byte_refusal_does_not_hide_core_success(tmp_path):
    snapshot = make_snapshot(tmp_path / "input", [[1, 0]] * 2)
    root = tmp_path / "analysis"
    result = analyze_snapshot(snapshot, root, projector=True, limits=GraphLimits(max_view_bytes=2))
    directory = run_directory(root, result)
    assert result["status"] == "complete"
    assert result["optional_views"]["projector"]["reason"] == "max_view_bytes"
    assert not (directory / "projector-metadata.tsv").exists()
    assert not (directory / "projector-vectors.tsv").exists()


def test_excel_refuses_long_text_instead_of_truncating(tmp_path):
    snapshot = make_snapshot(tmp_path / "input", [[1, 0]], texts=["synthetic " * 4000])
    result = analyze_snapshot(snapshot, tmp_path / "analysis", excel=True)
    assert result["optional_views"]["excel"]["reason"] == "excel_cell_length"


def test_illegal_excel_characters_report_view_failure_only(tmp_path):
    snapshot = make_snapshot(tmp_path / "input", [[1, 0]], texts=["synthetic\x01text"])
    result = analyze_snapshot(snapshot, tmp_path / "analysis", excel=True)
    assert result["status"] == "complete"
    assert result["optional_views"]["excel"]["status"] == "failed"
    assert result["optional_views"]["excel"]["reason"] == "IllegalCharacterError"


def test_incorrect_optional_view_is_not_published(tmp_path, monkeypatch):
    from narrative_blueprint.analysis.threshold import views
    snapshot = make_snapshot(tmp_path / "input", [[1, 0]])
    original = views.projector_view
    def corrupt(*args):
        paths = original(*args)
        paths[0].write_text("bad alignment\n", encoding="utf-8")
        return paths
    monkeypatch.setattr(views, "projector_view", corrupt)
    result = analyze_snapshot(snapshot, tmp_path / "analysis", projector=True)
    assert result["optional_views"]["projector"]["reason"] == "view_validation"
    assert "projector-metadata.tsv" not in result["outputs"]


@pytest.mark.parametrize("fault", ["edges", "validation", "rename", "manifest", "interruption", "checksum", "source_changed"])
def test_publication_faults_preserve_prior_complete_run(tmp_path, monkeypatch, fault):
    snapshot = make_snapshot(tmp_path / "input", [[1, 0]] * 3)
    root = tmp_path / "analysis"
    previous = analyze_snapshot(snapshot, root)
    marker = run_directory(root, previous) / "manifest.json"
    previous_bytes = marker.read_bytes()
    original_write = pipeline.write_json

    def fail(*args, **kwargs):
        raise OSError("synthetic storage failure")

    if fault == "edges":
        original = Exports.write_csv
        def broken(self, name, values):
            if name == "edges.csv":
                fail()
            return original(self, name, values)
        monkeypatch.setattr(Exports, "write_csv", broken)
    elif fault == "validation":
        monkeypatch.setattr(pipeline, "validate_tables", fail)
    elif fault == "rename":
        monkeypatch.setattr(pipeline.os, "rename", fail)
    elif fault == "manifest":
        def broken(path, value):
            if path.name == "manifest.json":
                fail()
            return original_write(path, value)
        monkeypatch.setattr(pipeline, "write_json", broken)
    elif fault == "interruption":
        def interrupt(*args):
            raise KeyboardInterrupt()
        monkeypatch.setattr(pipeline, "build_graph", interrupt)
    else:
        original = pipeline.validate_tables
        def corrupt(exports, db, run_id, result):
            if fault == "checksum":
                with (exports.scratch.directory / "edges.csv").open("ab") as stream:
                    stream.write(b"corruption")
            else:
                with (snapshot / "rejections.csv").open("ab") as stream:
                    stream.write(b"corruption")
            return original(exports, db, run_id, result)
        monkeypatch.setattr(pipeline, "validate_tables", corrupt)
    with pytest.raises((OSError, AnalysisRefused, KeyboardInterrupt)):
        analyze_snapshot(snapshot, root)
    assert list(root.rglob("manifest.json")) == [marker]
    assert marker.read_bytes() == previous_bytes
    failed = [directory for directory in root.iterdir() if directory != marker.parent]
    assert len(failed) == 1
    state = json.loads((failed[0] / "status.json").read_text())
    assert state["status"] in {"failed", "refused", "interrupted"}


@pytest.mark.parametrize("limits,reason", [(GraphLimits(max_export_bytes=100), "max_export_bytes"),
    (GraphLimits(max_edges=1), "max_edges")])
def test_limit_refusal_never_publishes_completion(tmp_path, limits, reason):
    snapshot = make_snapshot(tmp_path / "input", [[1, 0]] * 4)
    root = tmp_path / "analysis"
    with pytest.raises(AnalysisRefused, match=reason):
        analyze_snapshot(snapshot, root, limits=limits)
    assert not list(root.rglob("manifest.json"))


def test_partial_snapshot_requires_explicit_upstream_acceptance(tmp_path):
    snapshot = make_snapshot(tmp_path / "input", [[1, 0], [0, 0]])
    with pytest.raises(AnalysisRefused, match="snapshot_partial"):
        analyze_snapshot(snapshot, tmp_path / "refused")
    from narrative_blueprint.corpus.snapshot import build_snapshot
    partial = tmp_path / "accepted-snapshot"
    build_snapshot(tmp_path / "input/source.csv", partial, allow_legacy_source=True, allow_partial=True)
    result = analyze_snapshot(partial, tmp_path / "analysis")
    assert result["counts"]["selected"] == 2 and result["counts"]["analyzed"] == 1
    excluded = rows(run_directory(tmp_path / "analysis", result) / "rejections.csv")
    assert excluded[0]["reason"] == "zero_vector"


def test_output_must_not_modify_snapshot_directory(tmp_path):
    snapshot = make_snapshot(tmp_path / "input", [[1, 0]])
    with pytest.raises(AnalysisRefused, match="output_inside_snapshot"):
        analyze_snapshot(snapshot, snapshot / "analysis")
