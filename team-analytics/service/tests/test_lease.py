"""The shared refresh lease: never left claimed after a failure, and held for as long as a step runs."""

import threading
import time

from tests.support import Stack, StackTestCase, wait_for_clickhouse


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


class FailureTest(StackTestCase):
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


class LongStepTest(StackTestCase):
    def setUp(self) -> None:
        wait_for_clickhouse()
        self.stack = Stack(refresh_lease_s=2)
        self.addCleanup(self.stack.close)

    def test_a_step_longer_than_the_lease_keeps_other_replicas_out(self):
        inside, release = threading.Event(), threading.Event()

        def clock_that_holds_replica_a():
            if threading.current_thread().name == "replica-a":
                inside.set()
                release.wait(30)
            return self.stack.now

        replica_a = self.stack.new_service(clock=clock_that_holds_replica_a)
        replica_b = self.stack.new_service()
        outcome = {}
        thread = threading.Thread(target=lambda: outcome.update(a=replica_a.refresh()), name="replica-a")
        thread.start()
        try:
            self.assertTrue(inside.wait(30), "replica A did not start refreshing")
            # three lease lengths while replica A is still working
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                self.assertFalse(replica_b.refresh().ran, "replica B refreshed while A held the lease")
                time.sleep(0.5)
        finally:
            release.set()
            thread.join(30)
        self.assertTrue(outcome["a"].ran)
        self.assertTrue(replica_b.refresh().ran)


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


class LostLeaseTest(StackTestCase):
    """A replica that can no longer prove it holds the lease stops its step; an expired claim stays expired."""

    def setUp(self) -> None:
        wait_for_clickhouse()
        # the hanging-renewal test lets replica A finish a whole refresh after its renewal stalls: a longer lease
        longer = self._testMethodName == "test_a_renewal_that_hangs_does_not_hold_up_the_release"
        self.stack = Stack(refresh_lease_s=8 if longer else 3)
        self.addCleanup(self.stack.close)
        self.inside, self.go_on = threading.Event(), threading.Event()
        self.addCleanup(self.go_on.set)

    def held_replica(self):
        """A replica whose refresh waits, after claiming the lease and before computing, until `go_on` is set."""

        def clock():
            if threading.current_thread().name == "replica-a":
                self.inside.set()
                self.go_on.wait(60)
            return self.stack.now

        return self.stack.new_service(clock=clock)

    def start(self, replica) -> tuple[threading.Thread, dict]:
        outcome: dict = {}
        thread = threading.Thread(target=lambda: outcome.update(a=replica.refresh()), name="replica-a", daemon=True)
        thread.start()
        self.assertTrue(self.inside.wait(30), "replica A did not start refreshing")
        return thread, outcome

    def wait_until_refreshed(self, replica, seconds: float = 20) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if replica.refresh().ran:
                return
            time.sleep(0.3)
        self.fail("the other replica never got the lease")

    def test_a_replica_whose_renewals_failed_past_the_lease_stops_its_step(self):
        failing = threading.Event()
        failing.set()

        def renewal(write):
            if failing.is_set():
                raise ClickHouseBlip("renewal")
            return write()

        replica_a, replica_b = self.held_replica(), self.stack.new_service()
        on_renewals(replica_a.sql, renewal)
        thread, outcome = self.start(replica_a)
        # A's claim expires while its renewals fail; B takes the lease and refreshes
        self.wait_until_refreshed(replica_b)
        failing.clear()  # A's renewals would succeed again
        time.sleep(2)
        self.go_on.set()
        thread.join(30)
        self.assertFalse(thread.is_alive())
        self.assertFalse(outcome["a"].ran, "replica A finished a refresh after losing the lease")
        self.assertTrue(replica_a.refresh().ran, "replica A's next step did not start cleanly")

    def test_a_renewal_that_lands_after_the_claim_expired_does_not_take_the_lease_back(self):
        land, landed = threading.Event(), threading.Event()
        self.addCleanup(land.set)

        def late_renewal(write):
            if landed.is_set():
                return write()
            land.wait(60)
            try:
                return write()
            finally:
                landed.set()

        replica_a, replica_b, replica_c = self.held_replica(), self.stack.new_service(), self.stack.new_service()
        on_renewals(replica_a.sql, late_renewal)
        thread, _ = self.start(replica_a)
        self.wait_until_refreshed(replica_b)  # A's claim has expired
        land.set()
        self.assertTrue(landed.wait(30))
        self.assertTrue(replica_c.refresh().ran, "the expired claim of replica A came back to life")
        self.go_on.set()
        thread.join(30)

    def test_a_renewal_that_hangs_does_not_hold_up_the_release(self):
        renewing, hang = threading.Event(), threading.Event()
        self.addCleanup(hang.set)

        def hanging_renewal(write):
            renewing.set()
            hang.wait(60)
            return write()

        replica_a, replica_b = self.held_replica(), self.stack.new_service()
        on_renewals(replica_a.sql, hanging_renewal)
        thread, outcome = self.start(replica_a)
        self.assertTrue(renewing.wait(30), "replica A never renewed its lease")
        self.go_on.set()
        thread.join(15)
        self.assertFalse(thread.is_alive(), "replica A's step waited for a hanging renewal")
        self.assertTrue(outcome["a"].ran)
        self.assertTrue(replica_b.refresh().ran, "replica A did not release the lease")
