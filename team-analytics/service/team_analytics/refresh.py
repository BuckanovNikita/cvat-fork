"""Refresh of the stored totals: recompute a trailing window and replace its hours as a whole.

Every `sql/refresh/*.sql` file is one calculation. Each reads events from `read_from` (a look-back
before the window) to `window_to`, keeps what belongs to [window_from, window_to) and inserts it
with this refresh's `version`. The hours are then marked with that version (`hour_versions`), which
is what makes readers switch to them, and rows of older versions are removed.

Only one refresh runs at a time: a lease in ClickHouse covers several replicas, a lock covers
threads of one process. The lease (`Config.refresh_lease_s`) is renewed while a step runs and is
released whatever fails; see `Refresher.leased`. A replica that can no longer prove it holds the lease
(its renewals failed or came too late) stops its step before the next write (`Refresher.ensure_lease`), so
nothing it computed becomes visible; the claim it lost is never extended again (control/lock_holder.sql).
The lease's time comes from a `LeaseClock`.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TypeVar

from team_analytics.config import Config
from team_analytics.cutover import find_cutover
from team_analytics.sql import AtRun, Sql

log = logging.getLogger(__name__)

T = TypeVar("T")

# Pauses before a failed release of the lease is tried again (then it is kept for the next step).
RELEASE_RETRY_S = (0.2, 1.0)
# Time for a concurrent claim to land before the earliest claim is read back.
SETTLE_S = 0.5
# Longest wait for the renewal in progress when a step ends (a hanging renewal must not delay the release).
RENEWAL_JOIN_S = 2.0
# Part of the lease kept in hand: a step writes only while more than this is left of the lease it can prove.
LEASE_MARGIN = 0.1


class LeaseLost(Exception):
    """The step's replica can no longer prove it holds the refresh lease; the step stops."""


class LeaseClock:
    """The time the refresh lease runs on. This one is the service's; a test supplies its own.

    A replica measures its own claim in `monotonic` seconds and waits for its next renewal with `wait`.
    Claims are stamped and judged in ClickHouse at `database_now`: None stands for ClickHouse's own clock,
    the one clock every replica shares, so no replica's wall clock decides who holds the lease. The pauses
    that wait for ClickHouse or for a thread (SETTLE_S, RELEASE_RETRY_S, RENEWAL_JOIN_S) are real time on
    any clock."""

    def monotonic(self) -> float:
        return time.monotonic()

    def wait(self, stop: threading.Event, seconds: float) -> bool:
        """Waits `seconds`, or until `stop` is set; True when it was set."""
        return stop.wait(seconds)

    def database_now(self) -> str | None:
        """Bound as `now` when a lease statement runs (control/lock_*.sql)."""
        return None


