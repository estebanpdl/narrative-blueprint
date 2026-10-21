"""Narrative Blueprint; package imports do not initialize providers."""

__all__ = ["NarrativeBlueprint"]


def __getattr__(name):
    if name == "NarrativeBlueprint":
        from .blueprint import NarrativeBlueprint
        return NarrativeBlueprint
    raise AttributeError(name)
