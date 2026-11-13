"""Working time per annotator for the period: the largest rows and the rest as one line.

The project filter applies, the annotator filter does not (every annotator stays listed for picking).
"""

from __future__ import annotations

from team_analytics.service import Request

KEY = "by_annotator"
TOP = 8


def build(request: Request) -> dict:
    rows = request.sql.rows("read/overview_by_annotator.sql",
                            {**request.span().params(), **request.scope_params(), "top": TOP})
    first = rows[0] if rows else {"rest_count": 0, "rest_ms": 0}
    return {
        "rows": [
            {"user_id": int(row["user_id"]), "user_name": row["latest_user_name"],
             "working_time_ms": int(row["working_time_ms"])}
            for row in rows
        ],
        "rest": {"count": int(first["rest_count"]), "working_time_ms": int(first["rest_ms"])},
    }
