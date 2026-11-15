"""The cutover to the new activity logging, and what it makes of a period.

The cutover is the hour of the first shape-tagged operation event on the instance. It is looked for in the
recorded events: by the first job and in the daily check (`look_for_cutover`), and when a refresh
first stores a shape-tagged hour (`find_cutover`). Every hour found is stored (table `cutover`) and requests
read the earliest stored hour (read/cutover.sql), so the cutover moves to an earlier hour when an earlier
shape-tagged event turns up and never to a later one. Until an hour is stored there is no cutover. Against
it a span of time is
  - legacy when it ends at or before the cutover, or when no cutover is known: operations cover all
    shapes, class changes and hotkey use were not recorded, saved boxes stand in for Model;
  - partly legacy when it begins before the cutover and ends after it: figures are computed as usual
    (operations without a shape type count under All shapes only) and the page says since when the
    bounding box figures, class changes and hotkey use are complete;
  - otherwise (it begins at or after the cutover) not legacy, whatever its scope holds.
A period with no job work in its scope is empty, neither legacy nor partly legacy: read files decide that part
(`legacy` and `job_work` columns).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .sql import Limit, Sql

log = logging.getLogger(__name__)


def look_for_cutover(
    sql: Sql, now: datetime, limit: Limit, before_write: Callable[[], None] | None = None
) -> datetime | None:
    """The long-range search, run by the first job and in the daily check. It reads the recorded events
    before the stored cutover (before the end of the current hour while none is stored) in time order, stops
    at the first shape-tagged operation event and stores its hour. Once a cutover is stored it finds none unless
    an earlier event turned up, so it reads every event before the stored cutover; while none is stored it reads up to the first tagged
    event, or all of them when there is none to find. So the cutover is known before a tagged
    hour reaches the stored totals and moves earlier when an earlier event turned up. Returns the cutover
    as it is afterwards, or None.

    The search runs within `limit`, which ClickHouse enforces: a search that reaches it is stopped there and
    raises, as a failed one does, and stores nothing.

    `before_write` checks the lock of the step that runs the search. Rows are only added and the earliest
    is read, so two searches at once would leave one cutover.
    """
    stored = load_cutover(sql)
    until = _utc(now).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    found = _store_earliest(
        sql, until if stored is None else min(stored, until), before_write, limit
    )
    if found != stored:
        log.info("the cutover to the new activity logging is %s (was %s)", found, stored)
    return found


def find_cutover(sql: Sql, before_write: Callable[[], None]) -> datetime | None:
    """Stores the cutover when none is stored yet and the stored totals hold a shape-tagged operation (run
    inside a step holding the refresh lock; `before_write` checks that lock). The cutover
    is then the hour of the earliest shape-tagged operation event in the raw events, so it is right even
    while history is still being processed newest first. Returns the cutover stored now, or None."""
    due = sql.rows("control/cutover_due.sql")
    if not due:
        return None
    tagged = _utc(due[0]["tagged_hour"])
    found = _store_earliest(sql, tagged + timedelta(hours=1), before_write)
    if found is None:
        log.warning(
            "no shape-tagged operation event before %s, although the totals hold one", tagged
        )
    else:
        log.info("stored the cutover to the new activity logging: %s", found.isoformat())
    return found


def _store_earliest(
    sql: Sql, until: datetime, before_write: Callable[[], None] | None, limit: Limit | None = None
) -> datetime | None:
    """Stores the hour of the earliest shape-tagged operation event before `until`, when there is one (one
    statement over the raw events, control/cutover_find.sql), within `limit` when given; returns the cutover
    as it reads afterwards. The refresh's search (`find_cutover`) is given none of its own and runs within
    the runner's statement limit, as every statement of a refresh does."""
    if before_write is not None:
        before_write()
    sql.statements(
        "control/cutover_find.sql", {"until": until.strftime("%Y-%m-%d %H:%M:%S.000")}, limit=limit
    )
    return load_cutover(sql)


def _utc(moment: datetime) -> datetime:
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(UTC)


def load_cutover(sql: Sql) -> datetime | None:
    rows = sql.rows("read/cutover.sql")
    return _utc(rows[0]["cutover"]) if rows else None


@dataclass(frozen=True)
class Legacy:
    """What the cutover makes of the span [start, end)."""

    cutover: datetime | None
    start: datetime
    end: datetime

    @property
    def legacy_period(self) -> bool:
        return self.cutover is None or self.end <= self.cutover

    @property
    def partly_legacy(self) -> bool:
        return self.cutover is not None and self.start < self.cutover < self.end

    def params(self) -> dict:
        """For the read files: `legacy_period` (1 = all shapes, legacy when the scope has job work)."""
        return {"legacy_period": 1 if self.legacy_period else 0}

    def describe(self, *, job_work: bool) -> dict:
        """For responses: `partly_legacy` and the `cutover` moment (ISO, or None). `job_work` = the scope has job
        work in the span (from the read file); without it the span is empty, so not partly legacy either.
        """
        return {
            "partly_legacy": self.partly_legacy and job_work,
            "cutover": self.cutover.isoformat() if self.cutover else None,
        }
