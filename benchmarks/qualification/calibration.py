"""Measure NetworkX conversion and seeded Louvain on synthetic graph shapes."""

import gc
import random

import networkx as nx

from .measurement import Measurement, environment


CASES = {
    "isolates": (10000, 0),
    "sparse": (3000, 20),
    "groups": (3000, 100),
    "dense-500": (500, 500),
    "dense-1000": (1000, 1000),
    "dense-1500": (1500, 1500),
}


def calibrate(case, root):
    nodes, width = CASES[case]
    gc.collect()
    with Measurement(root) as meter:
        with meter.stage("total"):
            with meter.stage("conversion"):
                graph = nx.Graph()
                graph.add_nodes_from(range(nodes))
                rng = random.Random(42)
                for i in range(nodes):
                    if case == "sparse":
                        targets = sorted(rng.sample(range(i + 1, nodes), min(width, nodes - i - 1)))
                    else:
                        targets = range(i + 1, min(nodes, (i // width + 1) * width)) if width else ()
                    for j in targets:
                        # Match SQLite's fresh integer/float objects at conversion.
                        graph.add_edge(int(str(i)), int(str(j)), weight=float("0.9"))
                edges = graph.number_of_edges()
            with meter.stage("louvain"):
                groups = nx.community.louvain_communities(graph, seed=42, resolution=1) if edges else list(nx.connected_components(graph))
            communities = len(groups)
    return {"case": case, "nodes": nodes, "edges": edges, "communities": communities,
            "density": edges / (nodes * (nodes - 1) / 2), "stages": meter.stages,
            "sampling_errors": meter.errors, "environment": environment()}
