"""One run of the refresh job: steps taken while there is work, within a budget, with reads coming first.

Kept apart from the job itself (jobs.py), which only builds what a run needs from Django's settings, so
that the rules of a run are tested without Django.
"""

from __future__ import annotations

import time
from collections.abc import Callable

from .refresh import RefreshLock


class WatchedLock:
    """The refresh lock, noting what a run needs to know about its steps: whether a step asked if the
    lock is still held, which every step does before each write (`asked`), and whether the answer was
    ever no (`lost`)."""

    def __init__(self, lock: RefreshLock) -> None:
        self._lock = lock
        self.asked = False
        self.lost = False

    def acquire(self) -> bool:
        return self._lock.acquire()

    def held(self) -> bool:
        self.asked = True
        held = self._lock.held()
        if not held:
            self.lost = True
        return held

    def release(self) -> None:
        self._lock.release()


def refresh_run(
    step: Callable[[], float],
    lock: WatchedLock,
    *,
    budget_s: float,
    reads_waiting: Callable[[], bool],
    advance_generation: Callable[[], None],
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    """Takes steps (`step` returns 0 when it did work and there may be more) until there is none, the
    budget has passed, or a read is waiting: reads come before history. The first step always runs, and
    it is the refresh of recent hours whenever that is due, so the refresh is never put off.

    The generation of the totals is advanced once, when the run ends, if any step may have changed what
    readers see: a step that did work, a step that lost the lock on the way, or a step that failed after
    it had reached a write (it may have made hours visible before it failed). Once for the run, not after
    every step: while history is being filled a step ends several times a second, and every advance sends
    each request back to the worker.

    A run with nothing to do advances nothing, so answers stay cached between refreshes. Nor does a step
    that failed before any write, which is every step while ClickHouse cannot be reached: the answers in
    the cache are then all there is, and they stay usable.
    """
    deadline = monotonic() + budget_s
    wrote = False
    try:
        while True:
            lock.asked = False
            try:
                worked = step() == 0
            except Exception:
                # a step asks whether the lock is held before each write, and before nothing else
                wrote = wrote or lock.asked
                raise
            wrote = wrote or worked or lock.lost
            if not worked or monotonic() >= deadline or reads_waiting():
                break
    finally:
        if wrote:
            advance_generation()
