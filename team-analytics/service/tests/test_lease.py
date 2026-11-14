"""The shared refresh lease: never left claimed after a failure, held for as long as a step runs, and lost
for good once it could have run out.

The lease's time is supplied (`SuppliedClock`): it stands still until a test moves it, so no outcome here
depends on how long a refresh takes on this host. What is left of real time is PATIENCE_S. One test
(`ProductionClockTest`) runs on the service's own lease clock, ClickHouse's, with a short lease.
"""

import dataclasses
import threading
import time
from datetime import UTC, datetime, timedelta

from team_analytics.refresh import LeaseClock
from team_analytics.service import Service

from tests.support import FakeUser, StackTestCase, clickhouse_client, working_time

# Real seconds a test waits for something that should happen at once before it calls it stuck.
PATIENCE_S = 60
ORG = 7
ALICE = (11, "alice")
MINUTE = 60_000


class SuppliedClock(LeaseClock):
    """The lease clock of one test, shared by its replicas as ClickHouse's clock is: time passes only when
    the test says so. Each reading of the database's time is a microsecond after the last, so claims keep
    the order they were written in, as they do on a running clock."""

    def __init__(self) -> None:
        self._start = datetime.now(UTC)  # the real day: the lease table drops rows a day old
        self._us = 0
        self._moved = threading.Condition()
        self._due: list[int] = []  # when each thread waiting on this clock is due

    def monotonic(self) -> float:
        with self._moved:
            return self._us / 1_000_000

    def database_now(self) -> str:
        with self._moved:
            self._us += 1
            return (self._start + timedelta(microseconds=self._us)).strftime("%Y-%m-%d %H:%M:%S.%f")

    def wait(self, stop: threading.Event, seconds: float) -> bool:
        with self._moved:
            due = self._us + round(seconds * 1_000_000)
            self._due.append(due)
            self._moved.notify_all()
            try:
                while self._us < due and not stop.is_set():
                    self._moved.wait(0.01)  # `stop` is set without telling this clock: look again soon
            finally:
                self._due.remove(due)
            return stop.is_set()

    def advance(self, seconds: float) -> None:
        with self._moved:
            self._us += round(seconds * 1_000_000)
            self._moved.notify_all()

    def renewal_awaited(self, timeout: float) -> bool:
        """Waits until a replica's renewal thread waits for its next renewal; False when none got there."""
        with self._moved:
            return self._moved.wait_for(lambda: any(due > self._us for due in self._due), timeout)


class ClickHouseBlip(Exception):
    pass


def fail_once(sql, method: str, file: str) -> None:
    """Makes `sql.<method>(file, ...)` fail the next time, as a dropped ClickHouse connection would."""
    original = getattr(sql, method)
    failed = []

    def run(name, *args, **kwargs):
        if name == file and not failed:
            failed.append(name)
            raise ClickHouseBlip(name)
        return original(name, *args, **kwargs)

    setattr(sql, method, run)


def on_renewals(sql, behaviour) -> None:
    """Runs `behaviour(write)` for every renewal of the lease by this replica: a write of
    `control/lock_claim.sql` after the claim itself. `write()` performs the renewal."""
    original = sql.statements
    claims = []

    def run(name, *args, **kwargs):
        if name != "control/lock_claim.sql":
            return original(name, *args, **kwargs)
        claims.append(name)
        if len(claims) == 1:
            return original(name, *args, **kwargs)
        return behaviour(lambda: original(name, *args, **kwargs))

    sql.statements = run


def hold_after_computing(sql, inside: threading.Event, go_on: threading.Event) -> None:
    """Makes this replica's refresh in thread `replica-a` wait, once its refresh files have run and before it
    marks the hours, until `go_on` is set (`inside` is set when it waits): at its check for a cutover to store,
    which comes between the two."""
    original = sql.rows

    def run(name, *args, **kwargs):
        if name == "control/cutover_due.sql" and threading.current_thread().name == "replica-a":
            inside.set()
            go_on.wait()
        return original(name, *args, **kwargs)

    sql.rows = run


def kill(replica) -> None:
    """What killing a replica's process comes to: from now on nothing from it reaches ClickHouse, neither a
    renewal nor a release, and its threads end where they are."""

    def dead(*_args, **_kwargs):
        raise SystemExit

    replica.sql.statements = replica.sql.rows = dead