class _Lease:
    """What this replica can prove about its claim: it holds the lease until `deadline` (monotonic seconds).

    The deadline is taken before a claim or renewal is sent, so the claim in ClickHouse (expiry = its insert
    time + the lease) lives at least that long. A renewal extends it only when it returned before the
    deadline it extends; otherwise the lease is lost for good."""

    def __init__(self, token: str, length_s: float, sent_at: float, clock: LeaseClock) -> None:
        self.token = token
        self.length_s = length_s
        self._clock = clock
        self._deadline = sent_at + length_s
        self._lost = threading.Event()

    def renewed(self, sent_at: float) -> None:
        if not self._lost.is_set() and self._clock.monotonic() < self._deadline:
            self._deadline = sent_at + self.length_s
        else:
            self._lost.set()

    def held(self) -> bool:
        if not self._lost.is_set() and self._clock.monotonic() >= self._deadline - self.length_s * LEASE_MARGIN:
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
    def __init__(self, config: Config, sql: Sql, clock: Callable[[], datetime],
                 lease_clock: LeaseClock | None = None) -> None:
        self._config = config
        self._sql = sql
        self._clock = clock
        self._lease_clock = lease_clock or LeaseClock()
        self._local = threading.Lock()
        self._holder = f"{uuid.uuid4().hex[:8]}"
        # claims whose release failed: released before the next claim
        self._unreleased: set[str] = set()
        # the lease of the step in progress (set while `leased` runs its work)
        self._lease: _Lease | None = None

    def run(self) -> RefreshResult:
        """The ten-minute refresh: recompute the trailing window and record it as the latest refresh."""
        ran, result = self.leased(self._recompute)
        return result if ran else RefreshResult(ran=False)

    def leased(self, work: Callable[[], T]) -> tuple[bool, T | None]:
        """Runs `work` holding the refresh lease; (False, None) when a refresh or history step holds it, or
        when the lease was lost while `work` ran (`work` stopped at its next `ensure_lease`).

        The lease is renewed while `work` runs, so a step longer than the lease keeps it. Whatever fails, a
        claim written here is released before this returns or raises; a release that fails even when tried
        again is tried once more before the next claim."""
        if not self._local.acquire(blocking=False):
            return False, None
        try:
            self._release_pending()
            token = uuid.uuid4().hex
            lease = self._claim(token)
            if lease is None:
                return False, None
            stop = threading.Event()
            renewer = threading.Thread(target=self._renew, args=(lease, stop), daemon=True,
                                       name=f"lease-renewal-{token[:8]}")
            renewer.start()
            self._lease = lease
            try:
                return True, work()
            except LeaseLost:
                log.warning("lost the refresh lease; the step stopped before its next write")
                return False, None
            finally:
                self._lease = None
                stop.set()
                # bounded: a renewal that lands after the release is no live claim (control/lock_holder.sql)
                renewer.join(RENEWAL_JOIN_S)
                self._release(token)
        finally:
            self._local.release()

    def ensure_lease(self) -> None:
        """Raises LeaseLost unless the step in progress can still prove it holds the lease. Called before each
        write of a step (totals, hour marking, records), so a step that lost the lease leaves nothing visible."""
        lease = self._lease
        if lease is not None and not lease.held():
            raise LeaseLost(lease.token)

    def _claim(self, token: str) -> _Lease | None:
        try:
            sent_at = self._lease_clock.monotonic()
            self._write_claim(token)
            time.sleep(SETTLE_S)
            holder = self._sql.rows("control/lock_holder.sql", {"now": AtRun(self._lease_clock.database_now)})
        except BaseException:
            self._release(token)  # the claim may have been written
            raise
        if holder and holder[0]["token"] == token:
            return _Lease(token, self._config.refresh_lease_s, sent_at, self._lease_clock)
        self._release(token)
        return None

    def _write_claim(self, token: str) -> None:
        self._sql.statements("control/lock_claim.sql",
                             {"token": token, "holder": self._holder, "ttl_s": self._config.refresh_lease_s,
                              "now": AtRun(self._lease_clock.database_now)})

    def _renew(self, lease: _Lease, stop: threading.Event) -> None:
        """Extends the claim every third of the lease until `stop` is set (the work is over), or until the lease
        can no longer be proven: then it is never renewed again."""
        while not self._lease_clock.wait(stop, self._config.refresh_lease_s / 3):
            if not lease.held():
                log.warning("the refresh lease expired before it could be renewed")
                return
            sent_at = self._lease_clock.monotonic()
            try:
                self._write_claim(lease.token)
            except Exception:  # retried at the next third while the lease lasts
                log.exception("could not renew the refresh lease")
                continue
            lease.renewed(sent_at)

    def _release(self, token: str) -> None:
        """Releases a claim, trying again on failure; a release that still fails is kept for the next step."""
        for attempt, pause in enumerate(RELEASE_RETRY_S + (None,)):
            try:
                self._sql.statements("control/lock_release.sql",
                                     {"token": token, "holder": self._holder,
                                      "now": AtRun(self._lease_clock.database_now)})
                return
            except Exception:
                if pause is None:
                    log.exception("could not release the refresh lease after %s attempts", attempt + 1)
                    self._unreleased.add(token)
                    return
                time.sleep(pause)

    def _release_pending(self) -> None:
        for token in list(self._unreleased):
            self._unreleased.discard(token)
            self._release(token)

    def _recompute(self) -> RefreshResult:
        now = self._clock()
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        window_from = current_hour - timedelta(hours=self._config.refresh_window_hours - 1)
        window_to = current_hour + timedelta(hours=1)
        params = self.recompute(window_from, window_to)
        self.ensure_lease()
        self._sql.statements("control/record_refresh.sql",
                             {**params, "data_as_of": now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]})
        log.info("refreshed %s .. %s as version %s", window_from, window_to, params["version"])
        return RefreshResult(ran=True, version=params["version"], window_from=window_from, window_to=window_to)

    def recompute(self, window_from: datetime, window_to: datetime) -> dict:
        """Runs every refresh file over [window_from, window_to) (whole hours) and hands those hours to the
        result. The ten-minute refresh and each day of history use it alike; call it holding the lease (once
        the lease is lost it raises LeaseLost before its next write; rows written by then stay unmarked, so
        readers never see them, and the next marked refresh of those hours removes them).
        Returns the parameters the files ran with (`version` among them)."""
        hours = int((window_to - window_from).total_seconds() // 3600)
        read_from = window_from - timedelta(seconds=self._config.lookback_s)
        latest = self._sql.rows("control/latest_version.sql")[0]["version"] or 0
        version = max(int(time.time() * 1000), latest + 1)
        params = {
            "window_from": _text(window_from), "window_to": _text(window_to), "read_from": _text(read_from),
            "version": version, "window_hours": hours,
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
            tables = self._sql.rows("control/versioned_tables.sql", {"totals_db": self._config.totals_db})
            for row in tables:
                self._sql.statements("control/drop_superseded.sql", params, table=row["table"])
        return params
