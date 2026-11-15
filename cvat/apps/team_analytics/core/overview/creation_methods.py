"""Creation methods for the period: drawn, pasted and propagated objects, each with its average time.

The three add up to the Creation operation, and `total.average_ms` is its average; see
read/overview_creation_methods.sql. The `shapes` query narrows the figures as it does the operations.
`model` is the fourth method (count and share, no time), outside the three and their total;
`technical_accounts` is how many accounts are configured as technical (the page says so beside Model).
"""

from __future__ import annotations

from ..request import Request

KEY = "creation_methods"


def _number(value) -> float | None:
    return None if value is None else float(value)


def build(request: Request) -> dict:
    span = request.span()
    rows = request.sql.rows(
        "read/overview_creation_methods.sql",
        {
            **span.params(),
            **request.scope_params(),
            **request.legacy(span.start, span.end).params(),
        },
    )
    first = rows[0]
    return {
        "shapes": "all" if first["all_shapes"] else "bounding_boxes",
        "rows": [
            {
                "method": row["method"],
                "objects": int(row["objects"]),
                "timed_objects": int(row["timed_objects"]),
                "time_ms": int(row["time_ms"]),
                "average_ms": _number(row["average_ms"]),
                "share": _number(row["share"]),
            }
            for row in rows
        ],
        "total": {
            "objects": int(first["all_objects"]),
            "timed_objects": int(first["all_timed"]),
            "time_ms": int(first["all_time"]),
            "average_ms": _number(first["all_average_ms"]),
        },
        "model": {"objects": int(first["model_objects"]), "share": _number(first["model_share"])},
        "technical_accounts": len(request.config.technical_accounts),
    }
