"""Whether every hour of the requested period is processed. When it is not, the figures beside it are partial:
the page shows none of them (a period is offered only when all of it is processed)."""

from __future__ import annotations

from team_analytics.history import load_state
from team_analytics.service import Request

KEY = "processed"


def build(request: Request) -> bool:
    return load_state(request.sql, request.now).covers(request.span().start)
