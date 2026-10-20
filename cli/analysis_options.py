"""Options and validation for the provider-free diagnostic entry point."""

import math


# Hard ceilings keep the compatibility algorithm within a small-input envelope.
LIMITS = {
    "max_records": (100, 500),
    "max_dimension": (3072, 16384),
    "max_source_bytes": (4 * 1024**2, 16 * 1024**2),
    "max_pairs": (4950, 124750),
    "max_working_bytes": (64 * 1024**2, 256 * 1024**2),
}


def add_analysis_options(parser):
    group = parser.add_argument_group("Offline diagnostic analysis")
    group.add_argument("--analysis-only", action="store_true",
                       help="Analyze a small stored CSV without provider setup")
    group.add_argument("--analysis-source",
                       help="Explicit local CSV source (uuid,text,embedding)")
    group.add_argument("--declared-space",
                       help="User-declared embedding recipe; not verified provenance")
    group.add_argument("--allow-legacy-source", action="store_true",
                       help="Accept unknown generation completeness and provenance")
    for name, (default, ceiling) in LIMITS.items():
        group.add_argument(
            "--" + name.replace("_", "-"), type=int, default=None,
            help=f"Diagnostic limit; default {default}, hard ceiling {ceiling}",
        )


def effective_limits(args):
    limits = {}
    for name, (default, ceiling) in LIMITS.items():
        value = args.get(name)
        value = default if value is None else value
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= ceiling:
            raise ValueError(f"--{name.replace('_', '-')} must be between 1 and {ceiling}")
        limits[name] = value
    return limits


def validate_embeddings_args(args):
    """Reject contradictory options before any storage or provider setup."""
    if not args.get("analysis_only"):
        diagnostic_options = ("analysis_source", "declared_space", "allow_legacy_source", *LIMITS)
        if any(args.get(name) is not None and args.get(name) is not False
               for name in diagnostic_options):
            raise ValueError("Diagnostic options require --analysis-only")
        if not args.get("narrative_path"):
            raise ValueError("--narrative-path is required for embedding computation")
        return

    for name in ("narrative_path", "model", "gemini_task_type", "embeddings_output",
                 "mongo_db_name", "mongo_collection_name", "skip_analysis"):
        if args.get(name) is not None and args.get(name) is not False:
            raise ValueError(
                f"--analysis-only cannot be combined with --{name.replace('_', '-')}"
            )
    for name in ("analysis_source", "output", "declared_space"):
        if not str(args.get(name) or "").strip():
            raise ValueError(f"--{name.replace('_', '-')} is required with --analysis-only")
    if not args.get("allow_legacy_source"):
        raise ValueError("--allow-legacy-source is required: generation completeness is unknown")
    threshold = args.get("threshold", 0.75)
    if not math.isfinite(threshold) or not 0 < threshold <= 1:
        raise ValueError("--threshold must be finite and in (0, 1]")
    effective_limits(args)
