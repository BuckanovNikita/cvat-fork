"""Working time per annotator for the period, largest first."""

from __future__ import annotations

from team_analytics.service import Request

KEY = "by_annotator"


def build(request: Request) -> dict:
    rows = request.sql.rows("read/overview_by_annotator.sql", {**request.span().params(), **request.scope_params()})
    return {
        "rows": [
            {"user_id": int(row["user_id"]), "user_name": row["latest_user_name"],
             "working_time_ms": int(row["working_time_ms"])}
            for row in rows
        ],
    }
