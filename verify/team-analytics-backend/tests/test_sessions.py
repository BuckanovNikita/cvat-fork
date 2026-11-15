"""Sessions: uninterrupted intervals of one person's job work, split by pauses over five minutes."""

import json
from datetime import timedelta

from tests.support import FakeUser, StackTestCase, at, clickhouse_client, working_time

ORG = 7
ALICE = (11, "alice")
BOB = (12, "bob")
MINUTE = 60_000


def client(when, scope: str = "change:frame", *, user: tuple[int, str] = ALICE, org: int | None = ORG,
           project: int | None = 1, task: int | None = 1, job: int | None = 1) -> dict:
    """A client event as the UI's job logger writes it."""
    return {
        "scope": scope, "source": "client", "timestamp": when, "count": 1, "duration": 0,
        "project_id": project, "task_id": task, "job_id": job,
        "user_id": user[0], "user_name": user[1], "user_email": f"{user[1]}@example.com",
        "org_id": org, "org_slug": None if org is None else f"org{org}",
        "payload": json.dumps({"client_id": 5}),
    }


class SessionsCase(StackTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.callers.add_user("lead", FakeUser(2, "lead", memberships={"org7": (ORG, "maintainer", True),
                                                                          "org8": (8, "maintainer", True)}))
        self.stack.callers.add_user("admin", FakeUser(1, "admin", groups=["admin"]))

    def sessions(self, session: str = "lead", **query) -> dict:
        query.setdefault("org", "org7")
        status, body = self.stack.overview(session, **query)
        self.assertEqual(status, 200, body)
        return body["sessions"]

    def headline(self, **query) -> tuple[int, int, int]:
        sessions = self.sessions(**query)
        return sessions["sessions"], sessions["average_ms"], sessions["total_ms"]


class PauseRuleTest(SessionsCase):
    def test_a_pause_longer_than_five_minutes_starts_a_new_session(self):
        self.stack.add_events([
            client(at("2026-11-13 10:00:00")),
            client(at("2026-11-13 10:03:00")),
            client(at("2026-11-13 10:08:00")),  # exactly five minutes: the same session
            client(at("2026-11-13 10:13:00.001")),  # five minutes and a millisecond: a new one
            client(at("2026-11-13 10:15:00.001")),
        ])
        self.stack.refresh()

        self.assertEqual(self.headline(), (2, 5 * MINUTE, 10 * MINUTE))

    def test_sessions_are_formed_from_job_bound_client_events_and_working_time_rows(self):
        self.stack.add_events([
            # a working-time row bridges two client events eight minutes apart
            client(at("2026-11-13 10:00:00")),
            working_time(at("2026-11-13 10:04:00"), 30_000, user=ALICE, org=ORG),
            client(at("2026-11-13 10:08:00")),
            # rows without a job, and server rows other than working time, do not bridge
            client(at("2026-11-13 11:00:00")),
            client(at("2026-11-13 11:04:00"), "load:workspace", project=None, task=None, job=None),
            dict(working_time(at("2026-11-13 11:04:30"), 30_000, user=ALICE, org=ORG), scope="create:shapes",
                 payload="{}"),
            working_time(at("2026-11-13 11:05:00"), 30_000, user=ALICE, org=ORG, project=None, task=None, job=None),
            client(at("2026-11-13 11:08:00")),
        ])
        self.stack.refresh()

        self.assertEqual(self.headline(), (3, 160_000, 8 * MINUTE))

    def test_work_across_midnight_is_one_session(self):
        self.stack.add_events([
            client(at("2026-11-12 23:58:00")),
            client(at("2026-11-12 23:59:30")),
            client(at("2026-11-13 00:02:00")),
        ])
        self.stack.refresh()

        self.assertEqual(self.headline(), (1, 4 * MINUTE, 4 * MINUTE))
        self.assertEqual(self.headline(tz="America/New_York"), (1, 4 * MINUTE, 4 * MINUTE))


class PerAnnotatorTest(SessionsCase):
    stack_options = {"technical_accounts": ("importer",)}

    def test_each_annotator_has_a_session_count_and_average_whatever_the_job_stage(self):
        self.stack.add_events([
            client(at("2026-11-12 09:00:00"), "draw:object"),
            client(at("2026-11-12 09:04:00"), "draw:object"),
            client(at("2026-11-12 09:30:00"), "drag:object"),
            client(at("2026-11-12 09:32:00"), "resize:object"),
            client(at("2026-11-12 09:50:00"), "delete:object"),
            # a reviewer in a validation job only looks around and clicks
            client(at("2026-11-12 14:00:00"), "zoom:image", user=BOB, job=2),
            client(at("2026-11-12 14:03:00"), "click:element", user=BOB, job=2),
            # someone with only working-time rows in a job
            working_time(at("2026-11-12 08:00:00"), 60_000, user=(13, "carol"), org=ORG, job=3),
            # a technical account is not an annotator, and not part of the team's figures
            client(at("2026-11-12 09:00:00"), user=(99, "importer")),
            client(at("2026-11-12 09:04:00"), user=(99, "importer")),
        ])
        self.stack.refresh()

        sessions = self.sessions()
        self.assertEqual(sessions["by_annotator"], [
            {"user_id": 11, "user_name": "alice", "sessions": 3, "average_ms": 2 * MINUTE, "total_ms": 6 * MINUTE},
            {"user_id": 12, "user_name": "bob", "sessions": 1, "average_ms": 3 * MINUTE, "total_ms": 3 * MINUTE},
            {"user_id": 13, "user_name": "carol", "sessions": 1, "average_ms": 0, "total_ms": 0},
        ])
        self.assertEqual((sessions["sessions"], sessions["average_ms"], sessions["total_ms"]),
                         (5, 108_000, 9 * MINUTE))

    def test_no_job_work_gives_zero_sessions(self):
        self.stack.refresh()
        self.assertEqual(self.sessions(), {"sessions": 0, "average_ms": 0, "total_ms": 0, "by_annotator": []})


class OrganizationIsolationTest(SessionsCase):
    def test_an_organization_sees_sessions_of_its_own_events_and_instance_scope_sees_all_work_as_one(self):
        self.stack.add_events([
            client(at("2026-11-13 10:00:00")),
            client(at("2026-11-13 10:04:00")),
            client(at("2026-11-13 10:06:00"), org=8, project=5),
            client(at("2026-11-13 10:08:00"), org=8, project=5),
            client(at("2026-11-13 10:10:00")),
            client(at("2026-11-13 10:12:00")),
            client(at("2026-11-13 10:14:00"), org=None, project=6),  # personal workspace
        ])
        self.stack.refresh()

        self.assertEqual(self.headline(org="org7"), (2, 3 * MINUTE, 6 * MINUTE))
        self.assertEqual(self.headline(org="org8"), (1, 2 * MINUTE, 2 * MINUTE))
        self.assertEqual(self.headline(session="admin", org="org7"), (2, 3 * MINUTE, 6 * MINUTE))
        self.assertEqual(self.headline(session="admin", org=""), (1, 14 * MINUTE, 14 * MINUTE))


class RefreshEdgeTest(SessionsCase):
    """The 48-hour window of a refresh at NOW (2026-11-13 15:20) starts at 2026-11-11 16:00."""

    @staticmethod
    def session_from_15_50(minutes: range) -> list[dict]:
        return [client(at("2026-11-11 15:50:00") + timedelta(minutes=m)) for m in minutes]

    def test_a_session_crossing_the_window_start_is_counted_once_with_its_full_length(self):
        self.stack.add_events(self.session_from_15_50(range(0, 31, 2)))
        # history up to the 12th first, so the week is processed; the refreshes below then write the hours read
        self.stack.now = at("2026-11-13 15:20:00")
        self.stack.settle()
        self.stack.refresh(at("2026-11-11 16:30:00"))
        self.stack.refresh(at("2026-11-13 15:20:00"))

        self.assertEqual(self.headline(), (1, 30 * MINUTE, 30 * MINUTE))

    def test_a_session_still_going_on_at_one_refresh_is_stored_once_by_the_next(self):
        self.stack.add_events(self.session_from_15_50(range(0, 15, 2)))
        # history up to the 12th first, so the week is processed; the refreshes below then write the hours read
        self.stack.now = at("2026-11-13 15:20:00")
        self.stack.settle()
        self.stack.refresh(at("2026-11-11 16:05:00"))
        self.stack.add_events(self.session_from_15_50(range(16, 31, 2)))
        self.stack.refresh(at("2026-11-13 15:20:00"))

        self.assertEqual(self.headline(), (1, 30 * MINUTE, 30 * MINUTE))

    def test_a_window_that_ends_inside_a_session_leaves_it_to_the_window_holding_its_end(self):
        # A window can end before the latest events (a refresh whose clock is behind, a history fill).
        self.stack.add_events(self.session_from_15_50(range(0, 31, 2)))
        # history up to the 12th first, so the week is processed; the refreshes below then write the hours read
        self.stack.now = at("2026-11-13 15:20:00")
        self.stack.settle()
        self.stack.refresh(at("2026-11-11 15:58:00"))  # window ends at 16:00, the session goes on
        self.stack.refresh(at("2026-11-13 15:20:00"))  # window starts at 16:00

        self.assertEqual(self.headline(), (1, 30 * MINUTE, 30 * MINUTE))


class StoredIntervalsTest(SessionsCase):
    """Ticket 07 filters sessions by project from the stored intervals: each session with its time per project."""

    def stored(self) -> list[tuple]:
        totals = clickhouse_client(self.stack.totals_db)
        return totals.query(
            "SELECT user_id, toString(start_at), toString(end_at), length_ms, project_ids, project_ms FROM session_intervals "
            "WHERE instance_wide = 0 ORDER BY start_at").result_rows

    def test_each_session_is_stored_as_an_interval_with_the_time_spent_in_each_project(self):
        self.stack.add_events([
            client(at("2026-11-13 10:00:00"), project=1),
            client(at("2026-11-13 10:02:00"), project=1),
            client(at("2026-11-13 10:03:00"), project=2),  # the pause before a switch goes to the next project
            client(at("2026-11-13 10:06:00"), project=2),
            client(at("2026-11-13 10:07:00"), project=None),  # No project
            # a project touched only by the session's first event has no time in it
            client(at("2026-11-13 12:00:00"), project=3),
            client(at("2026-11-13 12:01:00"), project=1),
        ])
        self.stack.refresh()

        self.assertEqual(self.stored(), [
            (11, "2026-11-13 10:00:00.000", "2026-11-13 10:07:00.000", 7 * MINUTE,
             [0, 1, 2], [MINUTE, 2 * MINUTE, 4 * MINUTE]),
            (11, "2026-11-13 12:00:00.000", "2026-11-13 12:01:00.000", MINUTE, [1, 3], [MINUTE, 0]),
        ])
