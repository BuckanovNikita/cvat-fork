"""Operations and Other for the period: count, average and total time, share of working time.

The `shapes` query (bounding_boxes | all) narrows every operation figure; see read/overview_operations.sql.
`legacy` / `partly_legacy` / `cutover`: what the cutover to the new logging makes of the period (cutover.py).
"""

from __future__ import annotations

from ..request import Request

KEY = "operations"


def build(request: Request) -> dict:
    span = request.span()
    legacy = request.legacy(span.start, span.end)
    rows = request.sql.rows(
        "read/overview_operations.sql",
        {**span.params(), **request.scope_params(), **legacy.params()},
    )
    first = rows[0]
    return {
        "legacy": bool(first["legacy"]),
        # the period holds the cutover: bounding box figures, class changes and hotkey use cover the part after it
        **legacy.describe(job_work=bool(first["job_work"])),
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
                "hotkey_objects": int(row["hotkey_objects"]),
                "mouse_objects": int(row["mouse_objects"]),
            }
            for row in rows
        ],
    }
