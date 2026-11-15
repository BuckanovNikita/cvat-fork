"""Whether every hour of the requested period is processed. When it is not, the figures beside it are partial:
the page shows none of them (a period is offered only when all of it is processed). The history state is the
request's one reading (request.Request.history), which the overview takes before any section reads figures.
"""

from __future__ import annotations

from ..request import Request

KEY = "processed"


def build(request: Request) -> bool:
    span = request.span()
    return request.history().covers(span.start, span.end)
