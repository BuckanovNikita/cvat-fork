"""Processed history: the fill of older days, the daily recount and late events, as status and figures show them.

The service works in steps (`Service.step()`), as its loop runs them: the ten-minute refresh of recent hours
when it is due, else the daily check when it is due, else one day of history.
"""

import json
import os
import subprocess
import sys
import threading
import time
import traceback
from datetime import UTC, datetime, timedelta
from urllib.error import URLError
from urllib.request import Request, urlopen

from tests.support import NOW, FakeUser, StackTestCase, at, working_time
from tests.test_entry_point import SERVICE_DIR, free_port
from tests.test_sessions import client

ORG = 7
ALICE = (11, "alice")
BOB = (12, "bob")
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

    def settle(self) -> None:
        """Steps until the service has nothing more to do (it would wait for the next refresh)."""
        for _ in range(40):
            if self.stack.service.step() >= 1:
                return
        self.fail("the service kept working")

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

    def test_a_period_not_wholly_processed_carries_no_figures_only_its_envelope(self):
        self.step()  # the last 48 hours only: this week is not wholly processed
        body = self.overview(annotator=str(ALICE[0]))
        self.assertFalse(body["processed"])
        self.assertEqual(body["period"]["first_day"], "2026-11-07")
        self.assertEqual(body["filters"], {"project": None, "annotator": {"user_id": ALICE[0], "user_name": "alice"}})
        for section in ("headline", "sessions", "by_annotator", "by_project", "time_series", "input",
                        "creation_methods", "saved_boxes"):
            self.assertIsNone(body[section], section)
        # the legacy flags stay (no cutover yet: a legacy period); every figure beside them is null
        self.assertEqual(body["operations"], {"legacy": True, "partly_legacy": False, "cutover": None,
                                              "shapes": "all", "working_time_ms": None,
                                              "active_time_ms": None, "rows": None})

        self.step(6)  # processed from 2026-11-06: this week (from the 7th) now is, with its figures
        body = self.overview()
        self.assertTrue(body["processed"])
        self.assertEqual(self.alice_ms(), 30 * MINUTE)  # the 8th, 10th, 11th and 13th


    def test_a_new_day_does_not_take_any_period_away(self):
        self.fill()
        self.settle()
        self.stack.now = NOW + timedelta(hours=25)  # past midnight: the 13th is now an older day
        self.step()
        history = self.history()
        self.assertTrue(history["complete"], history)
        self.assertEqual(history["periods"], {"week": True, "two_weeks": True, "month": True, "year": True})

    def test_with_the_default_window_today_takes_no_step_of_its_own(self):
        worked = 0
        for _ in range(40):
            if self.stack.service.step() >= 1:  # nothing left to do: waiting for the next refresh
                break
            worked += 1
        # the ten-minute refresh, the seven steps of the days before today (see the first test), the daily check
        self.assertEqual(worked, 9)
        self.assertEqual(self.alice_ms(period="two_weeks"), 31 * MINUTE)


class ShortWindowTest(HistoryCase):
    """A refresh window shorter than a day leaves hours of today before it. They are processed once the
    history step has computed them, not before."""

    stack_options = {"refresh_window_hours": 1}  # at 15:20 the ten-minute refresh covers 15:00 onwards

    def week_processed(self, alice_ms: int) -> bool:
        """Whether the week reads as processed. When it does, Alice's working time in it must be `alice_ms`."""
        overview = self.overview()
        if overview["processed"]:
            rows = overview["by_annotator"]["rows"]
            self.assertEqual(sum(row["working_time_ms"] for row in rows if row["user_id"] == ALICE[0]), alice_ms)
        return overview["processed"]

    def test_an_event_from_earlier_today_is_counted_or_its_period_reads_as_not_processed(self):
        self.stack.add_events([working_time(at("2026-11-13 10:00:00"), 16 * MINUTE, user=ALICE, org=ORG)])
        processed = []
        for _ in range(3):
            self.step()
            processed.append(self.week_processed(16 * MINUTE))
        # the ten-minute refresh leaves 10:00 out; the history step computes it; then the daily check
        self.assertEqual(processed, [False, True, True])

    def test_status_offers_no_period_until_todays_earlier_hours_are_computed(self):
        self.stack.add_events([working_time(at("2026-11-13 10:00:00"), 16 * MINUTE, user=ALICE, org=ORG)])
        self.step()  # the ten-minute refresh only
        history = self.history()
        self.assertFalse(history["complete"])
        self.assertEqual(history["ready_from"], "2026-11-13T15:00:00+00:00")
        self.assertEqual(history["periods"], {"week": False, "two_weeks": False, "month": False, "year": False})

        self.step()
        history = self.history()
        self.assertTrue(history["complete"])
        self.assertEqual(history["periods"], {"week": True, "two_weeks": True, "month": True, "year": True})

    def test_todays_earlier_hours_come_first_then_the_days_before_most_recent_first(self):
        self.stack.add_events([
            working_time(at("2026-11-10 10:00:00"), 1 * MINUTE, user=ALICE, org=ORG),
            working_time(at("2026-11-12 10:00:00"), 2 * MINUTE, user=ALICE, org=ORG),
            working_time(at("2026-11-13 10:00:00"), 4 * MINUTE, user=ALICE, org=ORG),
        ])
        ready = []
        for _ in range(5):
            self.step()
            history = self.history()
            ready.append(None if history["complete"] else history["ready_from"])
        self.assertEqual(ready, [
            "2026-11-13T15:00:00+00:00",  # the ten-minute refresh: the current hour
            "2026-11-13T00:00:00+00:00",  # today's hours before it
            "2026-11-12T00:00:00+00:00",
            "2026-11-11T00:00:00+00:00",  # an empty day
            None,  # the 10th, the first day with events: complete
        ])
        self.assertEqual(self.alice_ms(period="two_weeks"), 7 * MINUTE)

    def test_an_hour_that_left_the_window_is_computed_again_before_it_reads_as_processed(self):
        self.stack.add_events([working_time(at("2026-11-13 15:05:00"), 1 * MINUTE, user=ALICE, org=ORG)])
        self.settle()
        self.assertTrue(self.week_processed(1 * MINUTE))

        # in the last minutes of the hour, after its last ten-minute refresh
        self.stack.add_events([working_time(at("2026-11-13 15:55:00"), 2 * MINUTE, user=ALICE, org=ORG)])
        self.stack.now = at("2026-11-13 16:05:00")
        self.step()  # the ten-minute refresh, now from 16:00
        self.assertFalse(self.week_processed(3 * MINUTE))
        self.step()  # the history step: the hour from 15:00
        self.assertTrue(self.week_processed(3 * MINUTE))
        self.settle()
        self.assertTrue(self.week_processed(3 * MINUTE))


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


