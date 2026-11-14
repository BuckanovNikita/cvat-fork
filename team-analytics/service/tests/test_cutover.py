"""The cutover to the new activity logging: the first shape-tagged event on the instance decides which periods
are legacy (all of it before), partly legacy (it falls inside) or not legacy (all of it after), whatever the
scope holds."""

from tests.support import FakeUser, StackTestCase, at, working_time
from tests.test_bounding_boxes import BOX
from tests.test_operations import client, draw

ORG_A, ORG_B = 7, 8
ALICE = (11, "alice")
BRUNO = (21, "bruno")
API = "/team-analytics-api/v1/"
CUTOVER = "2026-11-02T10:00:00+00:00"  # the hour of the first shape-tagged event (org A)


class CutoverCase(StackTestCase):
    stack_options = {"refresh_window_hours": 400 * 24}

    def setUp(self) -> None:
        super().setUp()
        cvat = self.stack.cvat
        cvat.add_user("lead-a", FakeUser(2, "lead-a", memberships={"org-a": (ORG_A, "maintainer", True)}))
        cvat.add_user("lead-b", FakeUser(3, "lead-b", memberships={"org-b": (ORG_B, "maintainer", True)}))

    def get(self, endpoint: str, session: str = "lead-a", **query) -> dict:
        query.setdefault("org", "org-a" if session == "lead-a" else "org-b")
        status, body = self.stack.get(API + endpoint, session, **query)
        self.assertEqual(status, 200, body)
        return body

    def operations(self, session: str = "lead-a", **query) -> dict:
        return self.get("overview", session, **query)["operations"]

    @staticmethod
    def created(operations: dict) -> int:
        return next(row["objects"] for row in operations["rows"] if row["operation"] == "creation")


