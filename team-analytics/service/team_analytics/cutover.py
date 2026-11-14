"""The cutover to the new activity logging, and what it makes of a period.

The cutover is the hour of the first shape-tagged operation event on the instance. It is stored once known
(`find_cutover`, table `cutover`) and read from there on requests (read/cutover.sql); once stored it does
not move. Until it is stored there is no cutover. Against it a span of time is
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

from team_analytics.sql import Sql

log = logging.getLogger(__name__)


def find_cutover(sql: Sql, before_write: Callable[[], None]) -> datetime | None:
    """Stores the cutover when none is stored yet and the stored totals hold a shape-tagged operation (run by the
    service's worker inside a step holding the refresh lease; `before_write` checks that lease). The cutover
    is then the hour of the earliest shape-tagged operation event in the raw events, so it is right even
    while history is still being processed newest first. Returns the cutover stored now, or None."""
    due = sql.rows("control/cutover_due.sql")
    if not due:
        return None
    tagged = _utc(due[0]["tagged_hour"])
    before_write()
    sql.statements("control/cutover_find.sql",
                   {"until": (tagged + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S.000")})
    found = load_cutover(sql)
    if found is None:
        log.warning("no shape-tagged operation event before %s, although the totals hold one", tagged)
    else:
        log.info("stored the cutover to the new activity logging: %s", found.isoformat())
    return found


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
        work in the span (from the read file); without it the span is empty, so not partly legacy either."""
        return {"partly_legacy": self.partly_legacy and job_work,
                "cutover": self.cutover.isoformat() if self.cutover else None}
