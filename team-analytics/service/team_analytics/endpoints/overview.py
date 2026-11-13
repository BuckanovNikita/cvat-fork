"""GET overview: the figures of the overview page, one key per section.

Sections are the modules of `team_analytics.overview`; each defines `KEY` and `build(request)`.
"""

from __future__ import annotations

from team_analytics import overview
from team_analytics.service import Request, discover

PATH = "overview"


def handle(request: Request) -> dict:
    span = request.span()
    body: dict = {"period": span.describe()}
    for section in discover(overview):
        body[section.KEY] = section.build(request)
    return body
