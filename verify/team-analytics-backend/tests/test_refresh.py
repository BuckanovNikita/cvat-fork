"""Refresh of the stored totals: trailing window, whole-hour replacement, one refresh at a time (the refresh lock
in Redis, shared by every engine of a stack as by the worker processes)."""

import threading
import time
from datetime import timedelta

from tests.support import NOW, FakeUser, StackTestCase, at, clickhouse_client, working_time

ORG = 7
ALICE = (11, "alice")


class RefreshTest(StackTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.callers.add_user("lead", FakeUser(2, "lead", groups=["admin"], memberships={"org7": (ORG, "owner", True)}))

    def alice_ms(self) -> int | None:
        status, body = self.stack.overview("lead", org="org7")
        self.assertEqual(status, 200, body)
        rows = [row["working_time_ms"] for row in body["by_annotator"]["rows"] if row["user_id"] == ALICE[0]]
        return rows[0] if rows else None

    def test_figures_appear_only_after_a_refresh(self):
        self.stack.add_events([working_time(at("2026-11-13 14:00:00"), 100_000, user=ALICE, org=ORG)])
        status, body = self.stack.overview("lead", org="org7")
        self.assertEqual(status, 200, body)
        # nothing is processed before the first refresh: no figures at all
        self.assertEqual((body["processed"], body["by_annotator"]), (False, None))
        self.stack.refresh()
        self.assertEqual(self.alice_ms(), 100_000)

    def test_a_late_event_in_a_refreshed_hour_is_counted_once_by_the_next_refresh(self):
        self.stack.add_events([working_time(at("2026-11-13 14:00:00"), 100_000, user=ALICE, org=ORG)])
        self.stack.refresh()
        self.stack.refresh(NOW + timedelta(minutes=10))
        self.assertEqual(self.alice_ms(), 100_000)

        # arrives a day late, stamped with the browser's time inside an hour already stored
        self.stack.add_events([working_time(at("2026-11-12 16:30:00"), 50_000, user=ALICE, org=ORG)])
        self.assertEqual(self.alice_ms(), 100_000)
        self.stack.refresh(NOW + timedelta(minutes=20))
        self.assertEqual(self.alice_ms(), 150_000)
        self.stack.refresh(NOW + timedelta(minutes=30))
        self.assertEqual(self.alice_ms(), 150_000)

    def test_a_refresh_recomputes_the_trailing_48_hours_only(self):
        self.stack.add_events([working_time(at("2026-11-11 16:00:00"), 10_000, user=ALICE, org=ORG)])  # inside
        self.stack.refresh()
        self.stack.settle()  # history computes the 11th and 12th: the week is processed
        # arrives late, before the window of 15:20 (which starts at 16:00 on the 11th)
        self.stack.add_events([working_time(at("2026-11-11 14:59:59"), 20_000, user=ALICE, org=ORG)])
        self.stack.refresh()
        self.assertEqual(self.alice_ms(), 10_000)

    def test_no_other_refresh_runs_while_one_is_in_progress_on_another_instance(self):
        inside, release = threading.Event(), threading.Event()

        def clock_that_holds_replica_a():
            # worker A's refresh reads the clock while it holds the refresh lock; keep it there
            if threading.current_thread().name == "replica-a":
                inside.set()
                release.wait(30)
            return self.stack.now

        replica_a = self.stack.new_engine(clock=clock_that_holds_replica_a)
        replica_b = self.stack.new_engine()
        outcome = {}
        thread = threading.Thread(target=lambda: outcome.update(a=replica_a.refresh()), name="replica-a")
        thread.start()
        try:
            self.assertTrue(inside.wait(30), "worker A did not start refreshing")
            self.assertFalse(replica_b.refresh().ran)
            self.assertFalse(replica_a.refresh().ran)  # another thread of the same worker process
        finally:
            release.set()
            thread.join(30)
        self.assertTrue(outcome["a"].ran)
        # once it is finished, the next refresh runs
        self.assertTrue(replica_b.refresh().ran)

    def test_concurrent_refreshes_on_several_instances_do_not_overlap(self):
        replicas = [self.stack.new_engine() for _ in range(3)]
        results = []
        start = threading.Barrier(len(replicas))

        def run(engine):
            start.wait()
            results.append(engine.refresh().ran)

        threads = [threading.Thread(target=run, args=(engine,)) for engine in replicas]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        # steps started together: one takes the lock in Redis, the others step aside without waiting
        self.assertEqual(sorted(results), [False, False, True])

    def test_each_stored_hour_keeps_only_the_newest_refresh(self):
        self.stack.add_events([working_time(at("2026-11-13 14:00:00"), 100_000, user=ALICE, org=ORG)])
        for minutes in (0, 10, 20):
            self.stack.refresh(NOW + timedelta(minutes=minutes))
        totals = clickhouse_client(self.stack.totals_db)
        deadline = time.monotonic() + 60
        while True:
            mutations = totals.query(
                "SELECT is_done, latest_fail_reason FROM system.mutations WHERE database = currentDatabase()"
            ).result_rows
            if all(done for done, _ in mutations) or time.monotonic() > deadline:
                break
            time.sleep(0.5)
        self.assertTrue(mutations)
        self.assertEqual([reason for _, reason in mutations if reason], [])
        self.assertTrue(all(done for done, _ in mutations), mutations)
        copies = totals.query(
            "SELECT hour, uniqExact(version) FROM working_time_hourly GROUP BY hour HAVING uniqExact(version) > 1"
        ).result_rows
        self.assertEqual(copies, [])
        markers = totals.query(
            "SELECT hour, count() FROM hour_versions GROUP BY hour HAVING count() > 1"
        ).result_rows
        self.assertEqual(markers, [])
        self.assertEqual(self.alice_ms(), 100_000)

    def test_totals_are_stored_in_their_own_database_and_events_are_only_read(self):
        self.stack.add_events([working_time(at("2026-11-13 14:00:00"), 100_000, user=ALICE, org=ORG)])
        events = clickhouse_client(self.stack.events_db)
        before = events.query("SELECT name, total_rows FROM system.tables WHERE database = currentDatabase()").result_rows
        self.stack.refresh()
        after = events.query("SELECT name, total_rows FROM system.tables WHERE database = currentDatabase()").result_rows
        self.assertEqual(after, before)
        self.assertEqual(before, [("events", 1)])

        totals = clickhouse_client(self.stack.totals_db)
        stored = totals.query(
            "SELECT hour, org_id, project_id, task_id, user_id, working_ms FROM working_time_hourly"
        ).result_rows
        self.assertEqual([row[1:] for row in stored], [(ORG, 1, 1, 11, 100_000)])
        self.assertEqual(stored[0][0].strftime("%Y-%m-%d %H:%M"), "2026-11-13 14:00")


# Real seconds a test waits for something that should happen at once before it calls it stuck.
PATIENCE_S = 60
# A short refresh lock for the worker that loses it: extended every third of it, so a takeover is noticed soon.
SHORT_LOCK_S = 1.5
MINUTE = 60_000


def hold_after_computing(sql, inside: threading.Event, go_on: threading.Event) -> None:
    """Makes this engine's refresh in thread `replica-a` wait, once its refresh files have run and before it
    marks the hours, until `go_on` is set (`inside` is set when it waits): at its check for a cutover to store,
    which comes between the two."""
    original = sql.rows

    def run(name, *args, **kwargs):
        if name == "control/cutover_due.sql" and threading.current_thread().name == "replica-a":
            inside.set()
            go_on.wait()
        return original(name, *args, **kwargs)

    sql.rows = run


class LostLockTest(StackTestCase):
    """A worker that can no longer prove it holds the refresh lock stops its step before the next write, so nothing
    it computed becomes visible (converted from the lease tests of the service: there the lease ran out in
    ClickHouse; here the lock in Redis is taken over, as after it expired, and the holder learns it at its next
    extension)."""

    def setUp(self) -> None:
        super().setUp()
        self.stack.callers.add_user("lead", FakeUser(2, "lead", groups=["admin"], memberships={"org7": (ORG, "owner", True)}))
        self.inside, self.go_on = threading.Event(), threading.Event()
        self.addCleanup(self.go_on.set)

    def test_work_done_after_the_lock_was_lost_stays_out_of_status_and_figures(self):
        self.stack.add_events([working_time(self.stack.now - timedelta(minutes=10), MINUTE, user=ALICE, org=ORG)])
        self.assertTrue(self.stack.engine.refresh().ran)
        before = self.status_and_figures()
        self.assertEqual(before[1], MINUTE)

        # worker A computes with two more minutes, five minutes later, and loses the lock before it marks them
        self.stack.add_events([working_time(self.stack.now - timedelta(minutes=5), 2 * MINUTE, user=ALICE, org=ORG)])
        self.stack.now += timedelta(minutes=5)
        replica_a = self.stack.new_engine(lock=self.stack.lock(SHORT_LOCK_S))
        hold_after_computing(replica_a.sql, self.inside, self.go_on)
        outcome: dict = {}
        thread = threading.Thread(target=lambda: outcome.update(a=replica_a.refresh()), name="replica-a", daemon=True)
        thread.start()
        self.assertTrue(self.inside.wait(PATIENCE_S), "worker A did not start refreshing")

        # the lock is gone (as if it had expired) and another worker holds it
        self.stack.redis.delete(self.stack.lock_name)
        intruder = self.stack.lock()
        self.assertTrue(intruder.acquire())
        self.addCleanup(intruder.release)
        time.sleep(SHORT_LOCK_S / 3 + 0.5)  # worker A's next extension finds another holder

        self.go_on.set()
        thread.join(PATIENCE_S)
        self.assertFalse(thread.is_alive(), "worker A's step did not end")
        self.assertFalse(outcome["a"].ran)
        self.assertEqual(self.status_and_figures(), before, "worker A's work after losing the lock became visible")
        self.assertTrue(intruder.held(), "worker A's release left the new holder's lock alone")

    def status_and_figures(self) -> tuple[str | None, int]:
        """The latest refresh as status reports it, and Alice's working time in this week's overview."""
        status, body = self.stack.get("/api/team-analytics/status", "lead", org="org7")
        self.assertEqual(status, 200, body)
        code, overview = self.stack.overview("lead", org="org7")
        self.assertEqual(code, 200, overview)
        rows = overview["by_annotator"]["rows"]
        return (body["refresh"]["last_success_at"],
                sum(row["working_time_ms"] for row in rows if row["user_id"] == ALICE[0]))
