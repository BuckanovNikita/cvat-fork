"""No figures for what is not fully processed (GLOSSARY: Processed history).

A read of a period that is not fully processed keeps its envelope (`processed`, the legacy flags and what
each endpoint names besides: the overview its period and filter echo, the list its period and kind, the
details table its kind, page size and technical-account count) and carries no figures: every figure-bearing
field is null, not partial. A trend bucket that is not fully processed has null values the same way. The
legacy flags of such an answer describe only what is processed and can change once it all is
(docs/fork-specification.md, "Known limit of unprocessed periods"). Every endpoint that answers with figures nulls them
here, through `withhold`, after building its answer; a field added to an answer is withheld unless it is named
as envelope. A read whose answer is withheld whole is skipped (the overview's sections outside the envelope, the
list's hotkeys, the details table's rows); a read that also gives the legacy flags still runs, and so do the
trends' reads, whose points carry flags of their own. The overview withholds whole sections, so a field added to a section's rows (operation
parts on an overview row, say) is null with its section.
"""

from __future__ import annotations

from collections.abc import Collection

# What the cutover makes of the span (cutover.py): a flag, not a figure, so it stays in the envelope
LEGACY_FLAGS = frozenset({"legacy", "partly_legacy", "cutover", "shapes"})


def withhold(answer: dict, envelope: Collection[str]) -> dict:
    """`answer` with every field outside `envelope` set to null (a nested section or list goes as a whole)."""
    return {key: value if key in envelope else None for key, value in answer.items()}
