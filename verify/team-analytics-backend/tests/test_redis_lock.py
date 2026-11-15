"""The refresh lock kept in Redis (core/redis_lock.py), against a real Redis, and a Refresher that is given it."""

import os
import threading
import time
import unittest
import uuid

import redis

from cvat.apps.team_analytics.core.config import Config
from cvat.apps.team_analytics.core.redis_lock import RedisLock
from cvat.apps.team_analytics.core.refresh import LeaseClock, Refresher

# Short enough to wait out, long enough for a slow host: the lock is extended every third of it.
LENGTH_S = 1.5


def connection():
    return redis.Redis(host=os.environ["REDIS_HOST"], port=int(os.environ.get("REDIS_PORT", "6379")))


class DeadHolderClock(LeaseClock):
    """The clock of a holder that died right after taking the lock: its renewal thread ends at once, so the
    lock is never extended."""

    def wait(self, stop: threading.Event, seconds: float) -> bool:
        return True


class RedisLockCase(unittest.TestCase):
    def setUp(self) -> None:
        self.redis = connection()
        self.name = f"ta-test-lock-{uuid.uuid4().hex}"
        self.addCleanup(self.redis.delete, self.name)

    def lock(self, clock: LeaseClock | None = None) -> RedisLock:
        lock = RedisLock(self.redis, LENGTH_S, name=self.name, clock=clock)
        self.addCleanup(lock.release)
        return lock


class RedisLockTest(RedisLockCase):
    def test_only_one_holder_at_a_time(self):
        first, second = self.lock(), self.lock()
        self.assertTrue(first.acquire())
        self.assertFalse(second.acquire(), "a second holder must be refused without waiting")
        self.assertTrue(first.held())
        self.assertFalse(second.held())

        first.release()
        self.assertTrue(second.acquire(), "a released lock is free at once")

    def test_a_step_longer_than_the_lock_keeps_it(self):
        holder, other = self.lock(), self.lock()
        self.assertTrue(holder.acquire())
        time.sleep(LENGTH_S * 2)
        self.assertTrue(holder.held(), "the lock is extended while the step runs")
        self.assertFalse(other.acquire())

    def test_a_holder_that_died_is_overtaken_once_the_lock_expired(self):
        dead, next_holder = self.lock(DeadHolderClock()), self.lock()
        self.assertTrue(dead.acquire())
        self.assertFalse(next_holder.acquire(), "not before the lock expired")

        time.sleep(LENGTH_S + 0.3)
        self.assertTrue(next_holder.acquire(), "after its length the lock of a dead holder is free")
        self.assertFalse(dead.held(), "a holder whose lock expired can no longer prove it holds it")

    def test_a_holder_cannot_prove_its_lock_shortly_before_it_runs_out(self):
        dead = self.lock(DeadHolderClock())
        self.assertTrue(dead.acquire())
        self.assertTrue(dead.held())
        time.sleep(LENGTH_S * 0.95)
        self.assertFalse(dead.held(), "within the last tenth the lock counts as lost")
        self.assertFalse(dead.held(), "and stays lost")

    def test_a_holder_whose_lock_was_taken_over_learns_it_at_its_next_extension(self):
        holder, intruder = self.lock(), self.lock()
        self.assertTrue(holder.acquire())
        self.redis.delete(self.name)  # as if it had expired
        self.assertTrue(intruder.acquire())

        time.sleep(LENGTH_S / 3 + 0.4)
        self.assertFalse(holder.held(), "its extension found another holder")
        holder.release()  # nothing of its own to release, and no error
        self.assertTrue(intruder.held(), "the release of the old holder left the new holder's lock alone")

    def test_release_without_a_lock_does_nothing(self):
        self.lock().release()


class RefresherWithLockTest(RedisLockCase):
    """A Refresher that is given a lock runs its steps under it, not under the lease in ClickHouse: no
    statement is sent here, so there is no ClickHouse to reach."""

    def refresher(self, clock: LeaseClock | None = None) -> Refresher:
        return Refresher(Config(), sql=None, clock=None, lock=self.lock(clock))

    def test_a_step_runs_under_the_lock_and_gives_it_back(self):
        refresher, other = self.refresher(), self.lock()
        seen = {}

        def work():
            seen["held_by_another"] = other.acquire()
            refresher.ensure_lease()
            return "done"

        self.assertEqual(refresher.leased(work), (True, "done"))
        self.assertFalse(seen["held_by_another"], "the lock is held while the step runs")
        self.assertTrue(other.acquire(), "and free after it")

    def test_a_step_is_refused_while_another_holds_the_lock(self):
        other = self.lock()
        self.assertTrue(other.acquire())
        ran = []
        self.assertEqual(self.refresher().leased(lambda: ran.append(1)), (False, None))
        self.assertEqual(ran, [], "the step must not run")

    def test_a_failing_step_still_gives_the_lock_back(self):
        refresher = self.refresher()

        def work():
            raise RuntimeError("the step failed")

        with self.assertRaises(RuntimeError):
            refresher.leased(work)
        self.assertTrue(self.lock().acquire())

    def test_a_step_that_lost_the_lock_stops_before_its_next_write(self):
        refresher = self.refresher(DeadHolderClock())
        written = []

        def work():
            refresher.ensure_lease()
            written.append("first")
            time.sleep(LENGTH_S)  # the lock runs out and is never extended
            refresher.ensure_lease()
            written.append("second")

        self.assertEqual(refresher.leased(work), (False, None))
        self.assertEqual(written, ["first"], "nothing is written once the lock cannot be proven")

    def test_outside_a_step_nothing_is_checked(self):
        self.refresher().ensure_lease()