class LeaseTestCase(StackTestCase):
    """Replicas of one stack on one supplied lease clock; replica A can be held inside its step."""

    def setUp(self) -> None:
        self.clock = SuppliedClock()
        self.stack_options = {"lease_clock": self.clock}
        super().setUp()
        self.lease_s = self.stack.config.refresh_lease_s
        self.inside, self.go_on = threading.Event(), threading.Event()
        self.addCleanup(self.go_on.set)

    def held_replica(self):
        """A replica whose refresh waits, after claiming the lease and before computing, until `go_on` is set."""

        def clock():
            if threading.current_thread().name == "replica-a":
                self.inside.set()
                self.go_on.wait()
            return self.stack.now

        return self.stack.new_service(clock=clock)

    def start(self, replica) -> tuple[threading.Thread, dict]:
        outcome: dict = {}
        thread = threading.Thread(target=lambda: outcome.update(a=replica.refresh()), name="replica-a", daemon=True)
        thread.start()
        self.assertTrue(self.inside.wait(PATIENCE_S), "replica A did not start refreshing")
        return thread, outcome

    def finish(self, thread: threading.Thread, stuck: str = "replica A's step did not end") -> None:
        """Lets replica A's step go on and waits for it to end."""
        self.go_on.set()
        thread.join(PATIENCE_S)
        self.assertFalse(thread.is_alive(), stuck)

    def a_third_of_the_lease_passes(self) -> None:
        """Moves the clock on by the time between two renewals, once replica A waits for its next one."""
        self.assertTrue(self.clock.renewal_awaited(PATIENCE_S), "replica A is not waiting to renew its lease")
        self.clock.advance(self.lease_s / 3)


class FailureTest(LeaseTestCase):
    def test_a_failed_check_of_the_claim_leaves_no_claim_behind(self):
        replica_a, replica_b = self.stack.new_service(), self.stack.new_service()
        fail_once(replica_a.sql, "rows", "control/lock_holder.sql")
        with self.assertRaises(ClickHouseBlip):
            replica_a.refresh()
        self.assertTrue(replica_b.refresh().ran)
        self.assertTrue(replica_a.refresh().ran)

    def test_a_failed_release_is_tried_again(self):
        replica_a, replica_b = self.stack.new_service(), self.stack.new_service()
        fail_once(replica_a.sql, "statements", "control/lock_release.sql")
        self.assertTrue(replica_a.refresh().ran)
        self.assertTrue(replica_b.refresh().ran)


class LongStepTest(LeaseTestCase):
    def test_a_step_longer_than_the_lease_keeps_other_replicas_out(self):
        landed = threading.Semaphore(0)

        def renewal(write):
            write()
            landed.release()

        replica_a, replica_b = self.held_replica(), self.stack.new_service()
        on_renewals(replica_a.sql, renewal)
        thread, outcome = self.start(replica_a)
        # three lease lengths while replica A is still working, from one renewal to the next
        for _ in range(9):
            self.a_third_of_the_lease_passes()
            self.assertTrue(landed.acquire(timeout=PATIENCE_S), "replica A did not renew its lease")
            self.assertFalse(replica_b.refresh().ran, "replica B refreshed while A held the lease")
        self.finish(thread)
        self.assertTrue(outcome["a"].ran)
        self.assertTrue(replica_b.refresh().ran)