class WithCutoverTest(CutoverCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.add_events([
            # organization A: the stock UI in October, the new logging from 2 November 10:00 on
            working_time(at("2026-10-20 10:00:00"), 3_600_000, user=ALICE, org=ORG_A),
            client("load:job", at("2026-10-20 10:00:00")),
            draw(at("2026-10-20 10:00:10")),
            draw(at("2026-10-20 10:00:20")),
            client("load:job", at("2026-11-02 10:30:00")),
            draw(at("2026-11-02 10:30:10"), input_method="mouse", **BOX),
            # an operation logged without a shape type after the cutover (a 3D job)
            client("load:job", at("2026-11-10 10:00:00")),
            draw(at("2026-11-10 10:00:10")),
            # organization B, this week only: review work (working time) and a 3D job, never a tagged event
            working_time(at("2026-11-11 10:00:00"), 1_800_000, user=BRUNO, org=ORG_B),
            client("load:job", at("2026-11-11 11:00:00"), user=BRUNO, org=ORG_B),
            draw(at("2026-11-11 11:00:10"), user=BRUNO, org=ORG_B),
        ])
        self.stack.refresh()

    def test_status_reports_the_cutover(self):
        self.assertEqual(self.get("status")["cutover"], {"at": CUTOVER})
        self.assertEqual(self.get("status", "lead-b")["cutover"], {"at": CUTOVER})

    def test_a_period_that_ends_before_the_cutover_is_legacy(self):
        operations = self.operations(period="month", month="2026-10", shapes="bounding_boxes")
        self.assertEqual((operations["legacy"], operations["partly_legacy"], operations["shapes"]),
                         (True, False, "all"))
        self.assertEqual(self.created(operations), 2)

    def test_a_period_that_holds_the_cutover_is_partly_legacy_and_keeps_the_shape_switch(self):
        boxes = self.operations(period="month", month="2026-11", shapes="bounding_boxes")
        self.assertEqual((boxes["legacy"], boxes["partly_legacy"], boxes["cutover"], boxes["shapes"]),
                         (False, True, CUTOVER, "bounding_boxes"))
        self.assertEqual(self.created(boxes), 1, "only the bounding box drawn after the cutover")
        self.assertEqual(self.created(self.operations(period="month", month="2026-11", shapes="all")), 2)

    def test_a_period_after_the_cutover_is_never_legacy_even_without_tagged_events_in_its_scope(self):
        for session in ("lead-a", "lead-b"):
            with self.subTest(session=session):
                operations = self.operations(session, shapes="bounding_boxes")
                self.assertEqual((operations["legacy"], operations["partly_legacy"], operations["shapes"]),
                                 (False, False, "bounding_boxes"))
                self.assertEqual(self.created(operations), 0)
                methods = self.get("overview", session, shapes="bounding_boxes")["creation_methods"]
                self.assertEqual(methods["shapes"], "bounding_boxes")

    def test_details_and_full_view_decide_by_the_same_cutover(self):
        for endpoint in ("details", "list?by=annotators"):
            path, _, by = endpoint.partition("?by=")
            extra = {"by": by} if by else {}
            with self.subTest(endpoint=endpoint):
                week_b = self.get(path, "lead-b", shapes="bounding_boxes", **extra)
                self.assertEqual((week_b["legacy"], week_b["partly_legacy"], week_b["shapes"]),
                                 (False, False, "bounding_boxes"))
                october = self.get(path, period="month", month="2026-10", shapes="bounding_boxes", **extra)
                self.assertEqual((october["legacy"], october["partly_legacy"], october["shapes"]), (True, False, "all"))
                november = self.get(path, period="month", month="2026-11", shapes="bounding_boxes", **extra)
                self.assertEqual((november["legacy"], november["partly_legacy"], november["cutover"]),
                                 (False, True, CUTOVER))

    def test_an_empty_period_that_holds_the_cutover_is_neither_legacy_nor_partly_legacy(self):
        # a project with no job work at all: the period holds the cutover, its scope holds nothing
        empty = {"period": "month", "month": "2026-11", "project": "999", "shapes": "bounding_boxes"}
        answers = {
            "overview": self.operations(**empty),
            "details": self.get("details", **empty),
            "list": self.get("list", by="annotators", **empty),
        }
        for endpoint, body in answers.items():
            with self.subTest(endpoint=endpoint):
                self.assertEqual((body["legacy"], body["partly_legacy"]), (False, False))

    def test_trend_buckets_are_marked_by_the_cutover(self):
        monthly = self.get("trends", step="month", shapes="bounding_boxes")
        starts = [bucket["start"] for bucket in monthly["buckets"]]
        points = dict(zip(starts, monthly["lines"][0]["points"], strict=True))
        self.assertEqual(monthly["shapes"], "bounding_boxes")
        self.assertTrue(points["2026-10-01"]["legacy"])
        self.assertIsNone(points["2026-10-01"]["boxes"])
        # the month that holds the cutover is not legacy: its boxes are the tagged ones
        self.assertFalse(points["2026-11-01"]["legacy"])
        self.assertEqual(points["2026-11-01"]["boxes"], 1)

        weekly_b = self.get("trends", "lead-b", shapes="bounding_boxes")
        last = weekly_b["lines"][0]["points"][-1]
        self.assertEqual((weekly_b["buckets"][-1]["start"], last["legacy"], last["boxes"]), ("2026-11-09", False, 0))
        self.assertTrue(last["hotkey_recorded"])


class WithoutCutoverTest(CutoverCase):
    def test_without_any_shape_tagged_event_a_period_with_job_work_is_legacy(self):
        self.stack.add_events([
            client("load:job", at("2026-11-13 10:00:00")),
            draw(at("2026-11-13 10:00:05")),
        ])
        self.stack.refresh()
        operations = self.operations(shapes="bounding_boxes")
        self.assertEqual((operations["legacy"], operations["partly_legacy"], operations["cutover"], operations["shapes"]),
                         (True, False, None, "all"))
        self.assertEqual(self.get("status")["cutover"], {"at": None})
        # every trend bucket is before the (unknown) cutover: the trends count all shapes
        trends = self.get("trends", shapes="bounding_boxes")
        last = trends["lines"][0]["points"][-1]
        self.assertEqual((trends["shapes"], last["legacy"], last["boxes"]), ("all", True, 1))

    def test_an_empty_period_is_not_legacy(self):
        self.stack.refresh()
        operations = self.operations()
        self.assertEqual((operations["legacy"], operations["partly_legacy"]), (False, False))
