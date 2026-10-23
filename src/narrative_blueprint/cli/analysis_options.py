"""Options and validation for the provider-free diagnostic entry point."""

import math
from pathlib import Path
from argparse import ArgumentParser


class EmbeddingInputError(ValueError):
    """Invalid arguments or diagnostic admission refusal, suitable for CLI usage."""


# Hard ceilings keep the compatibility algorithm within a small-input envelope.
LIMITS = {
    "max_records": (100, 500),
    "max_dimension": (3072, 16384),
    "max_source_bytes": (4 * 1024**2, 16 * 1024**2),
    "max_pairs": (4950, 124750),
    "max_working_bytes": (64 * 1024**2, 256 * 1024**2),
}


VALUE_HINTS = {
    "--analysis-source": 'expects a local CSV path; example: --analysis-source subset.csv',
    "--declared-space": (
        'expects a quoted recipe label describing how vectors were generated '
        '(model, task type, and preprocessing if known); example: '
        '--declared-space "gemini-embedding-001 / CLUSTERING / original text". '
        'This is your declaration, not verified provenance'
    ),
    "--output": ('expects a directory path (new for --analysis-only); '
                 'example: --output results/diagnostic-01'),
}


class DiagnosticArgumentParser(ArgumentParser):
    """Add actionable value hints to embeddings syntax errors only."""

    def error(self, message):
        if " embeddings" in self.prog and "expected one argument" in message:
            for option, hint in VALUE_HINTS.items():
                if option in message:
                    message += f"\n{option} {hint}"
                    break
        super().error(message)


VALUE_HINTS["--source"] = 'expects a local CSV path; example: --source subset.csv'
VALUE_HINTS["--analysis-dir"] = 'expects an analysis directory path; example: --analysis-dir results/analysis-01'


ANALYSIS_EPILOG = '''Analysis-only example (no provider credentials needed):
  nblue embeddings analyze --source subset.csv --allow-legacy-source --analysis-dir results/diagnostic-01

Optional --declared-space LABEL records your unverified note; omitted means unknown.
--allow-legacy-source is required, even when model metadata is present.
Small CSV inputs only: hard ceilings 16 MiB source and 500 records; other limits also apply.
For input format, outputs, and a CSV-aware subset recipe, see docs/analysis-only.md.

Corrected global analysis of a validated snapshot:
  nblue embeddings analyze --snapshot-dir results/snapshot-01 --analysis-dir results/analysis
This snapshot route replaces the legacy graph for full analysis. It uses configurable
graph limits (default --max-working-bytes 2147483648), without the CSV diagnostic ceilings.
See docs/global-similarity.md and docs/analysis-limits.md.
'''


def add_analysis_options(parser):
    from .compatibility import AliasValue

    inputs = parser.add_argument_group("Legacy CSV diagnostic input (use --snapshot-dir for corrected analysis)")
    inputs.add_argument("--source", "--analysis-source", dest="analysis_source", action=AliasValue,
                        metavar="CSV", help="Required for the CSV diagnostic; conflicts with --snapshot-dir; "
                        "local UTF-8 CSV (uuid,text,embedding); no default")
    group = parser.add_argument_group("Legacy CSV diagnostic provenance")
    group.add_argument("--declared-space", metavar="LABEL",
                       help="Optional unverified note; default unknown/null; " + VALUE_HINTS["--declared-space"])
    group.add_argument("--allow-legacy-source", action="store_true",
                       help=("Required for the CSV diagnostic, not used with --snapshot-dir "
                             "(default: off; no value). Legacy CSV has no "
                             "expected-input manifest: acknowledge unknown generation completeness and "
                             "unverified provenance, even when model metadata is present"))
    meanings = {
        "max_records": ("N", "Maximum CSV data records; refuses excess rows, does not select first N"),
        "max_dimension": ("N", "Maximum numbers per embedding vector"),
        "max_source_bytes": ("BYTES", "Maximum whole CSV size in bytes (default 4 MiB, ceiling 16 MiB)"),
        "max_pairs": ("N", "Maximum possible pairs N*(N-1)/2, before threshold filtering"),
        "max_working_bytes": ("BYTES", "Maximum estimated working bytes (default 64 MiB, ceiling 256 MiB); not an RSS cap"),
    }
    group = parser.add_argument_group("Legacy CSV diagnostic limits (working allowance also applies to snapshots)")
    for name, (default, ceiling) in LIMITS.items():
        metavar, meaning = meanings[name]
        group.add_argument(
            "--" + name.replace("_", "-"), type=int, default=None, metavar=metavar,
            help=(f"CSV diagnostic: {meaning}; positive integer, default {default}, hard ceiling {ceiling}."
                  + (" Snapshot analysis: default 2147483648 (2 GiB), no fixed ceiling."
                     if name == "max_working_bytes" else "")),
        )


