"""Processed history: computing older days, one UTC day at a time, newest first, and the daily recount.

The ten-minute refresh keeps the trailing hours current. Every whole day before today is also computed on
its own, with the same refresh files (`Refresher.recompute`), and recorded with the number of raw event
rows it had (`history_days`). That covers history that existed before deployment, and days that left the
trailing window. Once a day the raw counts are compared with the stored ones; a day that differs, and the
days on either side of it (sessions and operations crossing midnight are stored in the day they end), are
computed again, which replaces their totals.

A refresh window shorter than a day leaves hours of today before it, which belong to neither. The history
step computes those too, ahead of the older days, each time hours have left the window (`history_today`).
Until then they are not processed: a period that holds them is not, a period that ends before them still is.
A window of a day or longer leaves none.

A period is offered only when all of it is processed: `HistoryState.covers(start, end)`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from .cutover import look_for_cutover
from .refresh import LeaseLost, Refresher
from .sql import Limit, Sql

log = logging.getLogger(__name__)

# How often the raw counts of processed days are compared with the stored ones.
CHECK_EVERY = timedelta(days=1)


def _day_start(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def _text(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def _instant(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def aware(moment: datetime | None) -> datetime | None:
    if moment is None:
        return None
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(UTC)


@dataclass(frozen=True)
class HistoryState:
    today: date  # UTC
    first_day: date | None  # UTC day of the earliest event; None without events
    trailing_from: (
        datetime | None
    )  # start of the latest ten-minute refresh; None before the first one
    missing: (
        date | None
    )  # newest day before today not yet computed that the trailing hours do not cover
    # with a refresh window shorter than a day: where today's hours that left the window and wait for the
    # history step begin (they end at `trailing_from`); None when no hour waits
    waiting_from: datetime | None = None

    @property
    def started(self) -> bool:
        return self.trailing_from is not None

    @property
    def complete(self) -> bool:
        return self.started and self.missing is None and self.waiting_from is None

    @property
    def ready_from(self) -> datetime | None:
        """The earliest moment from which every hour up to now is processed; None when nothing is, or all is."""
        if not self.started or self.complete:
            return None
        if self.waiting_from is not None:
            return self.trailing_from
        return min(_day_start(self.missing + timedelta(days=1)), self.trailing_from)

    def _earlier_from(self) -> datetime | None:
        """While hours of today wait: the earliest moment from which every hour up to `waiting_from` is
        processed (None when every hour before it is)."""
        return None if self.missing is None else _day_start(self.missing + timedelta(days=1))

    def covers(self, start: datetime, end: datetime | None = None) -> bool:
        """Whether every hour from `start` up to `end` (UTC; up to now when None) is processed."""
        if self.complete:
            return True
        if self.waiting_from is not None and end is not None and end <= self.waiting_from:
            # wholly before today's hours that wait for the history step
            earlier = self._earlier_from()
            return earlier is None or start >= earlier
        ready = self.ready_from
        return ready is not None and start >= ready

    def days(self) -> tuple[int, int]:
        """(processed, all) UTC days from the first day with events to today."""
        if self.first_day is None:
            return (1, 1) if self.started else (0, 1)
        total = (self.today - self.first_day).days + 1
        if self.complete:
            return total, total
        if self.waiting_from is not None:
            # today is not processed as a whole; the days before it are from the one after `missing` on
            earlier = self._earlier_from()
            first_whole = self.first_day if earlier is None else earlier.date()
            return max(0, min(total - 1, (self.today - first_whole).days)), total
        ready = self.ready_from
        if ready is None:
            return 0, total
        first_whole = (
            ready.date() if ready == _day_start(ready.date()) else ready.date() + timedelta(days=1)
        )
        return max(0, min(total, (self.today - first_whole).days + 1)), total


def load_state(sql: Sql, now: datetime) -> HistoryState:
    today = now.astimezone(UTC).date()
    row = sql.rows("read/history_state.sql", {"today": today.isoformat()})[0]
    return HistoryState(
        today=today,
        first_day=row["first_event_day"],
        trailing_from=aware(row["trailing_from"]),
        missing=row["missing"],
        waiting_from=aware(row["waiting_from"]),
    )


class History:
    def __init__(
        self, sql: Sql, refresher: Refresher, clock: Callable[[], datetime], search_limit: Limit
    ) -> None:
        self._sql = sql
        self._search_limit = search_limit  # of the cutover search in the daily check
        self._refresher = refresher
        self._clock = clock

    def _today(self) -> date:
        return self._clock().astimezone(UTC).date()

    def check_due(self) -> bool:
        last = aware(self._sql.rows("read/history_last_check.sql")[0]["checked_at"])
        return last is None or self._clock() - last >= CHECK_EVERY

    def _next(self, today: date) -> dict | None:
        rows = self._sql.rows("control/history_next_day.sql", {"today": today.isoformat()})
        return rows[0] if rows else None

    def _version(self, at_least: int = 0) -> int:
        latest = self._sql.rows("control/history_version.sql")[0]["version"] or 0
        return max(int(time.time() * 1000), latest + 1, at_least)

    def check(self) -> int:
        """The daily check (holding the lock): marks days whose raw count changed, and their neighbours,
        for computing again, then looks for an earlier cutover in the recorded events. Returns the number of
        days marked."""
        now = self._clock()
        params = {"before": _text(_day_start(now.astimezone(UTC).date()))}
        days = [
            row["neighbour"] for row in self._sql.rows("control/history_changed_days.sql", params)
        ]
        self._refresher.ensure_lease()
        if days:
            self._sql.statements(
                "control/history_mark_pending.sql",
                {
                    "days": [day.isoformat() for day in days],
                    "version": self._version(),
                    "at": _instant(now),
                },
            )
        self._sql.statements(
            "control/history_record_check.sql", {"checked_at": _instant(now), "changed": len(days)}
        )
        log.info("history check: %s day(s) to compute again", len(days))
        # after the check is recorded: a search that fails, or reaches its limit, is tried again by the next
        # daily check, not at once; the step ends without it
        try:
            look_for_cutover(self._sql, now, self._search_limit, self._refresher.ensure_lease)
        except LeaseLost:
            raise
        except Exception:
            log.exception("could not look for the cutover in the daily check")
        return len(days)

    def process_next(self) -> date | None:
        """Computes the next day of history, or today's hours before the refresh window (holding the lock);
        None when there is nothing to do."""
        today = self._today()
        following = self._next(today)
        if following is None:
            return None
        day = following["day"]
        if day == today:
            self._process_today(
                today, aware(following["today_computed_to"]), aware(following["trailing_from"])
            )
            return day
        day_from, day_to = _day_start(day), _day_start(day + timedelta(days=1))
        now = self._clock()
        # counted before computing: a row landing meanwhile makes the next check compute the day again
        found = self._sql.rows(
            "control/history_day.sql", {"day_from": _text(day_from), "day_to": _text(day_to)}
        )[0]
        if found["raw_rows"] == 0 and found["marked_hours"] == 0:
            # an empty day without figures: it and the empty days before it need no computation
            first = found["previous_day"] + timedelta(days=1)
            self._record(first, (day - first).days + 1, 0, self._version(), now)
            log.info("history: no events %s .. %s", first, day)
            return day
        params = self._refresher.recompute(day_from, day_to)
        self._record(day, 1, int(found["raw_rows"]), self._version(params["version"]), now)
        log.info("history: computed %s as version %s", day, params["version"])
        return day

    def _process_today(self, today: date, computed_to: datetime, trailing_from: datetime) -> None:
        """Computes today's hours before the refresh window that have not been computed since they left it:
        from where the step got to (`computed_to`), or from today's midnight when that is later, up to
        `trailing_from`."""
        hours_from = max(_day_start(today), computed_to)
        now = self._clock()
        params = self._refresher.recompute(hours_from, trailing_from)
        self._refresher.ensure_lease()
        self._sql.statements(
            "control/history_record_today.sql",
            {"computed_to": _text(trailing_from), "at": _instant(now)},
        )
        log.info(
            "history: computed today's hours %s .. %s as version %s",
            hours_from,
            trailing_from,
            params["version"],
        )

    def _record(self, first: date, days: int, raw_rows: int, version: int, now: datetime) -> None:
        self._refresher.ensure_lease()
        self._sql.statements(
            "control/history_record_days.sql",
            {
                "first": first.isoformat(),
                "days": days,
                "raw_rows": raw_rows,
                "version": version,
                "at": _instant(now),
            },
        )
