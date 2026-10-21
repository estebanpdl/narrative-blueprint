"""Options and validation for the provider-free diagnostic entry point."""

import math
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
        if self.prog.endswith(" embeddings") and "expected one argument" in message:
            for option, hint in VALUE_HINTS.items():
                if option in message:
                    message += f"\n{option} {hint}"
                    break
        super().error(message)


ANALYSIS_EPILOG = '''Analysis-only example (no provider credentials needed):
  python main.py embeddings --analysis-only --analysis-source subset.csv --declared-space "gemini-embedding-001 / CLUSTERING / original text" --allow-legacy-source --output results/diagnostic-01

Use your actual recipe label; unknown details must remain unknown.
Both --declared-space LABEL and --allow-legacy-source are required.
Small CSV inputs only: hard ceilings 16 MiB source and 500 records; other limits also apply.
For input format, outputs, and a CSV-aware subset recipe, see docs/analysis-only.md.
'''


def add_analysis_options(parser):
    group = parser.add_argument_group("Offline diagnostic analysis")
    group.add_argument("--analysis-only", action="store_true",
                       help="Analyze a small stored CSV with the uncorrected legacy graph; no provider setup (default: off)")
    group.add_argument("--analysis-source", metavar="CSV",
                       help="Required with --analysis-only: local UTF-8 CSV (uuid,text,embedding); no default")
    group.add_argument("--declared-space", metavar="LABEL",
                       help="Required with --analysis-only; no default; " + VALUE_HINTS["--declared-space"])
    group.add_argument("--allow-legacy-source", action="store_true",
                       help=("Required with --analysis-only (default: off; no value). Legacy CSV has no "
                             "expected-input manifest: acknowledge unknown generation completeness and "
                             "unverified provenance, even when model metadata is present"))
    meanings = {
        "max_records": ("N", "Maximum CSV data records; refuses excess rows, does not select first N"),
        "max_dimension": ("N", "Maximum numbers per embedding vector"),
        "max_source_bytes": ("BYTES", "Maximum whole CSV size in bytes (default 4 MiB, ceiling 16 MiB)"),
        "max_pairs": ("N", "Maximum possible pairs N*(N-1)/2, before threshold filtering"),
        "max_working_bytes": ("BYTES", "Maximum estimated working bytes (default 64 MiB, ceiling 256 MiB); not an RSS cap"),
    }
    for name, (default, ceiling) in LIMITS.items():
        metavar, meaning = meanings[name]
        group.add_argument(
            "--" + name.replace("_", "-"), type=int, default=None, metavar=metavar,
            help=f"{meaning}; positive integer, default {default}, hard ceiling {ceiling}",
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
    if not args.get("analysis_only"):
        diagnostic_options = ("analysis_source", "declared_space", "allow_legacy_source", *LIMITS)
        if any(args.get(name) is not None and args.get(name) is not False
               for name in diagnostic_options):
            raise EmbeddingInputError("Diagnostic options require --analysis-only")
        if not args.get("narrative_path"):
            raise EmbeddingInputError("--narrative-path is required for embedding computation")
        return

    for name in ("narrative_path", "model", "gemini_task_type", "embeddings_output",
                 "mongo_db_name", "mongo_collection_name", "skip_analysis"):
        if args.get(name) is not None and args.get(name) is not False:
            raise EmbeddingInputError(
                f"--analysis-only cannot be combined with --{name.replace('_', '-')}"
            )
    for name in ("analysis_source", "output", "declared_space"):
        if not str(args.get(name) or "").strip():
            option = "--" + name.replace("_", "-")
            raise EmbeddingInputError(f"{option} is required with --analysis-only and {VALUE_HINTS[option]}")
    if not args.get("allow_legacy_source"):
        raise EmbeddingInputError(
            "--allow-legacy-source is required: legacy CSV has no expected-input manifest, "
            "so generation completeness is unknown and provenance unverified. "
            "This acknowledgement takes no value; example: --analysis-only --allow-legacy-source. "
            "Reported model metadata does not remove this requirement"
        )
    threshold = args.get("threshold", 0.75)
    if not math.isfinite(threshold) or not 0 < threshold <= 1:
        raise EmbeddingInputError("--threshold must be finite and in (0, 1]")
    effective_limits(args)
