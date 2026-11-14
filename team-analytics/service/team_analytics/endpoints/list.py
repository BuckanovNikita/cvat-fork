"""GET list: every row of one chart for the page's full view, for the period, filters and shape switch.

Query `by` = `annotators` | `projects` | `hotkeys`, plus everything the overview takes.

- `annotators` / `projects`: one row per annotator or project (read/list_rows.sql), largest working time first:
  working time and share, the four operations and Other, creation split by method, and Model. The row
  dimension's own filter is dropped (every annotator stays listed while one is selected), as on the overview;
  the shape switch is decided once for the whole list (`shapes`, `legacy` as in the overview's operations).
- `hotkeys`: every hotkey action with its count and share (read/list_hotkeys.sql); both filters apply, the shape
  switch does not.

Like the overview, `processed` says whether the whole period is processed; the page withholds partial figures.
"""

from __future__ import annotations

from team_analytics.history import load_state
from team_analytics.periods import BadRequest
from team_analytics.service import Request

PATH = "list"

KINDS = ("annotators", "projects", "hotkeys")
OPERATIONS = ("creation", "alignment", "class_change", "deletion")
METHODS = ("drawn", "pasted", "propagated")


def _number(value) -> float | None:
    return None if value is None else float(value)


def _figures(row: dict, name: str) -> dict:
    return {
        "objects": int(row[f"{name}_objects"]),
        "timed_objects": int(row[f"{name}_timed"]),
        "time_ms": int(row[f"{name}_ms"]),
        "average_ms": _number(row[f"{name}_average_ms"]),
    }


def _rows(request: Request, by: str) -> dict:
    span = request.span()
    legacy = request.legacy(span.start, span.end)
    scope = request.scope_params()
    params = {**span.params(), **scope, **legacy.params(), "by_project": 1 if by == "projects" else 0}
    # the row dimension's own filter does not narrow its rows
    if by == "projects":
        params.update(has_project=0, project=0)
    else:
        params.update(has_annotator=0, annotator=0)
    rows = request.sql.rows("read/list_rows.sql", params)
    all_shapes = not scope["bounding_boxes"] or legacy.legacy_period
    first = rows[0] if rows else {"all_shapes": all_shapes, "legacy": False, "job_work": False, "all_working_ms": 0}
    return {
        "legacy": bool(first["legacy"]),
        **legacy.describe(job_work=bool(first["job_work"])),
        "shapes": "all" if first["all_shapes"] else "bounding_boxes",
        "total": {"count": len(rows), "working_time_ms": int(first["all_working_ms"] or 0)},
        "rows": [
            {
                "id": int(row["id"]),
                "user_name": row["name"] if by == "annotators" else None,
                "working_time_ms": int(row["working_ms"]),
                "share": _number(row["share"]),
                "operations": {
                    **{name: _figures(row, name) for name in OPERATIONS},
                    "other": {"time_ms": int(row["other_ms"])},
                },
                "methods": {name: _figures(row, name) for name in METHODS},
                "model": int(row["model_objects"]),
            }
            for row in rows
        ],
    }


def _hotkeys(request: Request) -> dict:
    rows = request.sql.rows("read/list_hotkeys.sql", {**request.span().params(), **request.scope_params()})
    return {
        "hotkey_actions": int(rows[0]["hotkey_actions"]) if rows else 0,
        "rows": [{"action": row["action"], "actions": int(row["actions"]), "share": float(row["share"])}
                 for row in rows],
    }


def handle(request: Request) -> dict:
    by = request.query.get("by", "")
    if by not in KINDS:
        raise BadRequest(f"by must be one of {', '.join(KINDS)}")
    span = request.span()
    body = _hotkeys(request) if by == "hotkeys" else _rows(request, by)
    return {
        "period": span.describe(),
        "processed": load_state(request.sql, request.now).covers(span.start),
        "by": by,
        **body,
    }
