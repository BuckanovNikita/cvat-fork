"""GET overview: the figures of the overview page, one key per section.

Sections are the modules of `team_analytics.overview`; each defines `KEY` and `build(request)`.
A period that is not fully processed keeps its period, filters, `processed` and the legacy flags in
`operations`; every other section, and every figure in `operations`, is null (withheld.py).
"""

from __future__ import annotations

from team_analytics import overview
from team_analytics.overview import filters, operations, processed
from team_analytics.service import Request, discover
from team_analytics.withheld import LEGACY_FLAGS, withhold

PATH = "overview"

ENVELOPE = frozenset({"period", filters.KEY, processed.KEY, operations.KEY})


def handle(request: Request) -> dict:
    span = request.span()
    body: dict = {"period": span.describe()}
    for section in discover(overview):
        body[section.KEY] = section.build(request)
    if not body[processed.KEY]:
        # no figures for a period not fully processed: whole sections go null, rows and all
        body = withhold(body, ENVELOPE)
        body[operations.KEY] = withhold(body[operations.KEY], LEGACY_FLAGS)
    return body
