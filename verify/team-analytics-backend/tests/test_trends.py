"""Trends: working time, boxes created, average time per box and hotkey share over the last twelve weeks or
months, for the scope or for up to five compared annotators or projects."""

from __future__ import annotations

from tests.support import FakeUser, StackTestCase, at, working_time
from tests.test_keyboard_mouse import summary
from tests.test_operations import ALICE, BOB, ORG, client, draw, seconds

MINUTE = 60_000
HOUR = 60 * MINUTE
CAROL = (13, "carol")
BOX = {"shape_type": "rectangle", "rectangle_count": 1, "object_type": "shape", "input_method": "mouse"}
POLYGON = {"shape_type": "polygon", "rectangle_count": 0, "object_type": "shape", "input_method": "mouse"}

# support.NOW is Friday 2026-11-13 15:20 UTC: the current week started on Monday 2026-11-09
WEEKS = ["2026-08-24", "2026-08-31", "2026-09-07", "2026-09-14", "2026-09-21", "2026-09-28", "2026-10-05",
         "2026-10-12", "2026-10-19", "2026-10-26", "2026-11-02", "2026-11-09"]
MONTHS = ["2025-12-01", "2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01",
          "2026-07-01", "2026-08-01", "2026-09-01", "2026-10-01", "2026-11-01"]


class TrendsCase(StackTestCase):
    # one refresh covers more than a year, so every bucket is processed
    stack_options = {"refresh_window_hours": 400 * 24, "technical_accounts": (99,)}

    def setUp(self) -> None:
        super().setUp()
        self.stack.callers.add_user("lead", FakeUser(2, "lead", groups=["admin"], memberships={"org7": (ORG, "maintainer", True)}))

    def trends_response(self, **query) -> tuple[int, dict]:
        query.setdefault("org", "org7")
        return self.stack.get("/api/team-analytics/trends", "lead", **query)

    def trends(self, **query) -> dict:
        status, body = self.trends_response(**query)
        self.assertEqual(status, 200, body)
        return body

    @staticmethod
    def values(line: dict, key: str) -> list:
        return [point[key] for point in line["points"]]


class BucketsTest(TrendsCase):
    def test_twelve_monday_weeks_ending_with_the_current_week_whatever_the_period(self):
        self.stack.add_events([
            working_time(at("2026-08-24 00:30:00"), HOUR, user=ALICE, org=ORG),
            working_time(at("2026-08-23 23:30:00"), 5 * HOUR, user=ALICE, org=ORG),  # before the first week
            working_time(at("2026-11-08 12:00:00"), 2 * HOUR, user=ALICE, org=ORG),  # Sunday: the week of Nov 2
            working_time(at("2026-11-09 12:00:00"), 3 * HOUR, user=ALICE, org=ORG),
            working_time(at("2026-11-13 12:00:00"), 30 * MINUTE, user=BOB, org=ORG),
        ])
        self.stack.refresh()

        for period in ("week", "year", "month"):
            body = self.trends(period=period)
            self.assertEqual(body["step"], "week")
            self.assertEqual([bucket["start"] for bucket in body["buckets"]], WEEKS)
            self.assertEqual(len(body["lines"]), 1)
            self.assertEqual(self.values(body["lines"][0], "working_time_ms"),
                             [HOUR] + [0] * 9 + [2 * HOUR, 3 * HOUR + 30 * MINUTE])

    def test_weeks_follow_the_viewer_time_zone(self):
        # Sunday 22:30 UTC is Monday 01:30 in Europe/Helsinki (UTC+2 in November)
        self.stack.add_events([working_time(at("2026-11-08 22:30:00"), HOUR, user=ALICE, org=ORG)])
        self.stack.refresh()

        utc = self.values(self.trends(tz="UTC")["lines"][0], "working_time_ms")
        helsinki = self.values(self.trends(tz="Europe/Helsinki")["lines"][0], "working_time_ms")

        self.assertEqual(utc[-2:], [HOUR, 0])
        self.assertEqual(helsinki[-2:], [0, HOUR])

    def test_twelve_calendar_months_ending_with_the_current_month(self):
        self.stack.add_events([
            working_time(at("2025-12-01 10:00:00"), HOUR, user=ALICE, org=ORG),
            working_time(at("2025-11-30 10:00:00"), 7 * HOUR, user=ALICE, org=ORG),  # before the first month
            working_time(at("2026-11-02 10:00:00"), 2 * HOUR, user=ALICE, org=ORG),
        ])
        self.stack.refresh()

        body = self.trends(step="month")

        self.assertEqual(body["step"], "month")
        self.assertEqual([bucket["start"] for bucket in body["buckets"]], MONTHS)
        self.assertEqual(self.values(body["lines"][0], "working_time_ms"), [HOUR] + [0] * 10 + [2 * HOUR])

    def test_bad_queries_are_refused(self):
        for query in ({"step": "day"}, {"compare": "teams"}, {"ids": "1,x"}, {"ids": "1,2,3,4,5,6"}):
            status, body = self.trends_response(**query)
            self.assertEqual(status, 400, query)
            self.assertEqual(body["error"], "bad_request")


