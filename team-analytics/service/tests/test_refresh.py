"""Refresh of the stored totals: trailing window, whole-hour replacement, one refresh at a time."""

import threading
from datetime import timedelta

from tests.support import NOW, FakeUser, StackTestCase, at, clickhouse_client, working_time

ORG = 7
ALICE = (11, "alice")


class RefreshTest(StackTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.cvat.add_user("lead", FakeUser(2, "lead", memberships={"org7": (ORG, "owner", True)}))

    def alice_ms(self) -> int | None:
        status, body = self.stack.overview("lead", org="org7")
        self.assertEqual(status, 200, body)
        rows = [row["working_time_ms"] for row in body["by_annotator"]["rows"] if row["user_id"] == ALICE[0]]
        return rows[0] if rows else None

    def test_figures_appear_only_after_a_refresh(self):
        self.stack.add_events([working_time(at("2026-11-13 14:00:00"), 100_000, user=ALICE, org=ORG)])
        self.assertIsNone(self.alice_ms())
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
        self.stack.add_events([
            working_time(at("2026-11-11 16:00:00"), 10_000, user=ALICE, org=ORG),  # inside 48 h of 15:20
            working_time(at("2026-11-11 14:59:59"), 20_000, user=ALICE, org=ORG),  # before the window
        ])
        self.stack.refresh()
        self.assertEqual(self.alice_ms(), 10_000)

    def test_only_one_refresh_runs_at_a_time_across_service_instances(self):
        replicas = [self.stack.new_service() for _ in range(3)]
        results = []
        start = threading.Barrier(len(replicas))

        def run(service):
            start.wait()
            results.append(service.refresh().ran)

        threads = [threading.Thread(target=run, args=(service,)) for service in replicas]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sorted(results), [False, False, True])
        # once it is finished, the next refresh runs
        self.assertTrue(replicas[0].refresh().ran)

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