def effective_limits(args):
    limits = {}
    for name, (default, ceiling) in LIMITS.items():
        value = args.get(name)
        value = default if value is None else value
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= ceiling:
            raise EmbeddingInputError(f"--{name.replace('_', '-')} must be between 1 and {ceiling}")
        limits[name] = value
    return limits


def validate_embeddings_args(args):
    """Reject contradictory options before any storage or provider setup."""
    if args.get("snapshot_only"):
        from .snapshot_options import validate_snapshot_args
        validate_snapshot_args(args)
        return
    from .graph_options import graph_settings, reject_graph_options_without_snapshot
    if args.get("analysis_only") and args.get("snapshot_dir"):
        graph_settings(args)
        return
    reject_graph_options_without_snapshot(args)
    if not args.get("analysis_only"):
        for name in ("max_input_bytes", "max_input_records"):
            if type(args.get(name, 1)) is not int or args.get(name, 1) <= 0:
                raise EmbeddingInputError(f"--{name.replace('_', '-')} must be positive")
        diagnostic_options = ("analysis_source", "declared_space", "allow_legacy_source", *LIMITS)
        if any(args.get(name) is not None and args.get(name) is not False
               for name in diagnostic_options):
            raise EmbeddingInputError("Diagnostic options require --analysis-only (legacy) or embeddings analyze")
        if not args.get("narrative_path"):
            raise EmbeddingInputError("--input (--narrative-path) is required for embedding computation")
        if not args.get("skip_analysis") and not args.get("output"):
            raise EmbeddingInputError("--analysis-dir (--output) is required unless --skip-analysis is used")
        if args.get("gemini_task_type") and (args.get("model") or "text-embedding-3-small") != "gemini-embedding-001":
            raise EmbeddingInputError("--gemini-task-type can only be used with gemini-embedding-001")
        local = args.get("embeddings_output")
        mongo = (args.get("mongo_db_name"), args.get("mongo_collection_name"))
        if local:
            if any(mongo):
                raise EmbeddingInputError("--vectors-file cannot be combined with MongoDB arguments")
            if Path(local).suffix.lower() not in {".csv", ".parquet", ".db", ".sqlite", ".sqlite3"}:
                raise EmbeddingInputError("--vectors-file must use .csv, .parquet, .db, .sqlite or .sqlite3")
        elif not all(mongo):
            raise EmbeddingInputError("--vectors-file or both MongoDB destination options are required")
        return

    for name in ("narrative_path", "model", "gemini_task_type", "embeddings_output",
                 "mongo_db_name", "mongo_collection_name", "skip_analysis"):
        if args.get(name) is not None and args.get(name) is not False:
            raise EmbeddingInputError(
                f"--analysis-only cannot be combined with --{name.replace('_', '-')}"
            )
    for name in ("analysis_source", "output"):
        if not str(args.get(name) or "").strip():
            option = "--" + name.replace("_", "-")
            canonical = "--source" if name == "analysis_source" else "--analysis-dir"
            raise EmbeddingInputError(
                f"{canonical} ({option}) is required for embeddings analyze; {VALUE_HINTS[option]}"
            )
    if args.get("declared_space") is not None and not str(args["declared_space"]).strip():
        raise EmbeddingInputError("--declared-space must be nonblank when supplied; " + VALUE_HINTS["--declared-space"])
    if not args.get("allow_legacy_source"):
        raise EmbeddingInputError(
            "--allow-legacy-source is required: legacy CSV has no expected-input manifest, "
            "so generation completeness is unknown and provenance unverified. "
            "This acknowledgement takes no value; example: embeddings analyze --allow-legacy-source. "
            "Reported model metadata does not remove this requirement"
        )
    threshold = args.get("threshold", 0.75)
    if not math.isfinite(threshold) or not 0 < threshold <= 1:
        raise EmbeddingInputError("--threshold must be finite and in (0, 1]")
    effective_limits(args)
