"""Access rules: CVAT is asked with the caller's credentials; the scope comes from CVAT's answers."""

from datetime import timedelta

from tests.support import NOW, FakeUser, Stack, StackTestCase, at, wait_for_clickhouse, working_time

ORG_A, ORG_B = 7, 8
ALICE = (11, "alice")  # works in organization A
BRUNO = (21, "bruno")  # works in organization B
PAUL = (31, "paul")  # works in a personal workspace


class AccessTest(StackTestCase):
    def setUp(self) -> None:
        super().setUp()
        cvat = self.stack.cvat
        cvat.add_user("admin", FakeUser(1, "admin", groups=["admin"]))
        cvat.add_user("owner", FakeUser(2, "owner", memberships={"org-a": (ORG_A, "owner", True)}))
        cvat.add_user("maintainer", FakeUser(3, "maintainer", memberships={"org-a": (ORG_A, "maintainer", True)}))
        cvat.add_user("supervisor", FakeUser(4, "supervisor", memberships={"org-a": (ORG_A, "supervisor", True)}))
        cvat.add_user("worker", FakeUser(5, "worker", memberships={"org-a": (ORG_A, "worker", True)}))
        cvat.add_user("removed", FakeUser(6, "removed", memberships={"org-a": (ORG_A, "maintainer", False)}))
        cvat.add_user("outsider", FakeUser(7, "outsider"))
        cvat.add_user("maintainer-b", FakeUser(8, "maintainer-b", memberships={"org-b": (ORG_B, "maintainer", True)}))
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

    def assertRefused(self, session, status=403, **query):  # noqa: N802 - unittest style
        code, body = self.stack.overview(session, **query)
        self.assertEqual(code, status, body)
        self.assertNotIn("by_annotator", body)
        return body

    def test_owner_and_maintainer_read_their_organization_only(self):
        self.assertEqual(self.names("owner", org="org-a"), ["alice"])
        self.assertEqual(self.names("maintainer", org="org-a"), ["alice"])
        self.assertEqual(self.names("maintainer-b", org="org-b"), ["bruno"])

    def test_admin_group_reads_a_named_organization(self):
        self.assertEqual(self.names("admin", org="org-a"), ["alice"])
        self.assertEqual(self.names("admin", org="org-b"), ["bruno"])

    def test_admin_group_without_an_organization_reads_instance_scope_with_personal_workspaces(self):
        self.assertEqual(self.names("admin"), ["paul", "bruno", "alice"])

    def test_admin_is_decided_by_the_admin_group_not_by_the_superuser_flag(self):
        self.stack.cvat.add_user("group-admin", FakeUser(41, "group-admin", groups=["admin"], superuser=False))
        self.stack.cvat.add_user("flag-only", FakeUser(42, "flag-only", groups=["user"], superuser=True))
        self.assertEqual(self.names("group-admin"), ["paul", "bruno", "alice"])
        self.assertEqual(self.names("group-admin", org="org-b"), ["bruno"])
        self.assertEqual(self.assertRefused("flag-only")["error"], "forbidden")

    def test_supervisor_worker_and_non_member_are_refused(self):
        for session in ("supervisor", "worker", "outsider"):
            with self.subTest(session=session):
                self.assertRefused(session, org="org-a")

    def test_removed_member_is_refused(self):
        self.assertRefused("removed", org="org-a")

    def test_maintainer_of_another_organization_is_refused(self):
        self.assertRefused("maintainer-b", org="org-a")

    def test_owner_or_maintainer_without_an_organization_is_asked_to_select_one(self):
        for session in ("owner", "maintainer"):
            with self.subTest(session=session):
                self.assertEqual(self.assertRefused(session)["error"], "organization_required")

    def test_ordinary_member_without_an_organization_is_refused_not_asked_to_select_one(self):
        for session in ("worker", "supervisor", "outsider", "removed"):
            with self.subTest(session=session):
                self.assertEqual(self.assertRefused(session)["error"], "forbidden")

    def test_owner_or_maintainer_of_any_organization_is_asked_to_select_one(self):
        self.stack.cvat.add_user("both", FakeUser(9, "both", memberships={
            "org-a": (ORG_A, "worker", True), "org-b": (ORG_B, "maintainer", True)}))
        self.assertEqual(self.assertRefused("both")["error"], "organization_required")

    def test_unknown_organization_is_refused(self):
        self.assertRefused("maintainer", org="no-such-org")

    def test_a_request_without_credentials_is_refused(self):
        self.assertRefused(None, status=401, org="org-a")
        self.assertRefused("unknown-session", status=401, org="org-a")

    def test_identifiers_sent_by_the_browser_cannot_widen_the_scope(self):
        self.assertEqual(self.names("maintainer", org="org-a", org_id=str(ORG_B)), ["alice"])
        status, body = self.stack.get("/team-analytics-api/v1/overview", "maintainer",
                                      headers={"X-Organization": "org-b"}, org="org-a")
        self.assertEqual(status, 200, body)
        self.assertEqual([row["user_name"] for row in body["by_annotator"]["rows"]], ["alice"])
        # an organization the caller does not belong to is refused, whatever else is sent
        self.assertRefused("maintainer", org="org-b", org_id=str(ORG_A))

    def test_cvat_is_asked_with_the_callers_own_credentials(self):
        self.stack.cvat.requests.clear()
        self.names("maintainer", org="org-a")
        self.assertTrue(self.stack.cvat.requests)
        for request in self.stack.cvat.requests:
            self.assertIn("sessionid=maintainer", request["headers"].get("Cookie", ""))
        paths = [request["path"] for request in self.stack.cvat.requests]
        self.assertIn("/api/users/self", paths)
        self.assertIn("/api/memberships", paths)

    def test_cvats_answers_are_reused_for_at_most_one_minute(self):
        self.assertEqual(self.names("maintainer", org="org-a"), ["alice"])
        self.stack.cvat.users["maintainer"].memberships["org-a"] = (ORG_A, "maintainer", False)
        self.stack.cvat.requests.clear()
        self.stack.now = NOW + timedelta(seconds=59)
        self.assertEqual(self.names("maintainer", org="org-a"), ["alice"])
        self.assertEqual(self.stack.cvat.requests, [])
        self.stack.now = NOW + timedelta(seconds=61)
        self.assertRefused("maintainer", org="org-a")

    def test_reuse_does_not_extend_the_minute(self):
        self.assertEqual(self.names("maintainer", org="org-a"), ["alice"])
        del self.stack.cvat.users["maintainer"].memberships["org-a"]
        for seconds in (20, 40, 59):
            self.stack.now = NOW + timedelta(seconds=seconds)
            self.assertEqual(self.names("maintainer", org="org-a"), ["alice"])
        self.stack.now = NOW + timedelta(seconds=61)
        self.assertRefused("maintainer", org="org-a")

    def test_one_callers_answers_are_never_given_to_another(self):
        self.assertEqual(self.names("maintainer", org="org-a"), ["alice"])
        self.assertEqual(self.names("admin"), ["paul", "bruno", "alice"])
        for session in ("worker", "maintainer-b", "unknown-session"):
            with self.subTest(session=session):
                code, body = self.stack.overview(session, org="org-a")
                self.assertIn(code, (401, 403), body)
        # the same caller asking about another organization is asked about anew
        self.assertRefused("maintainer", org="org-b")
        self.assertEqual(self.assertRefused("maintainer")["error"], "organization_required")

    def test_a_clock_moved_back_does_not_keep_old_answers(self):
        self.assertEqual(self.names("maintainer", org="org-a"), ["alice"])
        self.stack.cvat.users["maintainer"].memberships["org-a"] = (ORG_A, "maintainer", False)
        self.stack.now = NOW - timedelta(hours=1)
        self.assertRefused("maintainer", org="org-a")

    def test_after_the_minute_an_unreachable_cvat_means_refusal(self):
        self.assertEqual(self.names("maintainer", org="org-a"), ["alice"])
        self.stack.cvat.down = True
        self.stack.now = NOW + timedelta(seconds=61)
        status, body = self.stack.overview("maintainer", org="org-a")
        self.assertEqual(status, 503, body)
        self.assertEqual(body, {"error": "cvat_unavailable"})

    def test_a_maintainer_with_many_newer_memberships_is_still_asked_to_select_an_organization(self):
        # CVAT pages memberships, newest first; the one maintainer membership is the oldest of 102
        memberships = {"org-old": (90, "maintainer", True)}
        memberships.update({f"org-{n}": (100 + n, "worker", True) for n in range(101)})
        self.stack.cvat.add_user("veteran", FakeUser(10, "veteran", memberships=memberships))
        self.assertEqual(self.assertRefused("veteran")["error"], "organization_required")
        # and a member who reads no organization among as many is still refused
        self.stack.cvat.add_user("crowd", FakeUser(12, "crowd", memberships={
            f"org-{n}": (100 + n, "worker", True) for n in range(101)}))
        self.assertEqual(self.assertRefused("crowd")["error"], "forbidden")

    def test_an_answer_of_cvat_that_cannot_be_used_is_a_refusal_with_nothing_read(self):
        unusable = {
            "/api/users/self": [(200, []), (200, {"username": "maintainer"}), (200, {"id": "x", "username": "m"}),
                                (200, {"id": 3, "username": "maintainer", "groups": "administrators"})],
            "/api/organizations": [(200, []), (200, {"results": "org-a"}), (200, {"results": [{"slug": "org-a"}]})],
            "/api/memberships": [(200, []), (200, {"count": 1}), (200, {"results": [None]})],
        }
        minutes = 0
        for path, answers in unusable.items():
            for answer in answers:
                with self.subTest(path=path, answer=answer):
                    # a new minute each time, so that no answer is reused from the cache
                    minutes += 2
                    self.stack.now = NOW + timedelta(minutes=minutes)
                    self.stack.cvat.overrides = {path: answer}
                    status, body = self.stack.overview("maintainer", org="org-a")
                    self.assertEqual((status, body), (503, {"error": "cvat_unavailable"}))
        # the malformed answers were not kept: once CVAT answers properly again, the maintainer reads
        self.stack.cvat.overrides = {}
        self.assertEqual(self.names("maintainer", org="org-a"), ["alice"])


class CvatUnreachableTest(StackTestCase):
    def setUp(self) -> None:
        wait_for_clickhouse()
        # nothing listens on port 9 of the test container
        self.stack = Stack(cvat_url="http://127.0.0.1:9")
        self.addCleanup(self.stack.close)

    def test_the_service_refuses_when_cvat_cannot_be_reached(self):
        status, body = self.stack.overview("maintainer", org="org-a")
        self.assertEqual(status, 503, body)
        self.assertEqual(body, {"error": "cvat_unavailable"})
