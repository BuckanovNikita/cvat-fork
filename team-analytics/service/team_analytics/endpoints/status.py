"""GET status: the state of the stored figures, one key per section.

Sections are the modules of `team_analytics.status`; each defines `KEY` and `build(request)`. A section that
cannot be read is null, so the others (the freshness warning above all) are still reported.
"""

from __future__ import annotations

import logging

from team_analytics import status
from team_analytics.periods import BadRequest
from team_analytics.service import Request, discover

PATH = "status"

log = logging.getLogger(__name__)


def handle(request: Request) -> dict:
    body: dict = {}
    for section in discover(status):
        try:
            body[section.KEY] = section.build(request)
        except BadRequest:
            raise
        except Exception:
            log.exception("status section %s failed", section.KEY)
            body[section.KEY] = None
    return body
