"""The cutover to the new activity logging (cutover.py): the hour of the first shape-tagged event on the
instance, or null before there is one."""

from __future__ import annotations

from team_analytics.service import Request

KEY = "cutover"


def build(request: Request) -> dict:
    cutover = request.cutover()
    return {"at": cutover.isoformat() if cutover else None}
