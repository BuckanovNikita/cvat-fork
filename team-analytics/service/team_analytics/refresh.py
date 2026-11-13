"""Refresh of the stored totals: recompute a trailing window and replace its hours as a whole.

Every `sql/refresh/*.sql` file is one calculation. Each reads events from `read_from` (a look-back
before the window) to `window_to`, keeps what belongs to [window_from, window_to) and inserts it
with this refresh's `version`. The hours are then marked with that version (`hour_versions`), which
is what makes readers switch to them, and rows of older versions are removed.

Only one refresh runs at a time: a lease in ClickHouse covers several replicas, a lock covers
threads of one process.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from team_analytics.config import Config
from team_analytics.sql import Sql

log = logging.getLogger(__name__)

LEASE_S = 1800
# Time for a concurrent claim to land before the earliest claim is read back.
SETTLE_S = 0.5


@dataclass(frozen=True)
class RefreshResult:
    ran: bool
    version: int | None = None
    window_from: datetime | None = None
    window_to: datetime | None = None


def _text(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


class Refresher:
    def __init__(self, config: Config, sql: Sql, clock: Callable[[], datetime]) -> None:
        self._config = config
        self._sql = sql
        self._clock = clock
        self._local = threading.Lock()
        self._holder = f"{uuid.uuid4().hex[:8]}"

    def run(self) -> RefreshResult:
        if not self._local.acquire(blocking=False):
            return RefreshResult(ran=False)
        try:
            token = uuid.uuid4().hex
            if not self._claim(token):
                return RefreshResult(ran=False)
            try:
                return self._recompute()
            finally:
                self._sql.statements("control/lock_release.sql", {"token": token, "holder": self._holder})
        finally:
            self._local.release()

    def _claim(self, token: str) -> bool:
        self._sql.statements("control/lock_claim.sql", {"token": token, "holder": self._holder, "ttl_s": LEASE_S})
        time.sleep(SETTLE_S)
        holder = self._sql.rows("control/lock_holder.sql")
        if holder and holder[0]["token"] == token:
            return True
        self._sql.statements("control/lock_release.sql", {"token": token, "holder": self._holder})
        return False

    def _recompute(self) -> RefreshResult:
        now = self._clock()
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        hours = self._config.refresh_window_hours
        window_from = current_hour - timedelta(hours=hours - 1)
        window_to = current_hour + timedelta(hours=1)
        read_from = window_from - timedelta(seconds=self._config.lookback_s)
        latest = self._sql.rows("control/latest_version.sql")[0]["version"] or 0
        version = max(int(time.time() * 1000), latest + 1)
        params = {
            "window_from": _text(window_from), "window_to": _text(window_to), "read_from": _text(read_from),
            "version": version, "window_hours": hours,
        }
        for name in self._sql.files("refresh"):
            self._sql.statements(name, params)
        self._sql.statements("control/mark_hours.sql", params)
        tables = self._sql.rows("control/versioned_tables.sql", {"totals_db": self._config.totals_db})
        for row in tables:
            self._sql.statements("control/drop_superseded.sql", params, table=row["table"])
        self._sql.statements("control/record_refresh.sql",
                             {**params, "data_as_of": now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]})
        log.info("refreshed %s .. %s as version %s", window_from, window_to, version)
        return RefreshResult(ran=True, version=version, window_from=window_from, window_to=window_to)
