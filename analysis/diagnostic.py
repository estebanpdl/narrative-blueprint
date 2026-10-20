"""Small-input compatibility adapter; its graph results are diagnostic only."""

import hashlib
import json
from importlib.metadata import version
from pathlib import Path

from analysis.diagnostic_source import read_source
from analysis.embedding_analysis import EmbeddingAnalysis
from cli.analysis_options import effective_limits


WARNINGS = [
    "Legacy source: original generation completeness is unknown.",
    "Declared embedding space is user supplied, not verified provenance.",
    "Legacy graph drops isolates and collapses duplicate texts; it is not an occurrence graph.",
    "Legacy batch filtering is not corrected; bridge edges contaminate community statistics.",
    "Diagnostic results are not complete assignments or evidence of narrative validity.",
    "Working-byte admission is an estimate, not a process memory or runtime guarantee.",
]


class DiagnosticAnalysis(EmbeddingAnalysis):
    """Reuse only legacy graph methods; never initialize generation or storage."""

    def __init__(self):
        self.analysis_results = {"total_communities": 0, "communities": []}

    def _export_community_analysis(self):
        # Avoid unlinked Excel exports and repeated full text/vector pair rows.
        pass

    def _analyze_communities(self, graph, narratives):
        if graph.number_of_edges():
            super()._analyze_communities(graph, narratives)


def _write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def run_diagnostic(args):
    limits = effective_limits(args)
    documents, source = read_source(args["analysis_source"], limits)
    output = Path(args["output"])
    if output.exists():
        raise ValueError("Diagnostic output must be a new directory; choose a new --output")
    threshold = args.get("threshold", 0.75)
    print("DIAGNOSTIC ONLY: legacy compatibility analysis")
    for warning in WARNINGS:
        print("WARNING:", warning)
    print("Effective limits:", json.dumps(limits, sort_keys=True))
    print(f"Selected occurrences: {len(documents)}; "
          f"unique texts: {len({row['text_hash'] for row in documents})}")
    print("Source SHA256:", source["sha256"])

    output.mkdir(parents=True, exist_ok=False)
    status = {
        "schema_version": "diagnostic-1",
        "method_version": "legacy-two-pass-1",
        "status": "running",
        "corrected_analysis_complete": False,
        "generation_completeness": "unknown",
        "source": source,
        "declared_space": args["declared_space"],
        "provenance_verified": False,
        "limits": limits,
        "parameters": {"threshold": threshold, "louvain_seed": 42, "resolution": 1},
        "versions": {name: version(name) for name in ("numpy", "scikit-learn", "networkx")},
        "counts": {
            "selected_occurrences": len(documents),
            "valid_occurrences": len(documents),
            "unique_texts": len({row["text_hash"] for row in documents}),
            "missing_occurrences": None,
            "generation_failed_occurrences": None,
        },
        "warnings": WARNINGS,
        "outputs": {},
    }
    try:
        analysis = DiagnosticAnalysis()
        analysis.run_similarity_analysis(
            narratives=[row["text"] for row in documents],
            embeddings=[row["embedding"] for row in documents],
            threshold=threshold,
        )
        selection = [{key: value for key, value in row.items() if key != "embedding"}
                     for row in documents]
        communities = []
        for index, community in enumerate(analysis.analysis_results["communities"]):
            # Text hashes refer to groups of selected occurrences, not one-to-one
            # community assignments; legacy analysis has already discarded IDs.
            communities.append({
                "legacy_community_index": index,
                "legacy_size": community["size"],
                "text_hashes": sorted(hashlib.sha256(text.encode("utf-8")).hexdigest()
                                      for text in community["narratives"]),
                "legacy_incident_edge_count": len(community["edges"]),
                "legacy_mean_incident_similarity": float(community["avg_similarity"]),
            })
        for name, value in (("selection.json", selection),
                            ("legacy-communities.json", communities)):
            path = output / name
            _write_json(path, value)
            status["outputs"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        status["counts"]["legacy_communities"] = len(communities)
        status["counts"]["legacy_represented_unique_texts"] = len(
            {text_hash for group in communities for text_hash in group["text_hashes"]}
        )
        status["status"] = "diagnostic_complete"
    except Exception as exc:
        status["status"] = "failed"
        status["error"] = str(exc)
        _write_json(output / "diagnostic-status.json", status)
        raise
    # Written last; this only certifies completion of the labelled diagnostic.
    _write_json(output / "diagnostic-status.json", status)
    print(f"Output status: diagnostic_complete; {output / 'diagnostic-status.json'}")
    return status
