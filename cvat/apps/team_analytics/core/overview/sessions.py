"""Sessions for the period: the scope's number of sessions and their average and total length, and the
same per annotator (most sessions first)."""

from __future__ import annotations

from ..request import Request

KEY = "sessions"


def build(request: Request) -> dict:
    rows = request.sql.rows(
        "read/overview_sessions.sql", {**request.span().params(), **request.scope_params()}
    )
    first = rows[0] if rows else {"all_sessions": 0, "all_average_ms": 0, "all_total_ms": 0}
    return {
        "sessions": int(first["all_sessions"]),
        "average_ms": int(first["all_average_ms"]),
        "total_ms": int(first["all_total_ms"]),
        "by_annotator": [
            {
                "user_id": int(row["user_id"]),
                "user_name": row["latest_user_name"],
                "sessions": int(row["sessions"]),
                "average_ms": int(row["average_ms"]),
                "total_ms": int(row["total_ms"]),
            }
            for row in rows
        ],
    }
