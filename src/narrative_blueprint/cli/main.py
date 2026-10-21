"""Shared dispatcher for console, module and source-checkout launchers."""

import time

from .analysis_options import EmbeddingInputError, validate_embeddings_args
from .parser import create_main_parser


def main(argv=None, *, prog="nblue"):
    parser = create_main_parser(prog=prog)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    args.pop("embedding_command", None)
    try:
        if command == "embeddings":
            validate_embeddings_args(args)
            from narrative_blueprint.runners.embeddings_runner import handle_embeddings
            handler = handle_embeddings
        else:
            if not args.get("output") and not (
                args.get("mongo_db_name") and args.get("mongo_collection_name")
            ):
                raise EmbeddingInputError(
                    "--result-file or both --mongo-db-name and --mongo-collection-name are required"
                )
            from narrative_blueprint.runners.blueprint_runner import handle_blueprint
            handler = handle_blueprint
        print(f"\n> Starting program at: {time.ctime()}\n")
        handler(args)
    except EmbeddingInputError as exc:
        parser.error(str(exc))
    print(f"\n> Ending program at: {time.ctime()}")
