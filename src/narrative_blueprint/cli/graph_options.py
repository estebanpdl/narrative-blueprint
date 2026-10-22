"""Corrected analysis of an existing validated snapshot, without providers."""

from dataclasses import asdict
import json

from narrative_blueprint.analysis.threshold.contracts import AnalysisRefused, GraphLimits, GraphParameters


def add_graph_options(parser):
    group = parser.add_argument_group("Corrected global analysis (snapshot input)")
    group.add_argument("--snapshot-dir", help="Completed snapshot input; replaces --source legacy diagnostic")
    group.add_argument("--tolerance", type=float, help="Numeric boundary/oracle tolerance, no threshold expansion; default 1e-7")
    group.add_argument("--resolution", type=float, help="Weighted Louvain resolution; default 1.0")
    group.add_argument("--seed", type=int, help="Weighted Louvain seed; default 42")
    group.add_argument("--excel-view", action="store_true", help="Optional capped literal-text workbook")
    group.add_argument("--projector-view", action="store_true", help="Optional capped aligned vector/metadata TSVs")
    limits = parser.add_argument_group("Corrected graph limits (with --snapshot-dir, no fixed ceilings)")
    for name, default in asdict(GraphLimits()).items():
        if name == "max_working_bytes":
            continue  # Shared spelling with the compatibility diagnostic.
        limits.add_argument("--" + name.replace("_", "-"), type=float if name == "max_seconds" else int,
                            help=f"Snapshot analysis default {default}; refuses excess")


def graph_settings(args):
    if not args.get("snapshot_dir") or not args.get("output"):
        raise AnalysisRefused("required_paths", "--snapshot-dir and --analysis-dir are required")
    for name in ("analysis_source", "allow_legacy_source", "declared_space", "max_records", "max_dimension", "max_source_bytes", "max_pairs",
                 "narrative_path", "model", "gemini_task_type", "embeddings_output", "mongo_db_name", "mongo_collection_name", "skip_analysis"):
        if args.get(name) is not None and args.get(name) is not False:
            raise AnalysisRefused("conflicting_option", f"--snapshot-dir cannot be combined with --{name.replace('_', '-')}")
    parameters = GraphParameters(**{key: args.get(key) if args.get(key) is not None else value
                                    for key, value in asdict(GraphParameters()).items()})
    limits = GraphLimits(**{key: args.get(key) if args.get(key) is not None else value
                           for key, value in asdict(GraphLimits()).items()})
    return parameters, limits


def reject_graph_options_without_snapshot(args):
    names = [name for name in asdict(GraphLimits()) if name != "max_working_bytes"]
    names += ["tolerance", "resolution", "seed", "excel_view", "projector_view"]
    if any(args.get(name) is not None and args.get(name) is not False for name in names):
        raise AnalysisRefused("snapshot_required", "corrected graph options require --snapshot-dir")


def run_graph(args):
    from narrative_blueprint.analysis.threshold.pipeline import analyze_snapshot
    parameters, limits = graph_settings(args)
    manifest = analyze_snapshot(args["snapshot_dir"], args["output"], parameters=parameters, limits=limits,
                                excel=args.get("excel_view", False), projector=args.get("projector_view", False))
    print(json.dumps({key: manifest[key] for key in ("run_id", "status", "counts", "timings")}, indent=2))
