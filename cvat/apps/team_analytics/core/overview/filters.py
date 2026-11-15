"""The filters the figures were read with: the project id (0 = No project) and the annotator with their name."""

from __future__ import annotations

from ..request import Request

KEY = "filters"


def build(request: Request) -> dict:
    annotator = request.filter_id("annotator")
    named = None
    if annotator is not None:
        rows = request.sql.rows("read/filter_annotator.sql", request.scope_params())
        named = {"user_id": annotator, "user_name": rows[0]["latest_user_name"] if rows else None}
    return {"project": request.filter_id("project"), "annotator": named}
