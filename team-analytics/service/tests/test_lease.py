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
