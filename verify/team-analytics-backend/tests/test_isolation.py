"""Organization isolation on the details table, the full view lists and the trends: an administrator who selected
one organization gets nothing of another organization or of personal workspaces, whatever identifiers the page
sends; instance scope (an administrator without an organization) holds every organization and personal workspaces.
Who may ask is CVAT's permission check (administrators only), not tested here."""

from tests.support import FakeUser, StackTestCase, at, working_time
from tests.test_bounding_boxes import BOX
from tests.test_keyboard_mouse import summary
from tests.test_operations import client, draw

ORG_A, ORG_B = 7, 8
ALICE = (11, "alice")  # organization A, project 1
BRUNO = (21, "bruno")  # organization B, project 9
PAUL = (31, "paul")  # personal workspace, project 5
API = "/api/team-analytics/"
FOREIGN_NAMES = ("bruno", "paul")


def work(user: tuple[int, str], org: int | None, project: int, hotkey: str) -> list[dict]:
    """An hour of job work: working time, a bounding box drawn and an input summary with `hotkey`."""
    where = {"user": user, "org": org, "project": project}
    return [
        working_time(at("2026-11-12 10:00:00"), 3_600_000, user=user, org=org, project=project),
        client("load:job", at("2026-11-12 10:00:00"), **where),
        draw(at("2026-11-12 10:00:10"), input_method="mouse", **BOX, **where),
        summary(at("2026-11-12 10:01:00"), hotkeys={hotkey: 3}, mouse={"header": 1}, **where),
    ]


class IsolationTest(StackTestCase):
    def setUp(self) -> None:
        super().setUp()
        callers = self.stack.callers
        # "lead": an administrator who selected organization A (get() names it); "admin": an administrator who
        # names an organization or none
        callers.add_user("lead", FakeUser(2, "lead", groups=["admin"], memberships={"org-a": (ORG_A, "maintainer", True)}))
        callers.add_user("admin", FakeUser(1, "admin", groups=["admin"],
                                           memberships={"org-b": (ORG_B, "maintainer", True)}))
        self.stack.add_events([
            *work(ALICE, ORG_A, 1, "NEXT_FRAME"),
            *work(BRUNO, ORG_B, 9, "ORG_B_ONLY"),
            *work(PAUL, None, 5, "PERSONAL_ONLY"),
        ])
        self.stack.refresh()

    def get(self, endpoint: str, session: str = "lead", **query) -> dict:
        if session == "lead":
            query.setdefault("org", "org-a")
        status, body = self.stack.get(API + endpoint, session, **query)
        self.assertEqual(status, 200, (endpoint, query, body))
        return body

    def assertNothingForeign(self, body: dict) -> None:
        text = repr(body)
        for name in FOREIGN_NAMES:
            self.assertNotIn(name, text)
        self.assertNotIn("ORG_B_ONLY", text)
        self.assertNotIn("PERSONAL_ONLY", text)

    def test_details_show_only_the_callers_organization(self):
        annotators = self.get("details")
        self.assertEqual([row["user_name"] for row in annotators["rows"]], ["alice"])
        self.assertNothingForeign(annotators)
        projects = self.get("details", by="projects")
        self.assertEqual(([row["id"] for row in projects["rows"]], projects["project_ids"]), ([1], [1]))
        # identifiers and names of another organization or a personal workspace find nothing
        self.assertEqual(self.get("details", search="bru")["total"], 0)
        self.assertEqual(self.get("details", by="projects", ids="9,5")["rows"], [])
        self.assertEqual(self.get("details", project="9")["rows"], [])
        self.assertEqual(self.get("details", by="projects", annotator="21")["rows"], [])

    def test_full_view_lists_show_only_the_callers_organization(self):
        for by in ("annotators", "projects", "hotkeys"):
            with self.subTest(by=by):
                listed = self.get("list", by=by)
                self.assertNothingForeign(listed)
                if by == "projects":
                    self.assertEqual([row["id"] for row in listed["rows"]], [1])
                if by == "hotkeys":
                    self.assertEqual([row["action"] for row in listed["rows"]], ["NEXT_FRAME"])
                # the other organization's project or annotator as the filter (a list ignores its own dimension)
                foreign = {"annotator": "21"} if by == "projects" else {"project": "9"}
                self.assertEqual(self.get("list", by=by, **foreign)["rows"], [])

    def test_trends_compare_nobody_and_nothing_of_another_organization(self):
        scope = self.get("trends")
        self.assertEqual([row["user_name"] for row in scope["candidates"]], ["alice"])
        compared = self.get("trends", compare="annotators", ids="21,31")
        self.assertNothingForeign(compared)
        for line in compared["lines"]:
            self.assertEqual({point["working_time_ms"] for point in line["points"]}, {0})
            self.assertEqual({point["boxes"] for point in line["points"]} - {None}, {0})
        projects = self.get("trends", compare="projects", ids="9,5")
        self.assertEqual({point["working_time_ms"] for line in projects["lines"] for point in line["points"]}, {0})
        self.assertEqual([row["id"] for row in projects["candidates"]], [1])

    def test_the_filter_echo_never_names_someone_of_another_organization(self):
        self.assertEqual(self.get("overview", annotator="21")["filters"]["annotator"], {"user_id": 21, "user_name": None})
        self.assertEqual(self.get("overview", annotator="31")["filters"]["annotator"], {"user_id": 31, "user_name": None})

    def test_an_administrator_reads_instance_scope_and_a_named_organization(self):
        names = {row["user_name"] for row in self.get("details", "admin")["rows"]}
        self.assertEqual(names, {"alice", "bruno", "paul"})
        self.assertEqual({row["id"] for row in self.get("list", "admin", by="projects")["rows"]}, {1, 5, 9})
        self.assertEqual({row["user_name"] for row in self.get("trends", "admin")["candidates"]},
                         {"alice", "bruno", "paul"})
        self.assertEqual([row["user_name"] for row in self.get("details", "admin", org="org-b")["rows"]], ["bruno"])


