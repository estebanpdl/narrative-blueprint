"""Compatibility normalization and value-free alias diagnostics."""

from argparse import Action, ArgumentError
import sys

from .analysis_options import DiagnosticArgumentParser


class AliasValue(Action):
    """Accept equal duplicate values and refuse ambiguous destinations."""

    def __call__(self, parser, namespace, values, option_string=None):
        seen = getattr(namespace, "_alias_values", {})
        if self.dest in seen and seen[self.dest][1] != values:
            previous = seen[self.dest][0]
            raise ArgumentError(self, f"conflicting values for {previous} and {option_string}")
        seen[self.dest] = (option_string, values)
        setattr(namespace, "_alias_values", seen)
        setattr(namespace, self.dest, values)
        canonical = self.option_strings[0]
        if option_string != canonical:
            print(f"Deprecated option {option_string}; use {canonical}. Supported through 1.x.",
                  file=sys.stderr)


class CommandParser(DiagnosticArgumentParser):
    """Normalize legacy flat commands once, before normal argparse dispatch."""

    def parse_args(self, args=None, namespace=None):
        tokens = list(sys.argv[1:] if args is None else args)
        if tokens and tokens[0] == "embeddings" and (
            len(tokens) == 1 or tokens[1].startswith("-")
        ) and tokens[1:] not in (["--help"], ["-h"]):
            mode = "analyze" if "--analysis-only" in tokens[1:] else "compute"
            tokens = ["embeddings", mode, *[x for x in tokens[1:] if x != "--analysis-only"]]
            print(f"Deprecated flat embeddings command; use embeddings {mode}. Supported through 1.x.",
                  file=sys.stderr)
        parsed = super().parse_args(tokens, namespace)
        vars(parsed).pop("_alias_values", None)
        return parsed
