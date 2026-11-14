"""No figures for what is not fully processed (GLOSSARY: Processed history).

A read of a period that is not fully processed keeps its envelope (the period, the filter echo, `processed`
and the legacy flags) and carries no figures: every figure-bearing field is null, not partial. A trend bucket
that is not fully processed has null values the same way. Every endpoint that answers with figures nulls them
here, through `withhold`, after building its answer as usual; a field added to an answer is withheld unless it
is named as envelope. The overview withholds whole sections, so a field added to a section's rows (operation
parts on an overview row, say) is null with its section.
"""

from __future__ import annotations

from collections.abc import Collection

# What the cutover makes of the span (cutover.py): a flag, not a figure, so it stays in the envelope
LEGACY_FLAGS = frozenset({"legacy", "partly_legacy", "cutover", "shapes"})


def withhold(answer: dict, envelope: Collection[str]) -> dict:
    """`answer` with every field outside `envelope` set to null (a nested section or list goes as a whole)."""
    return {key: value if key in envelope else None for key, value in answer.items()}
