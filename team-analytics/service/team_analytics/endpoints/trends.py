"""GET trends: four figures over the last twelve weeks or months, independent of the selected period.

Query: `step` = `week` (default; Monday weeks) | `month`; `tz`; the project and annotator filters and the shape
switch as everywhere; `compare` = `annotators` (default) | `projects`, the kind of line that can be compared and
offered as candidates; `ids` = up to five comma-separated ids of that kind. Without ids there is one line for
the scope under both filters; with ids one line per id, where the compared dimension replaces its own filter.
`period` and `month` are ignored. The last bucket is the current, incomplete week or month.

Each bucket says whether it is processed; like a period, an unprocessed bucket's figures are partial and the
page withholds them. Figures come from read/trends.sql; candidates (everyone of the compared kind with work
in the twelve buckets) from read/trends_candidates.sql.
"""

from __future__ import annotations

from datetime import date, timedelta

from team_analytics.history import load_state
from team_analytics.periods import BadRequest, decimal, hour_floor, midnight, monday, months_before, today, zone
from team_analytics.service import Request

PATH = "trends"

BUCKETS = 12
MAX_COMPARED = 5
STEPS = ("week", "month")
KINDS = ("annotators", "projects")


def _choice(request: Request, key: str, options: tuple[str, ...]) -> str:
    value = request.query.get(key, "") or options[0]
    if value not in options:
        raise BadRequest(f"{key} must be one of {', '.join(options)}")
    return value


def _ids(text: str) -> list[int]:
    ids: list[int] = []
    for part in filter(None, text.split(",")):
        number = decimal(part, 19)
        if number is None:
            raise BadRequest("ids must be identifiers")
        if number not in ids:
            ids.append(number)
    if len(ids) > MAX_COMPARED:
        raise BadRequest(f"at most {MAX_COMPARED} ids can be compared")
    return ids


def bucket_starts(current: date, step: str) -> list[date]:
    """The first days of the twelve buckets ending with the one holding `current`."""
    if step == "week":
        last = monday(current)
        return [last - timedelta(weeks=BUCKETS - 1 - index) for index in range(BUCKETS)]
    last = current.replace(day=1)
    return [months_before(last, BUCKETS - 1 - index) for index in range(BUCKETS)]


def _number(value) -> float | None:
    return None if value is None else float(value)


def _whole(value) -> int | None:
    return None if value is None else int(value)


def handle(request: Request) -> dict:
    step = _choice(request, "step", STEPS)
    kind = _choice(request, "compare", KINDS)
    ids = _ids(request.query.get("ids", ""))
    tz_name = request.query.get("tz", "UTC") or "UTC"
    tz = zone(tz_name)
    starts = bucket_starts(today(request.now, tz), step)
    span = {
        "from": midnight(starts[0], tz).strftime("%Y-%m-%d %H:%M:%S"),
        "to": (hour_floor(request.now) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
    }
    scope = request.scope_params()
    rows = request.sql.rows("read/trends.sql", {
        **span, **scope, "tz": tz_name, "monthly": 1 if step == "month" else 0,
        "first_bucket": starts[0].isoformat(), "buckets": [start.isoformat() for start in starts],
        "line_kind": kind if ids else "scope", "ids": ids,
    })
    candidates = request.sql.rows("read/trends_candidates.sql", {**span, **scope, "kind": kind})
    names = {int(row["id"]): row["name"] for row in candidates}
    state = load_state(request.sql, request.now)

    lines: list[dict] = []
    for row in rows:
        line = int(row["line"])
        if not lines or lines[-1]["key"] != line:
            lines.append({"key": line, "points": []})
        lines[-1]["points"].append({
            "working_time_ms": int(row["working_time_ms"]),
            "legacy": bool(row["legacy"]),
            "boxes": _whole(row["boxes"]),
            "timed_boxes": _whole(row["timed_boxes"]),
            "box_time_ms": _whole(row["box_time_ms"]),
            "average_ms": _number(row["average_ms"]),
            "hotkey_recorded": bool(row["hotkey_recorded"]),
            "hotkey_actions": int(row["hotkey_actions"]),
            "mouse_actions": int(row["mouse_actions"]),
            "hotkey_share": _number(row["hotkey_share"]),
        })
    for line in lines:
        key = line.pop("key")
        line["id"] = key if ids else None
        line["user_name"] = (names.get(key) or None) if ids and kind == "annotators" else None

    return {
        "step": step,
        "tz": tz_name,
        # the shapes the figures cover: all shapes when asked, or when nothing in the twelve buckets is shape-tagged
        "shapes": "all" if rows[0]["all_shapes"] else "bounding_boxes",
        "compare": kind,
        "buckets": [{"start": start.isoformat(), "processed": state.covers(midnight(start, tz))} for start in starts],
        "lines": lines,
        "candidates": [
            {"id": int(row["id"]), "user_name": row["name"] if kind == "annotators" else None,
             "working_time_ms": int(row["working_time_ms"])}
            for row in candidates
        ],
    }
