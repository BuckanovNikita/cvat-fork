"""GET overview: the figures of the overview page, one key per section.

Sections are the modules of the core's `overview`; each defines `KEY` and `build(request)`.
A period that is not fully processed keeps its period, filters, `processed` and the legacy flags in
`operations`; every other section, and every figure in `operations`, is null (withheld.py). The sections
outside that envelope are then not read; `operations` is, since its legacy flags come from its own read.
"""

from __future__ import annotations

from .. import overview
from ..overview import filters, operations, processed
from ..request import Request, discover
from ..withheld import LEGACY_FLAGS, withhold

PATH = "overview"

ENVELOPE = frozenset({"period", filters.KEY, processed.KEY, operations.KEY})


def handle(request: Request) -> dict:
    span = request.span()
    # the history state is read before any section reads figures (request.Request.history)
    whole = processed.build(request)
    body: dict = {"period": span.describe()}
    for section in discover(overview):
        # no figures for a period not fully processed: a section outside the envelope is not read at all
        body[section.KEY] = section.build(request) if whole or section.KEY in ENVELOPE else None
    if not whole:
        # whole sections are null, rows and all; `operations` keeps only its legacy flags
        body = withhold(body, ENVELOPE)
        body[operations.KEY] = withhold(body[operations.KEY], LEGACY_FLAGS)
    return body
