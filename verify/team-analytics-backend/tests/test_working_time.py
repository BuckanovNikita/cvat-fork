"""Working time per annotator: the figure equals the server's job-bound working time."""

from tests.support import FakeUser, StackTestCase, at, working_time

ORG = 7
ALICE = (11, "alice")
BOB = (12, "bob")
CAROL = (13, "carol")


class OrganizationLeadCase(StackTestCase):
    """A maintainer of organization 7 reads its figures."""

    def setUp(self) -> None:
        super().setUp()
        self.stack.callers.add_user("lead", FakeUser(2, "lead", memberships={"org7": (ORG, "maintainer", True)}))

    def annotators(self, **query) -> list[dict]:
        status, body = self.stack.overview("lead", org="org7", **query)
        self.assertEqual(status, 200, body)
        # each row's operation parts are pinned against the full view in test_full_view.py
        return [{key: row[key] for key in ("user_id", "user_name", "working_time_ms")}
                for row in body["by_annotator"]["rows"]]


class WorkingTimePerAnnotatorTest(OrganizationLeadCase):
    def test_lists_annotators_with_last_seven_days_working_time_largest_first(self):
        self.stack.add_events([
            working_time(at("2026-11-13 09:10:00"), 600_000, user=ALICE, org=ORG),
            working_time(at("2026-11-12 22:59:59"), 1_200_000, user=ALICE, org=ORG, project=None, task=4, job=9),
            working_time(at("2026-11-11 08:00:00"), 3_600_000, user=BOB, org=ORG, project=2, task=2, job=2),
            working_time(at("2026-11-07 00:00:00"), 60_000, user=CAROL, org=ORG),
        ])
        self.stack.keep_refreshing_since(at("2026-11-05 00:00:00"))

        self.assertEqual(self.annotators(), [
            {"user_id": 12, "user_name": "bob", "working_time_ms": 3_600_000},
            {"user_id": 11, "user_name": "alice", "working_time_ms": 1_800_000},
            {"user_id": 13, "user_name": "carol", "working_time_ms": 60_000},
        ])

    def test_counts_only_job_bound_rows_inside_the_seven_days(self):
        self.stack.add_events([
            working_time(at("2026-11-13 10:00:00"), 500_000, user=ALICE, org=ORG),
            # no job: not job-bound, Grafana's working-time panel leaves it out
            working_time(at("2026-11-13 10:05:00"), 900_000, user=ALICE, org=ORG, project=None, task=None, job=None),
            # older than the seven days (the week starts 2026-11-07 00:00 UTC)
            working_time(at("2026-11-06 23:59:59"), 700_000, user=ALICE, org=ORG),
            # the payload is the figure, as in Grafana, even when duration is not filled in
            working_time(at("2026-11-12 10:00:00"), 250_000, user=ALICE, org=ORG, duration=0),
            # another organization's work is not this organization's
            working_time(at("2026-11-13 11:00:00"), 400_000, user=ALICE, org=8),
            # a personal-workspace row has no organization
            working_time(at("2026-11-13 12:00:00"), 300_000, user=ALICE, org=None),
        ])
        self.stack.keep_refreshing_since(at("2026-11-05 00:00:00"))

        self.assertEqual(self.annotators(), [{"user_id": 11, "user_name": "alice", "working_time_ms": 750_000}])

    def test_seven_days_follow_the_viewers_time_zone(self):
        # In Asia/Tokyo (UTC+9) on 2026-11-14 00:20 the week starts 2026-11-08 00:00 JST = 2026-11-07 15:00 UTC.
        self.stack.add_events([
            working_time(at("2026-11-07 14:59:00"), 100_000, user=ALICE, org=ORG),
            working_time(at("2026-11-07 15:00:00"), 200_000, user=ALICE, org=ORG),
        ])
        self.stack.keep_refreshing_since(at("2026-11-05 00:00:00"))

        self.assertEqual(self.annotators(tz="Asia/Tokyo")[0]["working_time_ms"], 200_000)
        self.assertEqual(self.annotators(tz="UTC")[0]["working_time_ms"], 300_000)


class TechnicalAccountsTest(OrganizationLeadCase):
    stack_options = {"technical_accounts": ("importer",)}

    def test_technical_accounts_are_not_annotators(self):
        self.stack.add_events([
            working_time(at("2026-11-13 10:00:00"), 500_000, user=ALICE, org=ORG),
            working_time(at("2026-11-13 10:00:00"), 900_000, user=(99, "importer"), org=ORG),
        ])
        self.stack.keep_refreshing_since(at("2026-11-05 00:00:00"))

        self.assertEqual([row["user_name"] for row in self.annotators()], ["alice"])
