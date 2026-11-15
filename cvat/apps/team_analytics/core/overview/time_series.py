"""Working time laid out over the period: per viewer day, or per Monday week for long periods."""

from __future__ import annotations

from ..request import Request

KEY = "time_series"


def build(request: Request) -> dict:
    span = request.span()
    rows = request.sql.rows(
        "read/overview_time_series.sql", {**span.day_params(), **request.scope_params()}
    )
    return {
        "unit": span.unit,
        "buckets": [
            {"start": row["bucket"].isoformat(), "working_time_ms": int(row["working_time_ms"])}
            for row in rows
        ],
    }