class LostLeaseTest(LeaseTestCase):
    """A replica that can no longer prove it holds the lease stops its step; an expired claim stays expired."""

    def test_a_replica_whose_renewals_failed_past_the_lease_stops_its_step(self):
        failing, tried = threading.Event(), threading.Semaphore(0)
        failing.set()

        def renewal(write):
            try:
                if failing.is_set():
                    raise ClickHouseBlip("renewal")
                return write()
            finally:
                tried.release()

        replica_a, replica_b = self.held_replica(), self.stack.new_service()
        on_renewals(replica_a.sql, renewal)
        thread, outcome = self.start(replica_a)
        for _ in range(2):  # the renewals due inside the lease both fail
            self.a_third_of_the_lease_passes()
            self.assertTrue(tried.acquire(timeout=PATIENCE_S), "replica A did not try to renew its lease")
        self.a_third_of_the_lease_passes()
        # A's claim has run out while its renewals failed; B takes the lease and refreshes
        self.assertTrue(replica_b.refresh().ran, "the other replica never got the lease")
        failing.clear()  # A's renewals would succeed again
        self.clock.advance(self.lease_s / 3)
        self.finish(thread)
        self.assertFalse(outcome["a"].ran, "replica A finished a refresh after losing the lease")
        self.assertTrue(replica_a.refresh().ran, "replica A's next step did not start cleanly")

    def test_a_renewal_that_lands_after_the_claim_expired_does_not_take_the_lease_back(self):
        sent, land, landed = threading.Event(), threading.Event(), threading.Event()
        self.addCleanup(land.set)

        def late_renewal(write):
            if landed.is_set():
                return write()
            sent.set()
            land.wait()
            try:
                return write()
            finally:
                landed.set()

        replica_a, replica_b, replica_c = self.held_replica(), self.stack.new_service(), self.stack.new_service()
        on_renewals(replica_a.sql, late_renewal)
        thread, _ = self.start(replica_a)
        self.a_third_of_the_lease_passes()
        self.assertTrue(sent.wait(PATIENCE_S), "replica A did not try to renew its lease")
        self.clock.advance(self.lease_s * 2 / 3)  # A's claim has run out with its renewal still on the way
        self.assertTrue(replica_b.refresh().ran, "the other replica never got the lease")
        land.set()
        self.assertTrue(landed.wait(PATIENCE_S), "replica A's renewal never landed")
        self.assertTrue(replica_c.refresh().ran, "the expired claim of replica A came back to life")
        self.finish(thread)

    def test_work_done_after_the_lease_was_lost_stays_out_of_status_and_figures(self):
        self.stack.cvat.add_user("lead", FakeUser(2, "lead", memberships={"org7": (ORG, "owner", True)}))
        self.stack.add_events([working_time(self.stack.now - timedelta(minutes=10), MINUTE, user=ALICE, org=ORG)])
        self.assertTrue(self.stack.service.refresh().ran)
        before = self.status_and_figures()
        self.assertEqual(before[1], MINUTE)

        # replica A computes with two more minutes, five minutes later, and loses the lease before it marks them
        self.stack.add_events([working_time(self.stack.now - timedelta(minutes=5), 2 * MINUTE, user=ALICE, org=ORG)])
        self.stack.now += timedelta(minutes=5)
        failing = threading.Semaphore(0)

        def failing_renewal(_write):
            failing.release()
            raise ClickHouseBlip("renewal")

        replica_a = self.stack.new_service()
        hold_after_computing(replica_a.sql, self.inside, self.go_on)
        on_renewals(replica_a.sql, failing_renewal)
        thread, outcome = self.start(replica_a)
        for _ in range(2):  # the renewals due inside the lease both fail
            self.a_third_of_the_lease_passes()
            self.assertTrue(failing.acquire(timeout=PATIENCE_S), "replica A did not try to renew its lease")
        self.a_third_of_the_lease_passes()  # the lease has run out
        self.finish(thread)
        self.assertEqual(self.status_and_figures(), before, "replica A's work after losing the lease became visible")
        self.assertFalse(outcome["a"].ran)

    def status_and_figures(self) -> tuple[str | None, int]:
        """The latest refresh as status reports it, and Alice's working time in this week's overview."""
        status, body = self.stack.get("/team-analytics-api/v1/status", "lead", org="org7")
        self.assertEqual(status, 200, body)
        code, overview = self.stack.overview("lead", org="org7")
        self.assertEqual(code, 200, overview)
        rows = overview["by_annotator"]["rows"]
        return (body["refresh"]["last_success_at"],
                sum(row["working_time_ms"] for row in rows if row["user_id"] == ALICE[0]))

    def test_a_renewal_that_hangs_does_not_hold_up_the_release(self):
        renewing, hang = threading.Event(), threading.Event()
        self.addCleanup(hang.set)

        def hanging_renewal(write):
            renewing.set()
            hang.wait()
            return write()

        replica_a, replica_b = self.held_replica(), self.stack.new_service()
        on_renewals(replica_a.sql, hanging_renewal)
        thread, outcome = self.start(replica_a)
        self.a_third_of_the_lease_passes()
        self.assertTrue(renewing.wait(PATIENCE_S), "replica A never renewed its lease")
        self.finish(thread, "replica A's step waited for a hanging renewal")
        self.assertTrue(outcome["a"].ran)
        self.assertTrue(replica_b.refresh().ran, "replica A did not release the lease")


def renewal_attempts(sql) -> threading.Semaphore:
    """Released each time this replica tries to renew its lease, before the renewal is sent (and fails, once
    the replica is killed). Counts from now on; the claim itself is made before."""
    tried = threading.Semaphore(0)
    original = sql.statements

    def run(name, *args, **kwargs):
        if name == "control/lock_claim.sql":
            tried.release()
        return original(name, *args, **kwargs)

    sql.statements = run
    return tried


