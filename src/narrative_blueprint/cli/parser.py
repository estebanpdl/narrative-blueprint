"""Root parser for independent blueprint and embedding workflows."""

from .blueprint_parser import create_blueprint_parser
from .embeddings_parser import create_embeddings_parser
from .compatibility import CommandParser


def create_main_parser(prog="nblue"):
    parser = CommandParser(prog=prog, description="Narrative Blueprint Analysis", allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True, title="Commands")
    create_blueprint_parser(commands)
    create_embeddings_parser(commands)
    return parser


parser = create_main_parser()
