"""GET list: every row of one chart for the page's full view, for the period, filters and shape switch.

Query `by` = `annotators` | `projects` | `hotkeys`, plus everything the overview takes.

- `annotators` / `projects`: one row per annotator or project, largest working time first (rows.py, which the
  overview's rows by annotator and by project read too).
- `hotkeys`: every hotkey action with its count and share (read/list_hotkeys.sql); both filters apply, the shape
  switch does not.

Like the overview, `processed` says whether the whole period is processed. When it is not, the answer keeps
`period`, `processed`, `by` and the legacy flags, and every figure (`total`, `rows`, `hotkey_actions`) is null
(withheld.py). The hotkeys are then not read; the rows by annotator or project are, since the legacy flags come
from that read. The filters and the shape switch are judged first either way: a bad value is 400 whether or not the
period is processed.
"""

from __future__ import annotations

from ..periods import BadRequest
from ..request import Request
from ..rows import read as read_rows
from ..withheld import LEGACY_FLAGS, withhold

PATH = "list"

KINDS = ("annotators", "projects", "hotkeys")
ENVELOPE = frozenset({"period", "processed", "by"}) | LEGACY_FLAGS


def _hotkeys(request: Request) -> dict:
    rows = request.sql.rows(
        "read/list_hotkeys.sql", {**request.span().params(), **request.scope_params()}
    )
    return {
        "hotkey_actions": int(rows[0]["hotkey_actions"]) if rows else 0,
        "rows": [
            {"action": row["action"], "actions": int(row["actions"]), "share": float(row["share"])}
            for row in rows
        ],
    }


def handle(request: Request) -> dict:
    by = request.query.get("by", "")
    if by not in KINDS:
        raise BadRequest(f"by must be one of {', '.join(KINDS)}")
    span = request.span()
    request.scope_params()  # a bad annotator, project or shapes value is refused before the processed branch
    # read before any figure (request.Request.history)
    processed = request.history().covers(span.start, span.end)
    if by == "hotkeys":
        # no legacy flags in this answer: nothing is read for a period not fully processed
        body = _hotkeys(request) if processed else {"hotkey_actions": None, "rows": None}
    else:
        # read even then: the legacy flags of the envelope come from the rows' own read
        body = read_rows(request, by)
    answer = {
        "period": span.describe(),
        "processed": processed,
        "by": by,
        **body,
    }
    # no figures for a period not fully processed
    return answer if answer["processed"] else withhold(answer, ENVELOPE)