class FiguresTest(TrendsCase):
    def setUp(self) -> None:
        super().setUp()
        current = "2026-11-10 10:00:00"  # week of Nov 9
        legacy = "2026-10-13 10:00:00"  # week of Oct 12: events of the stock UI, no shape type
        tagged_no_input = "2026-10-20 10:00:00"  # week of Oct 19
        self.stack.add_events([
            working_time(at(current), HOUR, user=ALICE, org=ORG),
            client("load:job", seconds(current, 0)),
            draw(seconds(current, 10), **BOX),  # 10 s
            draw(seconds(current, 30), **POLYGON),  # 20 s
            client("paste:object", seconds(current, 40), count=3, **{**BOX, "rectangle_count": 3}),  # 10 s
            summary(seconds(current, 100), {"NEXT_FRAME": 3}, {"header": 1, "canvas": 10}),
            working_time(at(legacy), 2 * HOUR, user=ALICE, org=ORG),
            client("load:job", seconds(legacy, 0)),
            draw(seconds(legacy, 10)),
            draw(seconds(legacy, 20)),
            client("load:job", seconds(tagged_no_input, 0)),
            draw(seconds(tagged_no_input, 4), **BOX),
        ])
        self.stack.refresh()

    def test_boxes_created_and_average_time_per_box_under_the_shape_switch(self):
        boxes = self.trends(shapes="bounding_boxes")["lines"][0]["points"]
        everything = self.trends(shapes="all")["lines"][0]["points"]

        self.assertEqual((boxes[-1]["boxes"], boxes[-1]["average_ms"]), (4, 5000))
        self.assertEqual((everything[-1]["boxes"], everything[-1]["average_ms"]), (5, 8000))
        self.assertEqual((boxes[8]["boxes"], boxes[8]["average_ms"]), (1, 4000))
        # an empty week: nothing created, no average
        self.assertEqual((boxes[0]["boxes"], boxes[0]["average_ms"]), (0, None))
        self.assertEqual(self.trends(shapes="all")["shapes"], "all")
        self.assertEqual(self.trends()["shapes"], "all")
        self.assertEqual(self.trends(shapes="bounding_boxes")["shapes"], "bounding_boxes")

    def test_a_week_before_the_new_logging_has_no_box_figures_and_no_hotkey_share(self):
        boxes = self.trends(shapes="bounding_boxes")["lines"][0]["points"]
        everything = self.trends(shapes="all")["lines"][0]["points"]

        legacy = boxes[7]
        self.assertTrue(legacy["legacy"])
        self.assertEqual(legacy["working_time_ms"], 2 * HOUR)
        self.assertEqual((legacy["boxes"], legacy["average_ms"]), (None, None))
        self.assertFalse(legacy["hotkey_recorded"])
        self.assertIsNone(legacy["hotkey_share"])
        # all shapes are known for old events too
        self.assertEqual(everything[7]["boxes"], 2)
        self.assertFalse(everything[7]["hotkey_recorded"])

    def test_a_line_with_only_work_before_the_cutover_has_no_box_figure_for_those_weeks(self):
        # the cutover is the first tagged event (Alice, week of Oct 19); Bob worked only before it. A trend is all
        # shapes only when every bucket is before the cutover (tests/test_cutover.py), not because of its lines.
        legacy = "2026-10-13 10:00:00"
        self.stack.add_events([
            working_time(at(legacy), HOUR, user=BOB, org=ORG),
            client("load:job", seconds(legacy, 0), user=BOB),
            draw(seconds(legacy, 10), user=BOB),
            draw(seconds(legacy, 30), user=BOB),
        ])
        self.stack.refresh()

        body = self.trends(shapes="bounding_boxes", annotator=BOB[0])
        everything = self.trends(shapes="all", annotator=BOB[0])

        self.assertEqual(body["shapes"], "bounding_boxes")
        point = body["lines"][0]["points"][7]
        self.assertTrue(point["legacy"])
        self.assertEqual((point["boxes"], point["average_ms"]), (None, None))
        self.assertFalse(point["hotkey_recorded"])
        # under All shapes the old weeks count every object
        old = everything["lines"][0]["points"][7]
        self.assertEqual((everything["shapes"], old["boxes"], old["average_ms"]), ("all", 2, 15000))

    def test_hotkey_share_of_hotkey_and_mouse_actions(self):
        points = self.trends()["lines"][0]["points"]

        self.assertEqual((points[-1]["hotkey_actions"], points[-1]["mouse_actions"]), (3, 1))
        self.assertAlmostEqual(points[-1]["hotkey_share"], 0.75)
        # tagged work without a summary: recorded, but no actions to share
        self.assertTrue(points[8]["hotkey_recorded"])
        self.assertIsNone(points[8]["hotkey_share"])
        # an empty week is not a week before the new logging
        self.assertFalse(points[0]["legacy"])
        self.assertTrue(points[0]["hotkey_recorded"])


