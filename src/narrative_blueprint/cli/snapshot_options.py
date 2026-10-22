"""Options for provider-free snapshot validation without graph computation."""

from dataclasses import asdict
import json

from narrative_blueprint.corpus.contracts import SnapshotLimits, SnapshotRefused


def add_snapshot_parser(modes):
    parser = modes.add_parser("snapshot", help="Validate stored vectors into a disk-backed snapshot",
                              allow_abbrev=False)
    parser.set_defaults(snapshot_only=True)
    parser.add_argument("--source", required=True, help="Read-only CSV, Parquet or SQLite source")
    parser.add_argument("--snapshot-dir", required=True, help="New output directory; never overwritten")
    parser.add_argument("--generation-ledger", help="Expected-input receipt from embeddings compute")
    parser.add_argument("--allow-legacy-source", action="store_true", help="Accept unknown original generation coverage")
    parser.add_argument("--allow-partial", action="store_true", help="Explicitly accept incomplete generation and validation exclusions")
    parser.add_argument("--declared-space", help="Optional unverified note; does not replace source recipe")
    group = parser.add_argument_group("Snapshot limits (positive integers, no fixed hard ceilings)")
    for name, default in asdict(SnapshotLimits()).items():
        group.add_argument("--" + name.replace("_", "-"), type=int, default=default,
                           help=f"Default {default}; refuses excess, never truncates selection")
    return parser


def validate_snapshot_args(args):
    limits = SnapshotLimits(**{key: args.get(key, value) for key, value in asdict(SnapshotLimits()).items()})
    if not args.get("source") or not args.get("snapshot_dir"):
        raise SnapshotRefused("required_paths", "--source and --snapshot-dir are required")
    if args.get("declared_space") is not None and not args["declared_space"].strip():
        raise SnapshotRefused("invalid_declaration")
    if not args.get("generation_ledger") and not args.get("allow_legacy_source"):
        raise SnapshotRefused("legacy_acknowledgement", "--allow-legacy-source is required without a ledger")
    return limits


def run_snapshot(args):
    from narrative_blueprint.corpus.snapshot import build_snapshot
    result = build_snapshot(
        args["source"], args["snapshot_dir"], limits=validate_snapshot_args(args),
        generation_ledger=args.get("generation_ledger"),
        allow_partial=args.get("allow_partial", False),
        allow_legacy_source=args.get("allow_legacy_source", False),
        declared_space=args.get("declared_space"),
    )
    print(json.dumps({key: result[key] for key in ("status", "counts", "generation_coverage", "duration_seconds")}, indent=2))
