"""Dense-oracle, occurrence, deterministic ordering and admission contracts."""

import csv
from dataclasses import replace
import json

import networkx as nx
import numpy as np
import pytest

from narrative_blueprint.corpus.snapshot import build_snapshot
from narrative_blueprint.analysis.threshold.contracts import (
    AnalysisRefused, Budget, GraphLimits, GraphParameters, tile_bytes,
)
from narrative_blueprint.analysis.threshold.graph import build_graph
from narrative_blueprint.analysis.threshold.snapshot_input import Scratch, open_snapshot


def make_snapshot(root, vectors, ids=None, texts=None):
    root.mkdir(parents=True, exist_ok=True)
    source = root / "source.csv"
    ids = ids or [f"occurrence-{i:04}" for i in range(len(vectors))]
    texts = texts or [f"synthetic {i}" for i in range(len(vectors))]
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("uuid", "occurrence_id", "text", "embedding", "provider", "model_name"))
        for index, (identity, text, vector) in enumerate(zip(ids, texts, vectors)):
            writer.writerow((f"{index:04}", identity, text, json.dumps(vector), "synthetic", "fixture"))
    build_snapshot(source, root / "snapshot", allow_legacy_source=True)
    return root / "snapshot"


def analyze_core(root, vectors, *, ids=None, texts=None, limits=None, parameters=None):
    snapshot = make_snapshot(root, vectors, ids, texts)
    work = root / "scratch"
    work.mkdir()
    budget = Budget(limits)
    with open_snapshot(snapshot, budget) as (db, manifest, _):
        scratch = Scratch(work, budget)
        try:
            scratch.stage_nodes(db, manifest)
            result = build_graph(scratch, manifest, parameters)
            edges = list(scratch.db.execute('''SELECT a.occurrence_id,b.occurrence_id,e.weight
                FROM edges e JOIN nodes a ON a.node=e.i JOIN nodes b ON b.node=e.j ORDER BY e.i,e.j'''))
            nodes = list(scratch.db.execute("SELECT occurrence_id,community,outcome FROM nodes ORDER BY node"))
            return result, edges, nodes
        finally:
            scratch.close()


@pytest.mark.parametrize("dimension,rows", [(2, 1), (3, 2), (17, 4), (129, 5)])
def test_tiled_matches_independent_dense_oracle(tmp_path, dimension, rows):
    vectors = np.random.default_rng(1977).normal(size=(19, dimension))
    vectors[13] = vectors[0]
    parameters = GraphParameters(threshold=0.43)
    result, edges, nodes = analyze_core(tmp_path, vectors.tolist(), limits=GraphLimits(max_tile_rows=rows), parameters=parameters)
    normalized = vectors / np.linalg.norm(vectors, axis=1)[:, None]
    dense = normalized @ normalized.T
    expected = {(f"occurrence-{i:04}", f"occurrence-{j:04}"): dense[i, j]
                for i in range(19) for j in range(i + 1, 19)
                if dense[i, j] + parameters.tolerance >= parameters.threshold}
    assert {(a, b) for a, b, _ in edges} == expected.keys()
    for a, b, weight in edges:
        assert abs(weight - expected[a, b]) < 1e-7
    assert len(nodes) == 19 and result["comparisons"] == 171
    assert result["tile_rows"] == rows


def test_cross_block_only_match_duplicates_and_isolate(tmp_path):
    result, edges, nodes = analyze_core(tmp_path, [[1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 0]],
        texts=["repeated", "other", "isolated", "repeated"], limits=GraphLimits(max_tile_rows=2))
    assert [(a, b) for a, b, _ in edges] == [("occurrence-0000", "occurrence-0003")]
    assert result["nodes"] == 4 and result["isolates"] == 2 and result["communities"] == 3
    assert nodes[0][1] == nodes[3][1] and nodes[2][2] == "isolated"


