"""Saved boxes for the period: single-frame rectangles the server stored when jobs were saved.

Whatever their creation method, so they are the one box figure a legacy period has. In total, per annotator
(technical accounts left out) and per project; see read/overview_saved_boxes.sql.
"""

from __future__ import annotations

from ..request import Request

KEY = "saved_boxes"


def build(request: Request) -> dict:
    rows = request.sql.rows(
        "read/overview_saved_boxes.sql", {**request.span().params(), **request.scope_params()}
    )
    total = next(row for row in rows if row["kind"] == "total")
    return {
        "boxes": int(total["boxes"]),
        "by_annotator": [
            {"user_id": int(row["id"]), "user_name": row["user_name"], "boxes": int(row["boxes"])}
            for row in rows
            if row["kind"] == "annotator"
        ],
        "by_project": [
            {"project_id": int(row["id"]), "boxes": int(row["boxes"])}
            for row in rows
            if row["kind"] == "project"
        ],
    }
