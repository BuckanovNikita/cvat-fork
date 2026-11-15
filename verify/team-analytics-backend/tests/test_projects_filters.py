"""Projects and filters: every figure per project and per annotator, narrowed by a project, an annotator or both."""

import json

from tests.support import FakeUser, StackTestCase, at, working_time

ORG = 7
ALICE = (11, "alice")
BOB = (12, "bob")
CAROL = (13, "carol")
MINUTE = 60_000
HOUR = 60 * MINUTE


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


class FiltersCase(StackTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.callers.add_user("lead", FakeUser(2, "lead", groups=["admin"], memberships={"org7": (ORG, "maintainer", True),
                                                                          "org8": (8, "maintainer", True)}))
        self.stack.callers.add_user("admin", FakeUser(1, "admin", groups=["admin"]))

    def overview(self, session: str = "lead", **query) -> dict:
        query.setdefault("org", "org7")
        status, body = self.stack.overview(session, **query)
        self.assertEqual(status, 200, body)
        return body

    @staticmethod
    def projects(body: dict) -> list[tuple[int, int]]:
        return [(row["project_id"], row["working_time_ms"]) for row in body["by_project"]["rows"]]

    @staticmethod
    def annotators(body: dict) -> list[tuple[str, int]]:
        return [(row["user_name"], row["working_time_ms"]) for row in body["by_annotator"]["rows"]]

    @staticmethod
    def rest(body: dict, section: str) -> tuple[int, int]:
        # how many rows a chart does not show and their working time (their parts: test_full_view.py)
        rest = body[section]["rest"]
        return rest["count"], rest["working_time_ms"]

    def add_two_project_team(self) -> None:
        """alice: 3 h in project 1, 1 h without a project; bob: 2 h in project 2, 30 min in project 1."""
        self.stack.add_events([
            working_time(at("2026-11-12 09:00:00"), 3 * HOUR, user=ALICE, org=ORG, project=1, task=1),
            working_time(at("2026-11-12 13:00:00"), HOUR, user=ALICE, org=ORG, project=None, task=4, job=4),
            working_time(at("2026-11-12 10:00:00"), 2 * HOUR, user=BOB, org=ORG, project=2, task=2, job=2),
            working_time(at("2026-11-13 10:00:00"), 30 * MINUTE, user=BOB, org=ORG, project=1, task=1, job=3),
        ])
        self.stack.refresh()


class WorkingTimePerProjectTest(FiltersCase):
    def test_working_time_per_project_largest_first_with_no_project_as_project_0(self):
        self.add_two_project_team()

        body = self.overview()
        self.assertEqual(self.projects(body), [(1, 3 * HOUR + 30 * MINUTE), (2, 2 * HOUR), (0, HOUR)])
        self.assertEqual(self.rest(body, "by_project"), (0, 0))


class FilterTest(FiltersCase):
    def test_a_project_filter_narrows_the_annotators_and_keeps_every_project_listed(self):
        self.add_two_project_team()

        body = self.overview(project="1")
        self.assertEqual(self.annotators(body), [("alice", 3 * HOUR), ("bob", 30 * MINUTE)])
        self.assertEqual(self.projects(body), [(1, 3 * HOUR + 30 * MINUTE), (2, 2 * HOUR), (0, HOUR)])

    def test_an_annotator_filter_narrows_the_projects_and_keeps_every_annotator_listed(self):
        self.add_two_project_team()

        body = self.overview(annotator="12")
        self.assertEqual(self.projects(body), [(2, 2 * HOUR), (1, 30 * MINUTE)])
        self.assertEqual(self.annotators(body), [("alice", 4 * HOUR), ("bob", 2 * HOUR + 30 * MINUTE)])

    def test_both_filters_combine(self):
        self.add_two_project_team()

        body = self.overview(project="2", annotator="11")
        self.assertEqual(self.annotators(body), [("bob", 2 * HOUR)])  # within project 2
        self.assertEqual(self.projects(body), [(1, 3 * HOUR), (0, HOUR)])  # within alice
        self.assertEqual(body["headline"], {"annotators": 0, "projects": 0})

    def test_no_project_is_a_filter_of_its_own(self):
        self.add_two_project_team()

        self.assertEqual(self.annotators(self.overview(project="0")), [("alice", HOUR)])

    def test_a_filter_never_widens_the_organization(self):
        self.add_two_project_team()
        self.stack.add_events([working_time(at("2026-11-12 09:00:00"), HOUR, user=CAROL, org=8, project=9)])
        self.stack.refresh()

        body = self.overview(project="9", annotator="13")
        self.assertEqual((self.annotators(body), self.projects(body)), ([], []))
        # nor names someone from another organization
        self.assertEqual(body["filters"]["annotator"], {"user_id": 13, "user_name": None})
        self.assertEqual(self.annotators(self.overview(org="org8", project="9")), [("carol", HOUR)])

    def test_a_filter_that_is_not_an_identifier_is_refused(self):
        for query in ({"project": "abc"}, {"annotator": "-1"}, {"project": "1.5"}, {"annotator": "1" * 20}):
            with self.subTest(query):
                status, body = self.stack.overview("lead", org="org7", **query)
                self.assertEqual((status, body["error"]), (400, "bad_request"))


class SessionsUnderFiltersTest(FiltersCase):
    def sessions(self, **query) -> tuple[int, int, list]:
        sessions = self.overview(**query)["sessions"]
        return sessions["sessions"], sessions["total_ms"], [
            (row["user_name"], row["sessions"], row["total_ms"]) for row in sessions["by_annotator"]]

    def test_a_session_spanning_two_projects_counts_under_each_with_only_the_time_inside_it(self):
        self.stack.add_events([
            client(at("2026-11-13 10:00:00"), project=1),
            client(at("2026-11-13 10:04:00"), project=1),
            client(at("2026-11-13 10:05:00"), project=2),  # the pause before a switch goes to the next project
            client(at("2026-11-13 10:10:00"), project=2),
            client(at("2026-11-13 10:12:00"), project=None),
            # bob's single session in project 2
            client(at("2026-11-13 11:00:00"), user=BOB, project=2),
            client(at("2026-11-13 11:03:00"), user=BOB, project=2),
        ])
        self.stack.refresh()

        self.assertEqual(self.sessions(), (2, 15 * MINUTE, [("alice", 1, 12 * MINUTE), ("bob", 1, 3 * MINUTE)]))
        self.assertEqual(self.sessions(project="1"), (1, 4 * MINUTE, [("alice", 1, 4 * MINUTE)]))
        self.assertEqual(self.sessions(project="2"),
                         (2, 9 * MINUTE, [("alice", 1, 6 * MINUTE), ("bob", 1, 3 * MINUTE)]))
        self.assertEqual(self.sessions(project="0"), (1, 2 * MINUTE, [("alice", 1, 2 * MINUTE)]))
        self.assertEqual(self.sessions(project="3"), (0, 0, []))

    def test_an_annotator_filter_keeps_that_annotators_sessions_and_combines_with_a_project(self):
        self.stack.add_events([
            client(at("2026-11-13 10:00:00"), project=1),
            client(at("2026-11-13 10:04:00"), project=2),
            client(at("2026-11-13 11:00:00"), user=BOB, project=2),
            client(at("2026-11-13 11:03:00"), user=BOB, project=2),
        ])
        self.stack.refresh()

        self.assertEqual(self.sessions(annotator="12"), (1, 3 * MINUTE, [("bob", 1, 3 * MINUTE)]))
        self.assertEqual(self.sessions(annotator="11", project="2"), (1, 4 * MINUTE, [("alice", 1, 4 * MINUTE)]))
        self.assertEqual(self.sessions(annotator="12", project="1"), (0, 0, []))


class WorkingTimeOverThePeriodUnderFiltersTest(FiltersCase):
    def day(self, day: str, **query) -> int:
        buckets = self.overview(**query)["time_series"]["buckets"]
        return next(bucket["working_time_ms"] for bucket in buckets if bucket["start"] == day)

    def test_working_time_by_day_follows_both_filters(self):
        self.add_two_project_team()

        self.assertEqual(self.day("2026-11-12"), 6 * HOUR)
        self.assertEqual(self.day("2026-11-12", project="1"), 3 * HOUR)
        self.assertEqual(self.day("2026-11-12", annotator="12"), 2 * HOUR)
        self.assertEqual(self.day("2026-11-12", project="0", annotator="11"), HOUR)
        self.assertEqual(self.day("2026-11-13", project="1", annotator="11"), 0)


class HeadlineTest(FiltersCase):
    def test_active_annotators_and_the_projects_they_worked_in(self):
        self.add_two_project_team()

        self.assertEqual(self.overview()["headline"], {"annotators": 2, "projects": 3})
        self.assertEqual(self.overview(project="1")["headline"], {"annotators": 2, "projects": 1})
        self.assertEqual(self.overview(annotator="11")["headline"], {"annotators": 1, "projects": 2})


class SelectedAnnotatorTest(FiltersCase):
    def test_the_selected_annotator_is_named_even_outside_the_top_rows(self):
        self.add_two_project_team()

        self.assertEqual(self.overview(annotator="12")["filters"],
                         {"project": None, "annotator": {"user_id": 12, "user_name": "bob"}})
        self.assertEqual(self.overview(project="0")["filters"], {"project": 0, "annotator": None})
        # an annotator without work in the scope keeps the identifier only
        self.assertEqual(self.overview(annotator="99")["filters"]["annotator"], {"user_id": 99, "user_name": None})


class TopRowsTest(FiltersCase):
    def test_each_chart_shows_the_eight_largest_rows_and_the_count_and_total_of_the_rest(self):
        # ten annotators, annotator n working n minutes in project n
        self.stack.add_events([
            working_time(at("2026-11-12 09:00:00"), n * MINUTE, user=(100 + n, f"user{n:02}"), org=ORG,
                         project=n, task=n, job=n)
            for n in range(1, 11)
        ])
        self.stack.refresh()

        body = self.overview()
        self.assertEqual(self.annotators(body), [(f"user{n:02}", n * MINUTE) for n in range(10, 2, -1)])
        self.assertEqual(self.rest(body, "by_annotator"), (2, 3 * MINUTE))
        self.assertEqual(self.projects(body), [(n, n * MINUTE) for n in range(10, 2, -1)])
        self.assertEqual(self.rest(body, "by_project"), (2, 3 * MINUTE))

    def test_nothing_in_the_period_gives_no_rows_and_an_empty_rest(self):
        self.stack.refresh()
        body = self.overview()
        for section in ("by_project", "by_annotator"):
            self.assertEqual((body[section]["rows"], self.rest(body, section)), ([], (0, 0)))
