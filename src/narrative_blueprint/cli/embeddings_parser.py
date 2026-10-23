"""Separate options for generating vectors and analyzing stored vectors."""

from argparse import RawDescriptionHelpFormatter

from .analysis_options import ANALYSIS_EPILOG, add_analysis_options
from .compatibility import AliasValue


MODELS = ("text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002",
          "gemini-embedding-001")
TASK_TYPES = ("SEMANTIC_SIMILARITY", "CLASSIFICATION", "CLUSTERING", "RETRIEVAL_DOCUMENT",
              "RETRIEVAL_QUERY", "CODE_RETRIEVAL_QUERY", "QUESTION_ANSWERING", "FACT_VERIFICATION")


def _analysis_output(parser, diagnostic=False):
    group = parser.add_argument_group("Analysis output")
    group.add_argument("--analysis-dir", "-o", "--output", dest="output", action=AliasValue,
                       metavar="DIRECTORY", help=(
                           "Required analysis directory; snapshot runs create subdirectories; "
                           "the CSV diagnostic requires a new directory; no default" if diagnostic else
                           "Analysis directory; required unless --skip-analysis; no default"))
    group.add_argument("--threshold", type=float, default=0.75, metavar="SCORE",
                       help="Cosine threshold (default: 0.75); analyze requires finite (0, 1]")


def create_embeddings_parser(subparsers):
    parser = subparsers.add_parser(
        "embeddings", help="Compute vectors, validate snapshots or analyze similarities", allow_abbrev=False,
        epilog="Legacy flat options remain supported through 1.x. See docs/cli-compatibility.md.",
    )
    modes = parser.add_subparsers(dest="embedding_command", required=True, title="Embedding commands")
    compute = modes.add_parser("compute", help="Generate/store vectors; optionally run legacy analysis",
                               allow_abbrev=False)
    compute.set_defaults(analysis_only=False)
    inputs = compute.add_argument_group("Input")
    inputs.add_argument("--input", "--narrative-path", dest="narrative_path", action=AliasValue,
                        metavar="FILE", help="Required CSV/XLSX/JSON with uuid and narrative")
    inputs.add_argument("--max-input-bytes", type=int, default=256 * 1024**2,
                        help="Whole-file generation input admission (default 268435456); not streaming")
    inputs.add_argument("--max-input-records", type=int, default=1_000_000,
                        help="Generation row cap after loading (default 1000000)")
    inputs.add_argument("--generation-ledger", help="New SQLite outcome receipt; default unique file beside vector destination")
    provider = compute.add_argument_group("Provider")
    provider.add_argument("--model", choices=MODELS, default=None,
                          help="Compute default: text-embedding-3-small")
    provider.add_argument("--gemini-task-type", type=str.upper, choices=TASK_TYPES, default=None,
                          help="Gemini only; default SEMANTIC_SIMILARITY")
    vectors = compute.add_argument_group("Vector destination")
    vectors.add_argument("--vectors-file", "--embeddings-output", "--embedding-output",
                         dest="embeddings_output", action=AliasValue, metavar="FILE",
                         help="CSV/Parquet/DB/SQLite/SQLite3; conflicts with Mongo options")
    vectors.add_argument("--mongo-db-name", metavar="NAME")
    vectors.add_argument("--mongo-collection-name", metavar="NAME")
    _analysis_output(compute)
    compute.add_argument("--skip-analysis", action="store_true",
                         help="Compute/store only; no projector, similarity graph or Excel exports")

    analyze = modes.add_parser("analyze", help="Corrected snapshot analysis or legacy small-CSV diagnostic",
                               epilog=ANALYSIS_EPILOG, formatter_class=RawDescriptionHelpFormatter,
                               allow_abbrev=False)
    analyze.set_defaults(analysis_only=True)
    _analysis_output(analyze, diagnostic=True)
    add_analysis_options(analyze)
    from .graph_options import add_graph_options
    add_graph_options(analyze)
    from .snapshot_options import add_snapshot_parser
    add_snapshot_parser(modes)
    return parser
