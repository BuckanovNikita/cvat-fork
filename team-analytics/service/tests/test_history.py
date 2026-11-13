"""Processed history: the fill of older days, the daily recount and late events, as status and figures show them.

The service works in steps (`Service.step()`), as its loop runs them: the ten-minute refresh of recent hours
when it is due, else the daily check when it is due, else one day of history.
"""

from datetime import timedelta

from tests.support import NOW, FakeUser, StackTestCase, at, working_time

ORG = 7
ALICE = (11, "alice")
MINUTE = 60_000


class HistoryCase(StackTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.cvat.add_user("lead", FakeUser(2, "lead", memberships={"org7": (ORG, "owner", True)}))

    def step(self, times: int = 1) -> None:
        for _ in range(times):
            self.stack.service.step()

    def history(self, **query) -> dict:
        status, body = self.stack.get("/team-analytics-api/v1/status", "lead", org="org7", **query)
        self.assertEqual(status, 200, body)
        return body["history"]

    def overview(self, **query) -> dict:
        status, body = self.stack.overview("lead", org="org7", **query)
        self.assertEqual(status, 200, body)
        return body

    def alice_ms(self, **query) -> int:
        rows = self.overview(**query)["by_annotator"]["rows"]
        return sum(row["working_time_ms"] for row in rows if row["user_id"] == ALICE[0])

    def fill(self) -> None:
        """Steps until history is complete (bounded, so a fill that never ends fails the test)."""
        for _ in range(40):
            if self.history()["complete"]:
                return
            self.step()
        self.fail(f"history not complete: {self.history()}")


class FillTest(HistoryCase):
    def setUp(self) -> None:
        super().setUp()
        # now = Friday 2026-11-13 15:20 UTC; the ten-minute refresh covers 2026-11-11 16:00 onwards
        self.stack.add_events([
            working_time(at("2026-11-05 10:00:00"), 1 * MINUTE, user=ALICE, org=ORG),
            working_time(at("2026-11-08 10:00:00"), 2 * MINUTE, user=ALICE, org=ORG),
            working_time(at("2026-11-10 10:00:00"), 4 * MINUTE, user=ALICE, org=ORG),
            working_time(at("2026-11-11 10:00:00"), 8 * MINUTE, user=ALICE, org=ORG),
            working_time(at("2026-11-13 10:00:00"), 16 * MINUTE, user=ALICE, org=ORG),
        ])

    def test_history_is_processed_one_day_at_a_time_most_recent_first(self):
        self.assertIsNone(self.history()["ready_from"])  # nothing computed before the first step

        ready = []
        for _ in range(8):
            self.step()
            history = self.history()
            ready.append(None if history["complete"] else history["ready_from"])
        self.assertEqual(ready, [
            "2026-11-11T16:00:00+00:00",  # the ten-minute refresh first: the last 48 hours
            "2026-11-11T16:00:00+00:00",  # 12th: already inside those hours
            "2026-11-11T00:00:00+00:00",
            "2026-11-10T00:00:00+00:00",
            "2026-11-09T00:00:00+00:00",  # an empty day
            "2026-11-08T00:00:00+00:00",
            "2026-11-06T00:00:00+00:00",  # the empty 6th and 7th together
            None,  # the 5th, the first day with events: complete
        ])
        self.assertEqual(self.alice_ms(period="two_weeks"), 31 * MINUTE)

    def test_status_reports_how_far_history_is_processed_and_which_periods_are_available(self):
        self.step(7)  # processed from 2026-11-06 00:00 UTC, the 5th still to do
        history = self.history()
        self.assertEqual(history["ready_from"], "2026-11-06T00:00:00+00:00")
        self.assertFalse(history["complete"])
        self.assertEqual((history["first_day"], history["ready_from_day"]), ("2026-11-05", "2026-11-06"))
        self.assertEqual((history["days_ready"], history["days_total"]), (8, 9))
        self.assertEqual(history["periods"], {"week": True, "two_weeks": False, "month": False, "year": False})
        self.assertIsNone(history["earliest_month"])  # November began before the 6th

        # in New York the 6th begins at 05:00 UTC, also processed; its Week (from the 7th) too
        new_york = self.history(tz="America/New_York")
        self.assertEqual(new_york["ready_from_day"], "2026-11-06")
        self.assertTrue(new_york["periods"]["week"])
        # in Tokyo the 6th began at 15:00 UTC on the 5th: the first whole processed day there is the 7th
        self.assertEqual(self.history(tz="Asia/Tokyo")["ready_from_day"], "2026-11-07")

        self.step()
        history = self.history()
        self.assertTrue(history["complete"])
        self.assertIsNone(history["ready_from"])
        self.assertEqual((history["days_ready"], history["days_total"]), (9, 9))
        self.assertEqual(history["periods"], {"week": True, "two_weeks": True, "month": True, "year": True})

    def test_the_overview_says_whether_its_period_is_wholly_processed(self):
        self.step()  # the last 48 hours only
        self.assertFalse(self.overview()["processed"])
        self.step(6)
        self.assertTrue(self.overview()["processed"])
        self.assertFalse(self.overview(period="month")["processed"])
        self.assertFalse(self.overview(period="month", month="2026-10")["processed"])
        self.step()
        self.assertTrue(self.overview(period="month", month="2026-10")["processed"])
        self.assertTrue(self.overview(period="year")["processed"])


class NothingToProcessTest(HistoryCase):
    def test_before_the_first_refresh_nothing_is_available(self):
        history = self.history()
        self.assertFalse(history["complete"])
        self.assertIsNone(history["ready_from"])
        self.assertEqual(history["periods"], {"week": False, "two_weeks": False, "month": False, "year": False})
        self.assertEqual(history["days_ready"], 0)

    def test_with_only_recent_events_all_periods_are_available_after_the_first_refresh(self):
        self.stack.add_events([working_time(at("2026-11-13 10:00:00"), MINUTE, user=ALICE, org=ORG)])
        self.step()
        history = self.history()
        self.assertTrue(history["complete"])
        self.assertTrue(history["trends_ready"])
        self.assertEqual(history["periods"], {"week": True, "two_weeks": True, "month": True, "year": True})
        self.assertTrue(self.overview(period="year")["processed"])

    def test_without_any_events_all_periods_are_available_after_the_first_refresh(self):
        self.step()
        self.assertTrue(self.history()["complete"])
        self.assertTrue(self.overview(period="year")["processed"])


class TrendsReadinessTest(HistoryCase):
    def test_trends_need_three_complete_weeks_of_processed_history(self):
        self.stack.add_events([working_time(at(f"{day} 10:00:00"), MINUTE, user=ALICE, org=ORG)
                               for day in ("2026-10-14", "2026-10-21", "2026-10-28", "2026-11-04", "2026-11-13")])
        seen = []
        for _ in range(11):
            self.step()
            history = self.history()
            seen.append((history["complete_weeks"], history["trends_ready"]))
        # this week began on Monday 2026-11-09; complete weeks are the ones before it
        self.assertEqual(seen, [
            (0, False), (0, False), (0, False), (0, False), (0, False),  # processed from the 4th at most
            (1, False), (1, False),  # from Oct 29 / 28: the week of Nov 2
            (2, False), (2, False),  # from Oct 22 / 21: and the week of Oct 26
            (3, True),  # from Oct 15: and the week of Oct 19
            (12, True),  # complete
        ])
