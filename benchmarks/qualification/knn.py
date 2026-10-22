"""Bounded exact-kNN experiment; never selected by production analysis."""

from contextlib import closing
import csv
import json
import sqlite3
import time

import networkx as nx
import numpy as np
from sklearn.metrics import adjusted_rand_score

from narrative_blueprint.analysis.threshold.contracts import GraphParameters
from narrative_blueprint.analysis.threshold.pipeline import analyze_snapshot
from narrative_blueprint.corpus.snapshot import build_snapshot
from .measurement import Measurement, environment


CASES = ("groups", "identical", "circle", "boundary")


def normalized(vectors, dtype):
    result = np.asarray(vectors, dtype=dtype).copy()
    result /= np.linalg.norm(result, axis=1)[:, None]
    return result


def exact_knn(vectors, ids, k, floor, symmetry, *, dtype=np.float64, rows=64):
    """All candidates scored; descending score then stable-ID ties, no self.

    This qualification-only kernel intentionally caps N and dimensions. It uses
    the existing NumPy dependency and bounded score rows, not an ANN index.
    """
    n, d = np.shape(vectors)
    if n > 5000 or d > 4096 or not 0 < floor <= 1 or k < 1 or rows < 1:
        raise ValueError("Exact-kNN experiment limits exceeded")
    if n * min(k, max(0, n - 1)) > 1_000_000:
        raise ValueError("Exact-kNN directed candidate budget exceeded")
    if symmetry not in {"union", "mutual"} or len(set(ids)) != n:
        raise ValueError("Unique stable IDs and union/mutual symmetry required")
    order = np.argsort(np.asarray(ids), kind="stable")
    vectors = normalized(np.asarray(vectors)[order], dtype)
    identities = [ids[i] for i in order]
    directed = {}
    candidate_ids = np.arange(n)
    for start in range(0, n, rows):
        scores = np.clip(vectors[start:start + rows] @ vectors.T, -1, 1)
        for offset, score in enumerate(scores):
            i = start + offset
            score[i] = -np.inf
            # Full sort makes ties at k explicit; argpartition alone does not.
            ranked = np.lexsort((candidate_ids, -score))[:min(k, n - 1)]
            directed.update(((i, int(j)), float(score[j])) for j in ranked if score[j] >= floor)
    edges = {}
    for (i, j), weight in directed.items():
        if symmetry == "union" or (j, i) in directed:
            key = tuple(sorted((identities[i], identities[j])))
            edges[key] = max(weight, edges.get(key, -1.0))
    return edges


def threshold_edges(vectors, ids, floor, dtype=np.float64):
    vectors = normalized(vectors, dtype)
    scores = np.clip(vectors @ vectors.T, -1, 1)
    return {(ids[i], ids[j]): float(scores[i, j]) for i in range(len(ids))
            for j in range(i + 1, len(ids)) if scores[i, j] >= floor}


def partition(ids, edges):
    graph = nx.Graph()
    graph.add_nodes_from(sorted(ids))
    for (a, b), weight in sorted(edges.items()):
        graph.add_edge(a, b, weight=weight)
    groups = nx.community.louvain_communities(graph, seed=42, resolution=1) if edges else [{i} for i in sorted(ids)]
    memberships = {node: frozenset(group) for group in groups for node in group}
    labels = {node: min(group) for group in groups for node in group}
    return [labels[i] for i in sorted(ids)], memberships, len(groups)


