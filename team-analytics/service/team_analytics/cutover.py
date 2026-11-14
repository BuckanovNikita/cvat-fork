"""The cutover to the new activity logging, and what it makes of a period.

The cutover is the hour of the first shape-tagged event on the instance (read/cutover.sql, from the stored
totals). Against it a span of time is
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

from dataclasses import dataclass
from datetime import UTC, datetime

from team_analytics.sql import Sql


def load_cutover(sql: Sql) -> datetime | None:
    rows = sql.rows("read/cutover.sql")
    if not rows:
        return None
    moment = rows[0]["cutover"]
    return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(UTC)


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