class KilledHolderTest(LeaseTestCase):
    """A replica killed inside a step releases nothing and renews nothing. The others carry on once its lease
    has run out: two minutes after its claim, or after the last renewal of it, which comes every 40 seconds.
    A holder that is alive keeps the lease past those two minutes on the same clock; the kill is what ends it.
    Each renewal the killed holder's renewal thread tries is awaited, so a kill that stopped nothing would
    renew the lease and fail these tests."""

    def renewed(self, landed: threading.Semaphore, times: int) -> None:
        for _ in range(times):
            self.a_third_of_the_lease_passes()
            self.assertTrue(landed.acquire(timeout=PATIENCE_S), "replica A did not renew its lease")

    def test_a_holder_that_is_alive_keeps_the_lease_past_its_length(self):
        landed = threading.Semaphore(0)
        replica_a, replica_b = self.held_replica(), self.stack.new_service()
        on_renewals(replica_a.sql, lambda write: (write(), landed.release()))
        thread, outcome = self.start(replica_a)
        self.renewed(landed, 4)  # 160 s after the claim
        self.assertFalse(replica_b.refresh().ran, "replica B refreshed while A was alive and renewing")
        self.finish(thread)
        self.assertTrue(outcome["a"].ran)

    def test_a_holder_killed_in_mid_step_is_overtaken_once_its_lease_has_run_out(self):
        replica_a, replica_b = self.held_replica(), self.stack.new_service()
        self.start(replica_a)
        kill(replica_a)
        tried = renewal_attempts(replica_a.sql)
        self.a_third_of_the_lease_passes()  # 40 s after the claim
        self.assertTrue(tried.acquire(timeout=PATIENCE_S), "the killed holder's renewal was never due")
        self.clock.advance(79)
        self.assertFalse(replica_b.refresh().ran, "replica B refreshed inside the killed holder's lease")
        self.clock.advance(1)
        self.assertTrue(replica_b.refresh().ran, "replica B is still held up two minutes after the holder was killed")

    def test_a_holder_killed_after_a_renewal_is_overtaken_two_minutes_after_that_renewal(self):
        landed = threading.Semaphore(0)
        replica_a, replica_b = self.held_replica(), self.stack.new_service()
        on_renewals(replica_a.sql, lambda write: (write(), landed.release()))
        self.start(replica_a)
        self.renewed(landed, 1)  # renewed 40 s after the claim
        kill(replica_a)
        tried = renewal_attempts(replica_a.sql)
        self.a_third_of_the_lease_passes()  # 80 s after the claim
        self.assertTrue(tried.acquire(timeout=PATIENCE_S), "the killed holder's renewal was never due")
        self.clock.advance(79)
        self.assertFalse(replica_b.refresh().ran, "replica B refreshed inside the killed holder's renewed lease")
        self.clock.advance(1)
        self.assertTrue(replica_b.refresh().ran, "replica B is still held up two minutes after the last renewal")


class ProductionClockTest(StackTestCase):
    """The lease on the service's own clock: claims stamped and judged by ClickHouse's time, here with a lease
    of a few seconds. Only a lower bound on ClickHouse's clock is asserted, so a slow host can only make the
    test wait longer."""

    LEASE_S = 4

    def test_a_killed_holder_is_overtaken_once_its_lease_has_run_out_on_clickhouses_clock(self):
        config = dataclasses.replace(self.stack.config, refresh_lease_s=self.LEASE_S)
        inside, go_on = threading.Event(), threading.Event()
        self.addCleanup(go_on.set)

        def clock():
            if threading.current_thread().name == "holder":
                inside.set()
                go_on.wait()
            return self.stack.now

        holder, other = Service(config, clock=clock), Service(config, clock=lambda: self.stack.now)
        server = clickhouse_client()

        def clickhouse_now() -> datetime:
            return server.query("SELECT now64(6, 'Etc/UTC')").result_rows[0][0]

        before_the_claim = clickhouse_now()
        threading.Thread(target=holder.refresh, name="holder", daemon=True).start()
        self.assertTrue(inside.wait(PATIENCE_S), "the holder did not start refreshing")
        kill(holder)
        deadline = time.monotonic() + PATIENCE_S
        while not other.refresh().ran:
            self.assertLess(time.monotonic(), deadline, "the other replica never got the lease")
            time.sleep(0.5)
        taken_after = (clickhouse_now() - before_the_claim).total_seconds()
        self.assertGreaterEqual(taken_after, self.LEASE_S, "the other replica got the lease inside the holder's")