class ScopeAndComparisonTest(TrendsCase):
    def setUp(self) -> None:
        super().setUp()
        week = "2026-11-10 10:00:00"
        self.stack.add_events([
            working_time(at(week), HOUR, user=ALICE, org=ORG, project=1),
            working_time(at(week), 2 * HOUR, user=ALICE, org=ORG, project=2, task=2, job=2),
            working_time(at(week), 4 * HOUR, user=BOB, org=ORG, project=2, task=2, job=3),
            working_time(at(week), 8 * HOUR, user=CAROL, org=8, project=3, task=3, job=4),  # another org
            working_time(at(week), 16 * HOUR, user=(99, "robot"), org=ORG, project=1),  # technical account
        ])
        self.stack.refresh()

    def last(self, line: dict) -> int:
        return line["points"][-1]["working_time_ms"]

    def test_the_scope_line_follows_the_project_and_annotator_filters(self):
        self.assertEqual(self.last(self.trends()["lines"][0]), 7 * HOUR)
        self.assertEqual(self.last(self.trends(project=2)["lines"][0]), 6 * HOUR)
        self.assertEqual(self.last(self.trends(annotator=ALICE[0])["lines"][0]), 3 * HOUR)
        self.assertEqual(self.last(self.trends(project=2, annotator=ALICE[0])["lines"][0]), 2 * HOUR)
        self.assertIsNone(self.trends()["lines"][0]["id"])

    def test_compared_annotators_are_one_line_each_in_the_order_asked_under_the_project_filter(self):
        body = self.trends(compare="annotators", ids=f"{BOB[0]},{ALICE[0]}", project=2, annotator=ALICE[0])

        self.assertEqual([(line["id"], line["user_name"], self.last(line)) for line in body["lines"]],
                         [(BOB[0], "bob", 4 * HOUR), (ALICE[0], "alice", 2 * HOUR)])
        self.assertTrue(all(len(line["points"]) == 12 for line in body["lines"]))

    def test_compared_projects_are_one_line_each_under_the_annotator_filter(self):
        body = self.trends(compare="projects", ids="2,1", project=1, annotator=ALICE[0])

        self.assertEqual([(line["id"], self.last(line)) for line in body["lines"]], [(2, 2 * HOUR), (1, HOUR)])

    def test_nobody_outside_the_scope_appears_in_a_comparison(self):
        body = self.trends(compare="annotators", ids=f"{CAROL[0]},99")

        self.assertEqual([(line["id"], self.last(line)) for line in body["lines"]], [(CAROL[0], 0), (99, 0)])
        self.assertEqual([line["user_name"] for line in body["lines"]], [None, None])

    def test_candidates_are_everyone_of_the_compared_kind_with_work_in_scope(self):
        annotators = self.trends()["candidates"]
        projects = self.trends(compare="projects", annotator=ALICE[0])["candidates"]

        self.assertEqual([(row["id"], row["user_name"], row["working_time_ms"]) for row in annotators],
                         [(BOB[0], "bob", 4 * HOUR), (ALICE[0], "alice", 3 * HOUR)])
        self.assertEqual([(row["id"], row["working_time_ms"]) for row in projects], [(2, 2 * HOUR), (1, HOUR)])
        self.assertEqual([row["id"] for row in self.trends(project=1)["candidates"]], [ALICE[0]])


