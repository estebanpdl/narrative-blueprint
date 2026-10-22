"""Exhaustive two-dimensional comparisons and seeded all-node Louvain."""

from dataclasses import asdict
import time

import networkx as nx
import numpy as np

from .contracts import AnalysisRefused, GraphParameters


def read_tile(stream, start, stop, dimension):
    stream.seek(start * dimension * 4)
    raw = stream.read((stop - start) * dimension * 4)
    if len(raw) != (stop - start) * dimension * 4:
        raise AnalysisRefused("scratch_vectors")
    vectors = np.frombuffer(raw, dtype="<f4").reshape(stop - start, dimension).astype(np.float64)
    vectors /= np.linalg.norm(vectors, axis=1)[:, None]
    return vectors


def discover_edges(scratch, nodes, dimension, parameters):
    budget = scratch.budget
    rows = budget.admit(nodes, dimension)
    count = comparisons = 0
    started = time.perf_counter()
    with scratch.vectors.open("rb") as stream:
        for first in range(0, nodes, rows):
            left = read_tile(stream, first, min(nodes, first + rows), dimension)
            for second in range(first, nodes, rows):
                budget.tick()
                right = read_tile(stream, second, min(nodes, second + rows), dimension)
                scores = left @ right.T
                np.clip(scores, -1.0, 1.0, out=scores)
                for a in range(len(left)):
                    begin = a + 1 if first == second else 0
                    accepted = []
                    for b in range(begin, len(right)):
                        comparisons += 1
                        weight = float(scores[a, b])
                        if weight > 0 and weight + parameters.tolerance >= parameters.threshold:
                            accepted.append((first + a, second + b, weight))
                    budget.admit_graph(nodes, count + len(accepted))
                    scratch.disk(65536 + 256 * len(accepted))
                    scratch.db.executemany("INSERT INTO edges VALUES (?,?,?)", accepted)
                    count += len(accepted)
                    budget.tick()
                scratch.db.commit()
                del right, scores
            del left
    if comparisons != nodes * (nodes - 1) // 2:
        raise AnalysisRefused("comparison_count")
    scratch.disk()
    return {"nodes": nodes, "edges": count, "comparisons": comparisons,
            "tile_rows": rows, "comparison_seconds": time.perf_counter() - started}


def cluster_graph(scratch, result, parameters):
    nodes, edges = result["nodes"], result["edges"]
    budget = scratch.budget
    estimates = budget.admit_graph(nodes, edges)
    started = time.perf_counter()
    graph = nx.Graph()
    graph.add_nodes_from(range(nodes))
    for index, (i, j, weight) in enumerate(scratch.db.execute("SELECT i,j,weight FROM edges ORDER BY i,j")):
        graph.add_edge(i, j, weight=weight)
        if index % 4096 == 0:
            budget.tick()
    budget.tick()
    # Direct cases avoid modularity division by zero and preserve all isolates.
    if not edges:
        groups = ({node} for node in range(nodes))
    else:
        groups = nx.community.louvain_communities(graph, weight="weight", seed=parameters.seed,
                                                resolution=parameters.resolution)
    budget.tick()
    community_count = isolates = 0
    for members in groups:
        label = min(members)
        for node in members:
            outcome = "isolated" if graph.degree(node) == 0 else "singleton" if len(members) == 1 else "assigned"
            isolates += outcome == "isolated"
            scratch.db.execute("UPDATE nodes SET community=?,outcome=? WHERE node=?", (label, outcome, node))
        community_count += 1
        budget.tick()
    scratch.db.commit()
    del graph, groups
    scratch.disk()
    return {**result, **estimates, "communities": community_count, "isolates": isolates,
            "clustering_seconds": time.perf_counter() - started,
            "parameters": asdict(parameters), "networkx_version": nx.__version__, "numpy_version": np.__version__,
            "node_order": "occurrence_id ascending (SQLite BINARY)",
            "edge_order": "canonical node index i,j ascending",
            "community_ids": "minimum canonical node index; run-local labels"}


def build_graph(scratch, manifest, parameters=None):
    parameters = parameters or GraphParameters()
    result = discover_edges(scratch, manifest["counts"]["valid"], manifest["dimension"], parameters)
    return cluster_graph(scratch, result, parameters)
