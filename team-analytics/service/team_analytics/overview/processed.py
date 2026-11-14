"""Whether every hour of the requested period is processed. When it is not, the figures beside it are partial:
the page shows none of them (a period is offered only when all of it is processed). The history state is the
request's one reading (service.Request.history), which the overview takes before any section reads figures."""

from __future__ import annotations

from team_analytics.service import Request

KEY = "processed"


def build(request: Request) -> bool:
    return request.history().covers(request.span().start)
