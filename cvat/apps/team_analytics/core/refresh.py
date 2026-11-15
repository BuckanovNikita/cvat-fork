"""Refresh of the stored totals: recompute a trailing window and replace its hours as a whole.

Every `sql/refresh/*.sql` file is one calculation. Each reads events from `read_from` (a look-back
before the window) to `window_to`, keeps what belongs to [window_from, window_to) and inserts it
with this refresh's `version`. The hours are then marked with that version (`hour_versions`), which
is what makes readers switch to them, and rows of older versions are removed.

Only one refresh or history step runs at a time, across every worker process: each step takes the lock
the Refresher was given (`RefreshLock`; core/redis_lock.py keeps it in Redis) and gives it back whatever
fails. A step that can no longer prove it holds the lock (its extensions failed or came too late) stops
before its next write (`Refresher.ensure_lease`), so nothing it computed becomes visible.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, TypeVar

from .config import Config
from .cutover import find_cutover
from .sql import Sql

log = logging.getLogger(__name__)

T = TypeVar("T")

# Longest wait for the extension in progress when a step ends (a hanging extension must not delay the release).
RENEWAL_JOIN_S = 2.0
# Part of the lock's length kept in hand: a step writes only while more than this is left of what it can prove.
LEASE_MARGIN = 0.1


class LeaseLost(Exception):
    """The step can no longer prove it holds the refresh lock; the step stops."""


class RefreshLock(Protocol):
    """What lets one refresh or history step run at a time."""

    def acquire(self) -> bool:
        """Takes the lock without waiting; False when another step holds it."""
        ...

    def held(self) -> bool:
        """Whether the step that took the lock can still prove it holds it. Once False it stays False."""
        ...

    def release(self) -> None:
        """Gives the lock up; never raises."""
        ...


class LeaseClock:
    """The time a refresh lock's holder measures by. This one is the worker's; a test supplies its own."""

    def monotonic(self) -> float:
        return time.monotonic()

    def wait(self, stop: threading.Event, seconds: float) -> bool:
        """Waits `seconds`, or until `stop` is set; True when it was set."""
        return stop.wait(seconds)


class _Lease:
    """What a holder can prove about its lock: it holds it until `deadline` (monotonic seconds).

    The deadline is taken before the lock is taken or extended, so the lock itself lives at least that
    long. An extension moves the deadline only when it returned before the deadline it extends; otherwise
    the lock is lost for good."""

    def __init__(self, token: str, length_s: float, sent_at: float, clock: LeaseClock) -> None:
        self.token = token
        self.length_s = length_s
        self._clock = clock
        self._deadline = sent_at + length_s
        self._lost = threading.Event()

    def lose(self) -> None:
        """The lock is known to be gone (another holder took it over)."""
        self._lost.set()

    def renewed(self, sent_at: float) -> None:
        if not self._lost.is_set() and self._clock.monotonic() < self._deadline:
            self._deadline = sent_at + self.length_s
        else:
            self._lost.set()

    def held(self) -> bool:
        if (
            not self._lost.is_set()
            and self._clock.monotonic() >= self._deadline - self.length_s * LEASE_MARGIN
        ):
            self._lost.set()
        return not self._lost.is_set()


@dataclass(frozen=True)
class RefreshResult:
    ran: bool
    version: int | None = None
    window_from: datetime | None = None
    window_to: datetime | None = None


def _text(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M:%S")


class Refresher:
    def __init__(
        self,
        config: Config,
        sql: Sql,
        clock: Callable[[], datetime],
        lock: RefreshLock,
    ) -> None:
        self._config = config
        self._sql = sql
        self._clock = clock
        self._lock = lock
        # set while `leased` runs its work
        self._locked = False

    def run(self) -> RefreshResult:
        """The ten-minute refresh: recompute the trailing window and record it as the latest refresh."""
        ran, result = self.leased(self._recompute)
        return result if ran else RefreshResult(ran=False)

    def leased(self, work: Callable[[], T]) -> tuple[bool, T | None]:
        """Runs `work` holding the refresh lock; (False, None) when another step holds it, or when the lock
        was lost while `work` ran (`work` stopped at its next `ensure_lease`). Whatever fails, the lock is
        given back before this returns or raises."""
        if not self._lock.acquire():
            return False, None
        self._locked = True
        try:
            return True, work()
        except LeaseLost:
            log.warning("lost the refresh lock; the step stopped before its next write")
            return False, None
        finally:
            self._locked = False
            self._lock.release()

    def ensure_lease(self) -> None:
        """Raises LeaseLost unless the step in progress can still prove it holds the lock. Called before
        each write of a step (totals, hour marking, records), so a step that lost it leaves nothing visible.
        """
        if self._locked and not self._lock.held():
            raise LeaseLost("the refresh lock")

    def _recompute(self) -> RefreshResult:
        now = self._clock()
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        window_from = current_hour - timedelta(hours=self._config.refresh_window_hours - 1)
        window_to = current_hour + timedelta(hours=1)
        params = self.recompute(window_from, window_to)
        self.ensure_lease()
        self._sql.statements(
            "control/record_refresh.sql",
            {**params, "data_as_of": now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]},
        )
        log.info("refreshed %s .. %s as version %s", window_from, window_to, params["version"])
        return RefreshResult(
            ran=True, version=params["version"], window_from=window_from, window_to=window_to
        )

    def recompute(self, window_from: datetime, window_to: datetime) -> dict:
        """Runs every refresh file over [window_from, window_to) (whole hours) and hands those hours to the
        result. The ten-minute refresh and each day of history use it alike; call it holding the lock (once
        the lock is lost it raises LeaseLost before its next write; rows written by then stay unmarked, so
        readers never see them, and the next marked refresh of those hours removes them).
        Returns the parameters the files ran with (`version` among them)."""
        hours = int((window_to - window_from).total_seconds() // 3600)
        read_from = window_from - timedelta(seconds=self._config.lookback_s)
        latest = self._sql.rows("control/latest_version.sql")[0]["version"] or 0
        version = max(int(time.time() * 1000), latest + 1)
        params = {
            "window_from": _text(window_from),
            "window_to": _text(window_to),
            "read_from": _text(read_from),
            "version": version,
            "window_hours": hours,
        }
        # hours no refresh has marked before hold nothing to supersede (most days of a history fill)
        marked = self._sql.rows("control/window_marked.sql", params)[0]["marked"]
        for name in self._sql.files("refresh"):
            self.ensure_lease()
            self._sql.statements(name, params)
        # the first tagged hour in the totals: the cutover is found and stored before any hour is offered
        find_cutover(self._sql, self.ensure_lease)
        self.ensure_lease()  # once marked, the hours are visible
        self._sql.statements("control/mark_hours.sql", params)
        if marked:
            tables = self._sql.rows(
                "control/versioned_tables.sql", {"totals_db": self._config.totals_db}
            )
            for row in tables:
                self._sql.statements("control/drop_superseded.sql", params, table=row["table"])
        return params