def test_boundary_tolerance_and_positive_edges(tmp_path):
    cosines = [0.6 - 2e-6, 0.6 - 3e-7, 0.6, 0.6 + 2e-6, 0.0, -0.1]
    vectors = [[1., 0.]] + [[value, (1 - value**2)**0.5] for value in cosines]
    _, edges, _ = analyze_core(tmp_path, vectors, parameters=GraphParameters(threshold=0.6, tolerance=1e-6))
    linked = {b for a, b, _ in edges if a == "occurrence-0000"}
    assert linked == {"occurrence-0002", "occurrence-0003", "occurrence-0004"}
    assert all(weight > 0 for _, _, weight in edges)


def test_permutation_and_tile_size_preserve_ties_and_memberships(tmp_path):
    vectors = [[1, 0], [1, 0], [0.8, 0.6], [0, 1], [0, 1], [-1, 0]]
    ids = [f"node-{i}" for i in range(6)]
    first = analyze_core(tmp_path / "a", vectors, ids=ids, limits=GraphLimits(max_tile_rows=1))
    order = [4, 2, 5, 0, 3, 1]
    second = analyze_core(tmp_path / "b", [vectors[i] for i in order], ids=[ids[i] for i in order], limits=GraphLimits(max_tile_rows=3))
    assert first[1] == second[1]
    assert first[2] == second[2]
    assert first[0]["parameters"]["seed"] == 42
    assert first[0]["networkx_version"] == nx.__version__


@pytest.mark.parametrize("vectors", [[], [[1, 0]], [[1, 0], [0, 1], [-1, 0]]])
def test_empty_singleton_and_no_edges_bypass_louvain(tmp_path, monkeypatch, vectors):
    monkeypatch.setattr(nx.community, "louvain_communities", lambda *a, **k: pytest.fail("Louvain on edgeless graph"))
    result, edges, nodes = analyze_core(tmp_path, vectors)
    assert not edges and len(nodes) == result["communities"] == len(vectors)
    assert all(node[2] == "isolated" for node in nodes)


@pytest.mark.parametrize("name,value", [("max_nodes", 2), ("max_edges", 2), ("max_comparisons", 2),
    ("max_tile_bytes", 100), ("max_graph_bytes", 100), ("max_clustering_bytes", 100),
    ("max_working_bytes", 100), ("max_disk_bytes", 100), ("max_seconds", 1e-12),
    ("max_snapshot_bytes", 100), ("max_record_bytes", 100)])
def test_each_core_limit_refuses_without_changing_policy(tmp_path, name, value):
    with pytest.raises(AnalysisRefused, match=name):
        analyze_core(tmp_path, [[1, 0]] * 4, limits=replace(GraphLimits(), **{name: value}))


def test_high_dimension_derives_smaller_tiles_and_refuses_one_vector(tmp_path):
    budget = Budget(GraphLimits(max_tile_bytes=tile_bytes(2, 300)))
    assert budget.admit(10, 300) == 2
    with pytest.raises(AnalysisRefused, match="max_tile_bytes"):
        budget.admit(10, 10000)


def test_dense_graph_refused_before_networkx_conversion(tmp_path, monkeypatch):
    monkeypatch.setattr(nx, "Graph", lambda: pytest.fail("Graph allocated after edge refusal"))
    with pytest.raises(AnalysisRefused, match="max_edges"):
        analyze_core(tmp_path, [[1, 0]] * 8, limits=GraphLimits(max_edges=4))


def test_snapshot_tampering_and_hot_journal_refused(tmp_path):
    snapshot = make_snapshot(tmp_path, [[1, 0]])
    journal = snapshot / "corpus.sqlite-journal"
    journal.write_bytes(b"active")
    with pytest.raises(AnalysisRefused, match="snapshot_active"):
        with open_snapshot(snapshot, Budget()):
            pytest.fail("admitted active snapshot")
    journal.unlink()
    with (snapshot / "corpus.sqlite").open("ab") as stream:
        stream.write(b"tampered")
    with pytest.raises(AnalysisRefused, match="snapshot_checksum"):
        with open_snapshot(snapshot, Budget()):
            pytest.fail("admitted changed snapshot")


@pytest.mark.parametrize("kwargs", [{"threshold": 0}, {"threshold": float("nan")}, {"tolerance": -1},
    {"tolerance": 1}, {"resolution": 0}, {"seed": -1}])
def test_numeric_policy_validation(kwargs):
    with pytest.raises(AnalysisRefused):
        GraphParameters(**kwargs)
