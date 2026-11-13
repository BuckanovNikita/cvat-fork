"""Operations and Other for the period: count, average and total time, share of working time.

The `shapes` query (bounding_boxes | all) narrows every operation figure; see read/overview_operations.sql.
"""

from __future__ import annotations

from team_analytics.service import Request

KEY = "operations"


def build(request: Request) -> dict:
    rows = request.sql.rows("read/overview_operations.sql", {**request.span().params(), **request.scope_params()})
    first = rows[0]
    return {
        "legacy": bool(first["legacy"]),
        # the shapes the figures cover: what was asked for, or all shapes in a legacy period
        "shapes": "all" if first["all_shapes"] else "bounding_boxes",
        "working_time_ms": int(first["working_ms"] or 0),
        "active_time_ms": int(first["active_ms"] or 0),
        "rows": [
            {
                "operation": row["operation"],
                "objects": int(row["objects"]),
                "timed_objects": int(row["timed_objects"]),
                "time_ms": int(row["time_ms"]),
                "average_ms": None if row["average_ms"] is None else float(row["average_ms"]),
                "share": None if row["share"] is None else float(row["share"]),
            }
            for row in rows
        ],
    }
