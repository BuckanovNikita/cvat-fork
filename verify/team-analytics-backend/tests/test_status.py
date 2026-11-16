"""Status: when the figures were last refreshed successfully, and whether that is too long ago."""

from datetime import timedelta

from tests.support import NOW, FakeUser, StackTestCase, at, clickhouse_client, working_time

ORG = 7
ALICE = (11, "alice")


class FreshnessTest(StackTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.callers.add_user("lead", FakeUser(2, "lead", groups=["admin"], memberships={"org7": (ORG, "owner", True)}))
        self.stack.add_events([working_time(at("2026-11-13 14:00:00"), 100_000, user=ALICE, org=ORG)])

    def refresh_status(self, session="lead") -> dict:
        status, body = self.stack.get("/api/team-analytics/status", session, org="org7")
        self.assertEqual(status, 200, body)
        return body["refresh"]

    def test_before_any_refresh_there_is_no_time_and_the_figures_count_as_stale(self):
        refresh = self.refresh_status()
        self.assertIsNone(refresh["last_success_at"])
        self.assertTrue(refresh["stale"])

    def test_reports_the_time_of_the_last_successful_refresh(self):
        self.stack.refresh(NOW)
        self.stack.refresh(NOW + timedelta(minutes=10))
        refresh = self.refresh_status()
        self.assertEqual(refresh["last_success_at"], "2026-11-13T15:30:00+00:00")
        self.assertEqual(refresh["now"], "2026-11-13T15:30:00+00:00")
        self.assertEqual(refresh["interval_s"], 600)
        self.assertFalse(refresh["stale"])

    def test_stale_once_the_last_refresh_is_more_than_thirty_minutes_ago(self):
        self.stack.refresh(NOW)
        self.stack.now = NOW + timedelta(minutes=30)
        self.assertFalse(self.refresh_status()["stale"])
        self.stack.now = NOW + timedelta(minutes=30, seconds=1)
        self.assertTrue(self.refresh_status()["stale"])

    def test_a_failed_refresh_does_not_count(self):
        self.stack.refresh(NOW)
        clickhouse_client(self.stack.events_db).command("DROP TABLE events")
        with self.assertRaises(Exception):  # noqa: B017 - any failure of the computation
            self.stack.refresh(NOW + timedelta(minutes=40))
        refresh = self.refresh_status()
        self.assertEqual(refresh["last_success_at"], "2026-11-13T15:20:00+00:00")
        self.assertTrue(refresh["stale"])

    def test_a_second_replica_reports_the_refresh_another_one_made(self):
        self.stack.new_engine().refresh()
        self.assertEqual(self.refresh_status()["last_success_at"], "2026-11-13T15:20:00+00:00")
