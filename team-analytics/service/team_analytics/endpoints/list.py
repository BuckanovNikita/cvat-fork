"""GET list: every row of one chart for the page's full view, for the period, filters and shape switch.

Query `by` = `annotators` | `projects` | `hotkeys`, plus everything the overview takes.

- `annotators` / `projects`: one row per annotator or project, largest working time first (rows.py, which the
  overview's rows by annotator and by project read too).
- `hotkeys`: every hotkey action with its count and share (read/list_hotkeys.sql); both filters apply, the shape
  switch does not.

Like the overview, `processed` says whether the whole period is processed. When it is not, the answer keeps
`period`, `processed`, `by` and the legacy flags, and every figure (`total`, `rows`, `hotkey_actions`) is null
(withheld.py).
"""

from __future__ import annotations

from team_analytics.history import load_state
from team_analytics.periods import BadRequest
from team_analytics.rows import read as read_rows
from team_analytics.service import Request
from team_analytics.withheld import LEGACY_FLAGS, withhold

PATH = "list"

KINDS = ("annotators", "projects", "hotkeys")
ENVELOPE = frozenset({"period", "processed", "by"}) | LEGACY_FLAGS


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
    body = _hotkeys(request) if by == "hotkeys" else read_rows(request, by)
    answer = {
        "period": span.describe(),
        "processed": load_state(request.sql, request.now).covers(span.start),
        "by": by,
        **body,
    }
    # no figures for a period not fully processed
    return answer if answer["processed"] else withhold(answer, ENVELOPE)
