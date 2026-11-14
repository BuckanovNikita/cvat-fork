"""GET details: every figure for every annotator, or every project, ten rows a page, sorted by working time.

Query, beside the period, `tz`, filters and shape switch as for the overview: `by` = `annotators` (default) |
`projects`; `page` (1-based, default 1; a page past the end gives the last one); `search` = text an
annotator's name contains (annotators only); `ids` = comma-separated project ids the page matched by name
(projects only; given but empty = no project matches). The filter on the table's own dimension is not applied,
so every row stays listed for picking; the other filter is.

Figures come from read/details.sql, the scope's legacy flag, applied shapes and project ids (for the page's
name search, since only the page knows project names) from read/details_scope.sql. Like the overview, an
unprocessed period says `processed: false` and the page withholds it.
"""

from __future__ import annotations

from team_analytics.history import load_state
from team_analytics.periods import BadRequest, decimal
from team_analytics.service import Request

PATH = "details"

PAGE_SIZE = 10
KINDS = ("annotators", "projects")
MAX_IDS = 5000


def _page(text: str) -> int:
    if text == "":
        return 1
    page = decimal(text, 9)
    if page is None or page < 1:
        raise BadRequest("page must be a positive number")
    return page


def _ids(text: str) -> list[int]:
    ids = [decimal(part, 19) for part in text.split(",") if part]
    if len(ids) > MAX_IDS or None in ids:
        raise BadRequest("ids must be identifiers")
    return sorted(set(ids))


def _number(value) -> float | None:
    return None if value is None else float(value)


def handle(request: Request) -> dict:
    kind = request.query.get("by", "") or KINDS[0]
    if kind not in KINDS:
        raise BadRequest(f"by must be one of {', '.join(KINDS)}")
    page = _page(request.query.get("page", ""))
    search = request.query.get("search", "").strip() if kind == "annotators" else ""
    has_ids = kind == "projects" and "ids" in request.query
    ids = _ids(request.query.get("ids", "")) if has_ids else []

    span = request.span()
    scope = request.scope_params()
    # the table's own dimension is listed whole; the selected row is only marked by the page
    if kind == "annotators":
        scope.update(has_annotator=0, annotator=0)
    else:
        scope.update(has_project=0, project=0)
    params = {**span.params(), **scope}

    summary = request.sql.rows("read/details_scope.sql", params)[0]
    rows = request.sql.rows("read/details.sql", {
        **params, "by": kind, "search": search, "has_ids": 1 if has_ids else 0, "ids": ids,
        "offset": (page - 1) * PAGE_SIZE, "page_size": PAGE_SIZE,
    })
    total = int(rows[0]["total"]) if rows else 0
    other = "projects" if kind == "annotators" else "annotators"

    body = {
        "by": kind,
        "page": (int(rows[0]["place"]) - 1) // PAGE_SIZE + 1 if rows else 1,
        "page_size": PAGE_SIZE,
        "total": total,
        "legacy": bool(summary["legacy"]),
        "shapes": "all" if summary["all_shapes"] else "bounding_boxes",
        "processed": load_state(request.sql, request.now).covers(span.start),
        "technical_accounts": len(request.config.technical_accounts),
        "rows": [{
            "id": int(row["id"]),
            "user_name": row["user_name"] if kind == "annotators" else None,
            other: int(row["others"]),
            "sessions": int(row["sessions"]),
            "working_time_ms": int(row["working_time_ms"]),
            "drawn": int(row["drawn"]),
            "pasted": int(row["pasted"]),
            "propagated": int(row["propagated"]),
            "model": int(row["model"]),
            "saved_boxes": int(row["saved_boxes"]),
            "alignments": int(row["alignments"]),
            "class_changes": int(row["class_changes"]),
            "deletions": int(row["deletions"]),
            "average_create_ms": _number(row["average_create_ms"]),
            "hotkey_share": _number(row["hotkey_share"]),
        } for row in rows],
    }
    if kind == "projects":
        body["project_ids"] = [int(value) for value in summary["project_ids"]]
    return body