class LateEventTest(HistoryCase):
    """A day computed earlier is computed again once the daily check finds its raw count changed."""

    def setUp(self) -> None:
        super().setUp()
        self.stack.add_events([
            working_time(at("2026-11-08 10:00:00"), 2 * MINUTE, user=ALICE, org=ORG),
            working_time(at("2026-11-11 10:00:00"), 4 * MINUTE, user=ALICE, org=ORG),
            working_time(at("2026-11-13 10:00:00"), 8 * MINUTE, user=ALICE, org=ORG),
        ])
        self.fill()
        self.settle()  # includes the first daily check

    def test_an_event_that_arrives_two_days_late_is_counted_once_the_next_check_runs(self):
        self.assertEqual(self.alice_ms(period="two_weeks"), 14 * MINUTE)
        # happened two days ago, before the hours the ten-minute refresh recomputes
        self.stack.add_events([working_time(at("2026-11-11 15:20:00"), 16 * MINUTE, user=ALICE, org=ORG)])
        self.stack.now = NOW + timedelta(minutes=10)
        self.settle()  # ten-minute refresh only: the daily check ran less than a day ago
        self.assertEqual(self.alice_ms(period="two_weeks"), 14 * MINUTE)

        self.stack.now = NOW + timedelta(days=1)
        self.settle()  # the next daily check finds the 11th changed and computes it again
        self.assertEqual(self.alice_ms(period="two_weeks"), 30 * MINUTE)

    def test_computing_a_day_again_replaces_its_totals(self):
        self.stack.add_events([working_time(at("2026-11-08 12:00:00"), 16 * MINUTE, user=ALICE, org=ORG)])
        for day in range(1, 4):  # the change is found by the first check; later checks find nothing new
            self.stack.now = NOW + timedelta(days=day)
            self.settle()
            self.assertEqual(self.alice_ms(period="two_weeks"), 30 * MINUTE)
            self.assertEqual(self.alice_ms(period="month", month="2026-11"), 30 * MINUTE)

    def test_an_unchanged_day_is_left_alone_and_history_stays_complete(self):
        self.stack.now = NOW + timedelta(days=1)
        self.settle()
        self.assertTrue(self.history()["complete"])
        self.assertEqual(self.alice_ms(period="two_weeks"), 14 * MINUTE)


class LateEventInASessionTest(HistoryCase):
    def test_a_session_across_midnight_stays_whole_when_history_is_filled_day_by_day(self):
        self.stack.add_events([client(at("2026-11-08 23:58:00")), client(at("2026-11-09 00:02:00"))])
        self.fill()
        self.assertEqual(self.sessions(), (1, 4 * MINUTE))

    def test_a_late_event_that_joins_a_session_across_midnight_keeps_it_one_session(self):
        self.stack.add_events([
            client(at("2026-11-08 23:54:00")),
            client(at("2026-11-08 23:58:00")),
        ])
        self.fill()
        self.settle()
        self.assertEqual(self.sessions(), (1, 4 * MINUTE))

        # arrives late, four minutes after the session's last event, on the next day
        self.stack.add_events([client(at("2026-11-09 00:02:00"))])
        self.stack.now = NOW + timedelta(days=1)
        self.settle()
        self.assertEqual(self.sessions(), (1, 8 * MINUTE))

    def sessions(self) -> tuple[int, int]:
        sessions = self.overview(period="two_weeks")["sessions"]
        return sessions["sessions"], sessions["total_ms"]