class ProcessedTest(TrendsCase):
    stack_options = {}

    def test_a_bucket_is_processed_only_when_all_of_it_is(self):
        self.stack.add_events([
            working_time(at("2026-11-03 10:00:00"), HOUR, user=ALICE, org=ORG),
            working_time(at("2026-11-12 10:00:00"), HOUR, user=ALICE, org=ORG),
        ])
        self.stack.refresh()  # the trailing 48 h only

        self.assertEqual([bucket["processed"] for bucket in self.trends()["buckets"]], [False] * 12)

        for _ in range(20):  # history: one day per step, newest first
            self.stack.engine.step()
            if self.trends()["buckets"][-1]["processed"]:
                break
        body = self.trends()
        self.assertEqual([bucket["processed"] for bucket in body["buckets"]], [False] * 11 + [True])
        # an unprocessed bucket has no value, only its flags; the processed one beside it keeps its figures
        (line,) = body["lines"]
        withheld = {"working_time_ms": None, "legacy": False, "boxes": None, "timed_boxes": None,
                    "box_time_ms": None, "average_ms": None, "hotkey_recorded": True, "hotkey_actions": None,
                    "mouse_actions": None, "hotkey_share": None}
        # `legacy: False, hotkey_recorded: True` pin a recorded limit (docs/fork-specification.md, "Known limit
        # of unprocessed periods"): the flags of an unprocessed bucket describe only what is processed of it and
        # can change, even to the opposite, once it is processed
        self.assertEqual(line["points"][:11], [withheld] * 11)
        # every key outside a point's envelope is null, so a field added to a point later is withheld too
        for point in line["points"][:11]:
            self.assertLessEqual({key for key, value in point.items() if value is not None},
                                 {"legacy", "hotkey_recorded"})
        self.assertEqual(line["points"][11]["working_time_ms"], HOUR)

        for _ in range(20):
            self.stack.engine.step()
        body = self.trends()
        self.assertEqual([bucket["processed"] for bucket in body["buckets"]], [True] * 12)
        self.assertEqual([point["working_time_ms"] for point in body["lines"][0]["points"]],
                         [0] * 10 + [HOUR, HOUR])

    def test_a_candidate_has_working_time_only_from_processed_buckets(self):
        self.stack.add_events([
            working_time(at("2026-11-03 10:00:00"), 5 * HOUR, user=ALICE, org=ORG),
            working_time(at("2026-11-12 10:00:00"), HOUR, user=ALICE, org=ORG),
            working_time(at("2026-11-12 11:00:00"), 2 * HOUR, user=BOB, org=ORG),
            working_time(at("2026-10-05 10:00:00"), 3 * HOUR, user=CAROL, org=ORG),
        ])
        self.stack.refresh()  # the trailing 48 h only: no bucket is processed

        def candidates() -> list:
            return [(row["id"], row["working_time_ms"]) for row in self.trends()["candidates"]]

        # the trailing hours are computed, but they lie in the current week, which is not processed: whoever
        # worked in them is offered with no figure and not ranked by that time (it would put Bob first), by id
        self.assertEqual(candidates(), [(ALICE[0], None), (BOB[0], None)])
        for row in self.trends()["candidates"]:
            self.assertLessEqual({key for key, value in row.items() if value is not None}, {"id", "user_name"})

        for _ in range(20):  # history: one day per step, newest first
            self.stack.engine.step()
            if self.trends()["buckets"][-1]["processed"]:
                break
        self.assertEqual([bucket["processed"] for bucket in self.trends()["buckets"]], [False] * 11 + [True])
        # the processed current week counts: Bob's two hours, Alice's one (her older work and Carol's are
        # not computed yet)
        self.assertEqual(candidates(), [(BOB[0], 2 * HOUR), (ALICE[0], HOUR)])

        # history goes on to compute the 3rd: Alice's five hours there are stored, but their week (from the
        # 2nd) is not processed while the days before the 3rd back to Carol's are not, so they count for nothing
        self.stack.callers.add_user("admin", FakeUser(1, "admin", groups=["admin"]))
        for _ in range(20):
            self.stack.engine.step()
            status, body = self.stack.get("/api/team-analytics/status", "admin", org="org7")
            self.assertEqual(status, 200, body)
            if body["history"]["ready_from_day"] == "2026-11-03":
                break
        self.assertEqual(body["history"]["ready_from_day"], "2026-11-03")
        self.assertEqual([bucket["processed"] for bucket in self.trends()["buckets"]], [False] * 11 + [True])
        self.assertEqual(candidates(), [(BOB[0], 2 * HOUR), (ALICE[0], HOUR)])

        for _ in range(60):
            self.stack.engine.step()
        self.assertEqual([bucket["processed"] for bucket in self.trends()["buckets"]], [True] * 12)
        self.assertEqual(candidates(), [(ALICE[0], 6 * HOUR), (CAROL[0], 3 * HOUR), (BOB[0], 2 * HOUR)])
