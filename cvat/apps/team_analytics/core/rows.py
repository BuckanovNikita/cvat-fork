"""Every row by annotator or by project for the period, filters and shape switch, in one read (read/list_rows.sql).

The full view (endpoints/list.py) answers with these rows; the overview's working time by annotator and by project
(overview/by_annotator.py, overview/by_project.py) takes its top rows and its rest from the same read, so a row's
operation parts on the overview are that row in the full view, and the overview asks one question per section, not
one per row.

Per row: working time and share, the four operations and Other (`operations`), creation split by method, and Model.
The row dimension's own filter is dropped (every annotator stays listed while one is selected); the shape switch is
decided once for the whole list (`shapes`, `legacy` as in the overview's operations).
"""

from __future__ import annotations

from .request import Request

KINDS = ("annotators", "projects")
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


def read(request: Request, by: str) -> dict:
    """Every row of `by` (`annotators` | `projects`), largest working time first, with the legacy flags."""
    span = request.span()
    legacy = request.legacy(span.start, span.end)
    scope = request.scope_params()
    params = {
        **span.params(),
        **scope,
        **legacy.params(),
        "by_project": 1 if by == "projects" else 0,
    }
    # the row dimension's own filter does not narrow its rows
    if by == "projects":
        params.update(has_project=0, project=0)
    else:
        params.update(has_annotator=0, annotator=0)
    rows = request.sql.rows("read/list_rows.sql", params)
    all_shapes = not scope["bounding_boxes"] or legacy.legacy_period
    first = (
        rows[0]
        if rows
        else {"all_shapes": all_shapes, "legacy": False, "job_work": False, "all_working_ms": 0}
    )
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


def operations_of(rows: list[dict]) -> dict:
    """The operation parts of several rows as one: each part added up row by row (Other as each row has it)."""
    parts: dict = {}
    for name in OPERATIONS:
        objects = sum(row["operations"][name]["objects"] for row in rows)
        timed = sum(row["operations"][name]["timed_objects"] for row in rows)
        time_ms = sum(row["operations"][name]["time_ms"] for row in rows)
        parts[name] = {
            "objects": objects,
            "timed_objects": timed,
            "time_ms": time_ms,
            "average_ms": time_ms / timed if timed > 0 else None,
        }
    parts["other"] = {"time_ms": sum(row["operations"]["other"]["time_ms"] for row in rows)}
    return parts


def top(request: Request, by: str, count: int) -> tuple[dict, list[dict], dict]:
    """The overview's part of the list: (the list, its `count` largest rows with working time, the rest).

    A row with no working time (a project with only Model boxes, say) is no bar on the overview: it is neither
    shown nor counted in the rest.
    """
    listed = read(request, by)
    worked = [row for row in listed["rows"] if row["working_time_ms"] > 0]
    hidden = worked[count:]
    rest = {
        "count": len(hidden),
        "working_time_ms": sum(row["working_time_ms"] for row in hidden),
        "operations": operations_of(hidden),
    }
    return listed, worked[:count], rest
