"""GET details: every figure for every annotator, or every project, ten rows a page, sorted by working time.

Query, beside the period, `tz`, filters and shape switch as for the overview: `by` = `annotators` (default) |
`projects`; `page` (1-based, default 1; a page past the end gives the last one); `search` = text an
annotator's name contains (annotators only); `ids` = comma-separated project ids the page matched by name
(projects only; given but empty = no project matches). The filter on the table's own dimension is not applied,
so every row stays listed for picking; the other filter is.

Figures come from read/details.sql, the scope's legacy flag, applied shapes and project ids (for the page's
name search, since only the page knows project names) from read/details_scope.sql. Like the overview, a
period not fully processed says `processed: false` and carries no figures: it keeps `by`, `page_size`,
`processed`, `technical_accounts` and the legacy flags, and `page`, `total`, `rows` and `project_ids` are null
(withheld.py). Its rows are then not read; the summary is, since the legacy flags come from it.
"""

from __future__ import annotations

from ..periods import BadRequest, decimal
from ..request import Request
from ..withheld import LEGACY_FLAGS, withhold

PATH = "details"

PAGE_SIZE = 10
KINDS = ("annotators", "projects")
MAX_IDS = 5000
ENVELOPE = frozenset({"by", "page_size", "processed", "technical_accounts"}) | LEGACY_FLAGS


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
    # read before any figure (request.Request.history)
    processed = request.history().covers(span.start, span.end)
    scope = request.scope_params()
    # the table's own dimension is listed whole; the selected row is only marked by the page
    if kind == "annotators":
        scope.update(has_annotator=0, annotator=0)
    else:
        scope.update(has_project=0, project=0)
    legacy = request.legacy(span.start, span.end)
    params = {**span.params(), **scope, **legacy.params()}

    summary = request.sql.rows("read/details_scope.sql", params)[0]
    # the table's rows are not read for a period not fully processed (the legacy flags come from the summary)
    rows = (
        request.sql.rows(
            "read/details.sql",
            {
                **params,
                "by": kind,
                "search": search,
                "has_ids": 1 if has_ids else 0,
                "ids": ids,
                "offset": (page - 1) * PAGE_SIZE,
                "page_size": PAGE_SIZE,
            },
        )
        if processed
        else []
    )
    total = int(rows[0]["total"]) if rows else 0
    other = "projects" if kind == "annotators" else "annotators"

    body = {
        "by": kind,
        "page": (int(rows[0]["place"]) - 1) // PAGE_SIZE + 1 if rows else 1,
        "page_size": PAGE_SIZE,
        "total": total,
        "legacy": bool(summary["legacy"]),
        **legacy.describe(job_work=bool(summary["job_work"])),
        "shapes": "all" if summary["all_shapes"] else "bounding_boxes",
        "processed": processed,
        "technical_accounts": len(request.technical_accounts),
        "rows": [
            {
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
            }
            for row in rows
        ],
    }
    if kind == "projects":
        body["project_ids"] = [int(value) for value in summary["project_ids"]]
    # no figures for a period not fully processed
    return body if body["processed"] else withhold(body, ENVELOPE)