def compare_case(case, root):
    rng = np.random.default_rng(42)
    if case == "groups":
        vectors = np.repeat(rng.normal(size=(10, 32)), 50, axis=0)
    elif case == "identical":
        vectors = np.ones((128, 16))
    elif case == "circle":
        angles = np.linspace(0, 2 * np.pi, 400, endpoint=False)
        vectors = np.column_stack((np.cos(angles), np.sin(angles)))
    else:
        cosines = np.array([0.75 + delta for delta in (-1e-6, -5e-8, -1e-8, 0, 1e-8, 5e-8, 1e-6)])
        vectors = np.vstack(([1., 0.], np.column_stack((cosines, np.sqrt(1 - cosines**2)))))
    ids = [f"id-{i:08}" for i in range(len(vectors))]
    source = root / "synthetic.csv"
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("uuid", "occurrence_id", "text", "embedding"))
        writer.writerows((identity, identity, "synthetic", json.dumps(vector.tolist())) for identity, vector in zip(ids, vectors))
    with Measurement(root) as meter:
        with meter.stage("total"):
            build_snapshot(source, root / "snapshot", allow_legacy_source=True)
            reference = analyze_snapshot(root / "snapshot", root / "analysis", parameters=GraphParameters())
            with closing(sqlite3.connect(root / "snapshot/corpus.sqlite")) as db:
                vectors = np.array([np.frombuffer(row[0], dtype="<f4") for row in
                                    db.execute("SELECT vector FROM records ORDER BY occurrence_id")])
            with (root / "analysis" / ("run-" + reference["run_id"]) / "edges.csv").open(newline="", encoding="utf-8") as stream:
                baseline = {(row["source_occurrence_id"], row["target_occurrence_id"]): float(row["cosine"])
                            for row in csv.DictReader(stream)}
            labels, membership, communities = partition(ids, baseline)
            reference32 = threshold_edges(vectors, ids, .75, np.float32)
            labels32, _, _ = partition(ids, reference32)
            permutation = rng.permutation(len(ids))
            trials = []
            for k in (5, 20, 50):
                for symmetry in ("union", "mutual"):
                    started = time.perf_counter()
                    edges = exact_knn(vectors, ids, k, .75, symmetry)
                    elapsed = time.perf_counter() - started
                    clustering_started = time.perf_counter()
                    candidate_labels, candidate_membership, candidate_count = partition(ids, edges)
                    clustering_seconds = time.perf_counter() - clustering_started
                    permuted = exact_knn(vectors[permutation], [ids[i] for i in permutation], k, .75, symmetry)
                    permuted_labels, _, _ = partition(ids, permuted)
                    float32 = exact_knn(vectors, ids, k, .75, symmetry, dtype=np.float32)
                    float32_labels, _, _ = partition(ids, float32)
                    trials.append({"k": k, "floor": .75, "symmetry": symmetry, "edges": len(edges),
                        "density": len(edges) / (len(ids) * (len(ids) - 1) / 2),
                        "missed_threshold_pairs": len(baseline.keys() - edges.keys()),
                        "extra_threshold_pairs": len(edges.keys() - baseline.keys()),
                        "communities": candidate_count, "adjusted_rand_index": adjusted_rand_score(labels, candidate_labels),
                        "changed_membership_nodes": sum(membership[i] != candidate_membership[i] for i in ids),
                        "selection_seconds": elapsed, "clustering_seconds": clustering_seconds,
                        "permutation_edge_difference": len(edges.keys() ^ permuted.keys()),
                        "permutation_assignment_ari": adjusted_rand_score(candidate_labels, permuted_labels),
                        "float32_edge_difference": len(edges.keys() ^ float32.keys()),
                        "float32_assignment_ari": adjusted_rand_score(candidate_labels, float32_labels)})
    return {"case": case, "status": "complete", "nodes": len(ids), "dimension": vectors.shape[1],
            "edges": len(baseline), "communities": communities, "reference_method": reference["method"],
            "reference_comparison_seconds": reference["graph"]["comparison_seconds"],
            "reference_analysis_seconds": reference["timings"]["total_seconds"],
            "knn_score_rows": 64, "knn_directed_comparisons": len(ids) * (len(ids) - 1),
            "tie_order": "descending computed cosine, then stable occurrence ID ascending; self excluded",
            "threshold_float32_edge_difference": len(baseline.keys() ^ reference32.keys()),
            "threshold_float32_assignment_ari": adjusted_rand_score(labels, labels32),
            "trials": trials, "stages": meter.stages, "sampling_errors": meter.errors, "environment": environment()}
