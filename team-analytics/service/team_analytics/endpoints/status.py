"""GET status: the state of the stored figures, one key per section.

Sections are the modules of `team_analytics.status`; each defines `KEY` and `build(request)`.
"""

from __future__ import annotations

from team_analytics import status
from team_analytics.service import Request, discover

PATH = "status"


def handle(request: Request) -> dict:
    return {section.KEY: section.build(request) for section in discover(status)}
