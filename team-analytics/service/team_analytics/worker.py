"""What the service's loop does next, one short step at a time, so that history never delays recent hours.

A step is, in this order of priority:
  1. the ten-minute refresh of recent hours, when the last one (by any replica) is an interval old;
  2. one day of history (or of days marked for a recount), newest first; with a refresh window shorter
     than a day, today's hours that have left the window come first (history.py);
  3. the daily check, when the last one is a day old: it compares raw counts and marks changed days for a
     recount, then looks for an earlier cutover in the recorded events (cutover.py), within a time limit.
Each step holds the shared refresh lease only for itself, so between two days of history a due refresh
always comes first. A step that finds the lease taken (another replica is working) is retried soon.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from team_analytics.config import Config
from team_analytics.history import History, aware
from team_analytics.refresh import Refresher
from team_analytics.sql import Sql

# Seconds before trying again when another replica holds the lease.
RETRY_S = 5.0


class Worker:
    def __init__(self, config: Config, sql: Sql, refresher: Refresher, history: History,
                 clock: Callable[[], datetime]) -> None:
        self._config = config
        self._sql = sql
        self._refresher = refresher
        self._history = history
        self._clock = clock

    def _refresh_age_s(self) -> float | None:
        last = aware(self._sql.rows("read/status_last_refresh.sql")[0]["last_success_at"])
        return None if last is None else (self._clock().astimezone(UTC) - last).total_seconds()

    def step(self) -> float:
        """Does the most urgent piece of work, if any; returns the seconds to wait before the next step."""
        interval = self._config.refresh_interval_s
        age = self._refresh_age_s()
        if age is None or age >= interval:
            return 0.0 if self._refresher.run().ran else RETRY_S
        if self._history.next_day() is not None:
            ran, _ = self._refresher.leased(self._history.process_next)
            return 0.0 if ran else RETRY_S
        if self._history.check_due():
            ran, _ = self._refresher.leased(self._history.check)
            return 0.0 if ran else RETRY_S
        return max(1.0, interval - age)
