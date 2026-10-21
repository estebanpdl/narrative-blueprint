"""Options for structured blueprint generation."""

from .compatibility import AliasValue


def create_blueprint_parser(subparsers):
    parser = subparsers.add_parser(
        "blueprint", help="Generate structured blueprints using a provider",
        description="Generate blueprints from text and an explicit TOML prompt template.",
        allow_abbrev=False,
    )
    inputs = parser.add_argument_group("Input")
    inputs.add_argument("--input", "--narrative-path", dest="narrative_path", action=AliasValue,
                        required=True, metavar="FILE", help="CSV/XLSX/JSON with uuid and narrative")
    inputs.add_argument("--prompt-template", required=True, metavar="TOML",
                        help="Explicit file with [system] and [message] prompt fields")
    inputs.add_argument("--sample-size", type=int, default=None, metavar="N",
                        help="Legacy prefix slice; omitted or zero processes all rows")
    provider = parser.add_argument_group("Provider")
    provider.add_argument("--model", default="gpt-4o-mini", metavar="MODEL",
                          help="Blueprint model (default: gpt-4o-mini)")
    output = parser.add_argument_group("Result destination")
    output.add_argument("--result-file", "--output", dest="output", action=AliasValue,
                        metavar="JSON", help="JSON destination; takes precedence over Mongo options")
    output.add_argument("--mongo-db-name", metavar="NAME")
    output.add_argument("--mongo-collection-name", metavar="NAME")
    return parser
