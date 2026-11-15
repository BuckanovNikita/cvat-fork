"""The refresh lock kept in Redis: one refresh or history step at a time, across every worker process.

The lock is a key with an expiry, taken without waiting. While a step holds it, a thread extends it every
third of its length, so a step longer than the lock keeps it; a holder that died stops extending, and the
lock frees itself when it expires. What the holder can prove is tracked by `refresh._Lease`: a deadline
taken before each extension is sent, and the lock counts as lost within the last tenth of it. A step asks
`held()` before each write and stops when it is False.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from redis.exceptions import LockError, RedisError

from .refresh import RENEWAL_JOIN_S, LeaseClock, _Lease

log = logging.getLogger(__name__)

LOCK_NAME = "team_analytics:refresh"


class RedisLock:
    """A `refresh.RefreshLock` on a Redis connection. One instance serves one process."""

    def __init__(
        self,
        connection: Any,
        length_s: float,
        name: str = LOCK_NAME,
        clock: LeaseClock | None = None,
    ) -> None:
        self._connection = connection
        self._length_s = length_s
        self._name = name
        self._clock = clock or LeaseClock()
        self._lock: Any = None
        self._lease: _Lease | None = None
        self._stop: threading.Event | None = None
        self._renewer: threading.Thread | None = None

    def acquire(self) -> bool:
        # one token for the step and its renewal thread
        lock = self._connection.lock(self._name, timeout=self._length_s, thread_local=False)
        sent_at = self._clock.monotonic()
        if not lock.acquire(blocking=False):
            return False
        lease = _Lease(self._name, self._length_s, sent_at, self._clock)
        stop = threading.Event()
        renewer = threading.Thread(
            target=self._renew, args=(lock, lease, stop), daemon=True, name="refresh-lock-renewal"
        )
        self._lock, self._lease, self._stop, self._renewer = lock, lease, stop, renewer
        renewer.start()
        return True

    def held(self) -> bool:
        return self._lease is not None and self._lease.held()

    def release(self) -> None:
        lock, stop, renewer = self._lock, self._stop, self._renewer
        self._lock = self._lease = self._stop = self._renewer = None
        if lock is None or stop is None or renewer is None:
            return
        stop.set()
        # bounded: an extension that lands after the release finds the key gone and changes nothing
        renewer.join(RENEWAL_JOIN_S)
        try:
            lock.release()
        except LockError:
            pass  # it expired, or another step took it over: there is nothing of ours to release
        except RedisError:
            log.exception("could not release the refresh lock; it expires by itself")

    def _renew(self, lock: Any, lease: _Lease, stop: threading.Event) -> None:
        """Extends the lock every third of its length until `stop` is set (the step is over), or until it
        can no longer be proven: then it is never extended again."""
        while not self._clock.wait(stop, self._length_s / 3):
            if not lease.held():
                log.warning("the refresh lock expired before it could be extended")
                return
            sent_at = self._clock.monotonic()
            try:
                lock.extend(self._length_s, replace_ttl=True)
            except LockError:
                lease.lose()
                log.warning("the refresh lock was taken over")
                return
            except Exception:  # tried again at the next third while the lock lasts
                log.exception("could not extend the refresh lock")
                continue
            lease.renewed(sent_at)