class RefreshPriorityTest(HistoryCase):
    """Processing history does not delay the ten-minute refresh of recent hours."""

    def setUp(self) -> None:
        super().setUp()
        start = at("2026-10-01 10:00:00")
        self.stack.add_events([working_time(start + timedelta(days=n), MINUTE, user=ALICE, org=ORG)
                               for n in range(44)])

    def last_refresh_age(self) -> timedelta:
        status, body = self.stack.get("/team-analytics-api/v1/status", "lead", org="org7")
        self.assertEqual(status, 200, body)
        return self.stack.now - datetime.fromisoformat(body["refresh"]["last_success_at"])

    def test_a_due_refresh_comes_before_the_next_day_of_history(self):
        self.step()
        ready = [self.history()["ready_from"]]
        bob = []
        for n in range(1, 13):  # a step every four minutes, from 15:24
            self.stack.now = NOW + timedelta(minutes=4 * n)
            if n == 2:  # recent work, at 15:28
                self.stack.add_events([working_time(self.stack.now, 64 * MINUTE, user=BOB, org=ORG)])
            self.step()
            self.assertLess(self.last_refresh_age(), timedelta(minutes=10))
            ready.append(self.history()["ready_from"])
            rows = self.overview()["by_annotator"]["rows"]
            bob.append(sum(row["working_time_ms"] for row in rows if row["user_id"] == BOB[0]))
        # counted by the refresh at 15:32, while history was still being processed
        self.assertEqual(bob[:3], [0, 0, 64 * MINUTE])
        self.assertFalse(self.history()["complete"])
        self.assertLess(ready[-1], ready[1])  # history kept moving back meanwhile

    def test_a_refresh_due_while_another_replica_processes_a_day_is_retried_soon(self):
        self.step()  # the refresh at 15:20
        inside, release = threading.Event(), threading.Event()

        def clock_holding_a_day_of_history():
            names = {frame.name for frame in traceback.extract_stack()}
            if threading.current_thread().name == "replica-a" and "process_next" in names:
                inside.set()
                release.wait(30)
            return self.stack.now

        replica_a = self.stack.new_service(clock=clock_holding_a_day_of_history)
        replica_b = self.stack.new_service()
        self.stack.now = NOW + timedelta(minutes=9)
        thread = threading.Thread(target=replica_a.step, name="replica-a")
        thread.start()
        try:
            self.assertTrue(inside.wait(30), "replica A did not start a day of history")
            self.stack.now = NOW + timedelta(minutes=11)  # the refresh is now due
            self.assertLessEqual(replica_b.step(), 5)  # the lease is taken: try again in seconds, not minutes
        finally:
            release.set()
            thread.join(30)
        self.assertEqual(replica_b.step(), 0)  # the refresh ran
        self.assertEqual(self.last_refresh_age(), timedelta(0))


class RunningServiceTest(HistoryCase):
    """The service as deployed (`python -m team_analytics`) processes history on its own."""

    def test_the_running_service_processes_older_days_without_being_asked(self):
        now = datetime.now(UTC)
        self.stack.add_events([
            working_time(now - timedelta(days=5), 100_000, user=ALICE, org=ORG),
            working_time(now, 1_000, user=ALICE, org=ORG),
        ])
        port = free_port()
        env = {
            **os.environ,
            "CLICKHOUSE_DB": self.stack.events_db,
            "TEAM_ANALYTICS_DB": self.stack.totals_db,
            "TEAM_ANALYTICS_CVAT_URL": self.stack.cvat.url,
            "TEAM_ANALYTICS_LISTEN_HOST": "127.0.0.1",
            "TEAM_ANALYTICS_LISTEN_PORT": str(port),
        }
        process = subprocess.Popen(  # noqa: S603 - our own module
            [sys.executable, "-B", "-m", "team_analytics"], cwd=SERVICE_DIR, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            history = None
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                history = self.read(port, "status").get("history")
                if history and history["complete"]:
                    break
                time.sleep(0.5)
            self.assertTrue(history and history["complete"], history)
            rows = self.read(port, "overview", "&period=two_weeks")["by_annotator"]["rows"]
            self.assertEqual(rows, [{"user_id": ALICE[0], "user_name": "alice", "working_time_ms": 101_000}])
        finally:
            process.terminate()
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    @staticmethod
    def read(port: int, path: str, query: str = "") -> dict:
        request = Request(f"http://127.0.0.1:{port}/team-analytics-api/v1/{path}?org=org7{query}",
                          headers={"Cookie": "sessionid=lead"})
        try:
            with urlopen(request, timeout=5) as response:
                return json.loads(response.read())
        except (URLError, ConnectionError):
            return {}