# The history block every caller gets (only administrators read): it dates the instance, whatever the scope.
HISTORY = {"complete", "percent", "periods", "earliest_month", "complete_weeks", "trends_ready",
           "first_day", "days_ready", "days_total", "ready_from", "ready_from_day"}


class HistoryStatusTest(StackTestCase):
    """Status while history is processed. Organization B's events begin on 2026-10-01, the instance's first
    day with events; organization A's on 2026-11-10."""

    def setUp(self) -> None:
        super().setUp()
        callers = self.stack.callers
        callers.add_user("admin", FakeUser(1, "admin", groups=["admin"],
                                           memberships={"org-a": (ORG_A, "maintainer", True)}))
        self.stack.add_events([
            working_time(at("2026-10-01 10:00:00"), 60_000, user=BRUNO, org=ORG_B, project=9),
            working_time(at("2026-11-10 10:00:00"), 60_000, user=ALICE, org=ORG_A, project=1),
        ])
        # processed from 2026-11-10 (UTC), the older days still to do
        for _ in range(10):
            if self.status()["history"]["ready_from_day"] == "2026-11-10":
                break
            self.stack.engine.step()
        self.assertEqual(self.status()["history"]["ready_from_day"], "2026-11-10")

    def status(self, **query) -> dict:
        status, body = self.stack.get(API + "status", "admin", **query)
        self.assertEqual(status, 200, body)
        return body

    def test_an_administrator_gets_the_full_block_with_or_without_an_organization(self):
        for query in ({}, {"org": "org-a"}, {"org": "org-a", "tz": "Asia/Tokyo"}):
            with self.subTest(**query):
                body = self.status(**query)
                self.assertEqual(set(body), {"history", "refresh", "cutover"})
                history = body["history"]
                self.assertEqual(set(history), HISTORY)
                self.assertFalse(history["complete"])
                self.assertEqual(history["first_day"], "2026-10-01")
                self.assertEqual((history["days_ready"], history["days_total"]), (4, 44))
                # 4 of the 44 days from 2026-10-01 to 2026-11-13 are processed, rounded down
                self.assertEqual(history["percent"], 9)
                self.assertEqual(history["periods"],
                                 {"week": False, "two_weeks": False, "month": False, "year": False})
                self.assertIsNone(history["earliest_month"])
                self.assertFalse(history["trends_ready"])
                self.assertIn("last_success_at", body["refresh"])
                self.assertIn("at", body["cutover"])

    def test_an_organization_and_instance_scope_get_the_same_block(self):
        self.assertEqual(self.status(org="org-a")["history"], self.status()["history"])

    def test_complete_history_reads_as_all_of_it(self):
        for _ in range(10):
            if self.status()["history"]["complete"]:
                break
            self.stack.engine.step()
        for query in ({}, {"org": "org-a"}):
            with self.subTest(**query):
                history = self.status(**query)["history"]
                self.assertTrue(history["complete"])
                self.assertEqual(history["percent"], 100)
                self.assertEqual((history["days_ready"], history["days_total"]), (44, 44))
                self.assertEqual((history["complete_weeks"], history["trends_ready"]), (12, True))


class OverviewScopeTest(StackTestCase):
    """The overview's annotators by scope (converted from the service's access tests, whose subject was who may
    read: what remains is what each scope reads)."""

    def setUp(self) -> None:
        super().setUp()
        self.stack.callers.add_user("admin", FakeUser(1, "admin", groups=["admin"], memberships={
            "org-a": (ORG_A, "maintainer", True), "org-b": (ORG_B, "maintainer", True)}))
        self.stack.add_events([
            working_time(at("2026-11-13 10:00:00"), 100_000, user=ALICE, org=ORG_A),
            working_time(at("2026-11-13 10:00:00"), 200_000, user=BRUNO, org=ORG_B),
            working_time(at("2026-11-13 10:00:00"), 300_000, user=PAUL, org=None),
        ])
        self.stack.refresh()

    def names(self, session, **query) -> list[str]:
        status, body = self.stack.overview(session, **query)
        self.assertEqual(status, 200, body)
        return [row["user_name"] for row in body["by_annotator"]["rows"]]

    def test_an_administrator_reads_a_named_organization(self):
        self.assertEqual(self.names("admin", org="org-a"), ["alice"])
        self.assertEqual(self.names("admin", org="org-b"), ["bruno"])

    def test_an_administrator_without_an_organization_reads_instance_scope_with_personal_workspaces(self):
        self.assertEqual(self.names("admin"), ["paul", "bruno", "alice"])

    def test_identifiers_sent_by_the_browser_cannot_widen_the_scope(self):
        self.assertEqual(self.names("admin", org="org-a", org_id=str(ORG_B)), ["alice"])
        self.assertEqual(self.names("admin", org="org-a", instance="1"), ["alice"])
