"""How far history is processed, and which periods (in the viewer's time zone, query `tz`) are fully available.

A period is offered only when every hour of it is processed; trends need three complete weeks.

An administrator gets the whole block. Everyone else gets whether history is complete, the percentage, the
periods that can be offered and the trends' readiness; not the first day with events, the day counts or
the moment from which history is processed. What remains still describes the whole instance, and while
history is processed it lets a caller who polls work out the first day with events (docs/fork-specification.md,
"Known limit of `status` for a caller outside the admin group").
"""

from __future__ import annotations

from datetime import date, timedelta

from ..periods import PERIODS, midnight, monday, today, zone
from ..request import Request

KEY = "history"

# Trends show twelve buckets and need at least three complete weeks.
TREND_WEEKS = 12
TREND_MIN_WEEKS = 3


def _first_month(day: date) -> date:
    """The first month that starts on or after `day`."""
    if day.day == 1:
        return day
    return date(day.year + day.month // 12, day.month % 12 + 1, 1)


def build(request: Request) -> dict:
    tz_name = request.query.get("tz", "UTC") or "UTC"
    tz = zone(tz_name)
    # the request's one reading of the history state (request.Request.history), as every endpoint takes it
    state = request.history()
    current = today(request.now, tz)
    spans = {key: builder(request.now, tz, tz_name, None) for key, builder in PERIODS.items()}
    periods = {key: state.covers(span.start, span.end) for key, span in spans.items()}
    ready_from = state.ready_from
    ready_day = None  # the viewer's first whole day that is processed
    earliest_month = None
    weeks = TREND_WEEKS if state.complete else 0
    if ready_from is not None:
        ready_day = ready_from.astimezone(tz).date()
        if midnight(ready_day, tz) < ready_from:
            ready_day += timedelta(days=1)
        month = _first_month(ready_day)
        earliest_month = month.strftime("%Y-%m") if month <= current else None
        first_monday = monday(
            ready_day + timedelta(days=6)
        )  # the first Monday on or after ready_day
        weeks = max(0, min(TREND_WEEKS, (monday(current) - first_monday).days // 7))
    done, total = state.days()
    # rounded down, so it reads 100 only once history is complete
    percent = 100 if state.complete else min(99, done * 100 // total)
    if not request.scope.admin:
        # Built field by field, so a field added to the full block is not given away by default: no first day
        # with events, no day counts, not the exact moment processing has reached.
        return {
            "complete": state.complete,
            "percent": percent,
            "periods": periods,
            "earliest_month": earliest_month,
            "complete_weeks": weeks,
            "trends_ready": weeks >= TREND_MIN_WEEKS,
        }
    return {
        "complete": state.complete,
        "percent": percent,
        "ready_from": ready_from.isoformat() if ready_from else None,
        "ready_from_day": ready_day.isoformat() if ready_day else None,
        "first_day": state.first_day.isoformat() if state.first_day else None,
        "days_ready": done,
        "days_total": total,
        "periods": periods,
        # with history complete every month is available (null); otherwise the earliest one, or null for none
        "earliest_month": earliest_month,
        "complete_weeks": weeks,
        "trends_ready": weeks >= TREND_MIN_WEEKS,
    }
