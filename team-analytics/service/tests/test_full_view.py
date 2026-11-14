"""Full view: every row of one chart (GET list), by annotator, by project or by hotkey, for the period, the
filters and the shape switch, adding up to what the overview shows as its top rows and the rest."""

from __future__ import annotations

from tests.support import at, working_time
from tests.test_bounding_boxes import BOX, BOX_TRACK
from tests.test_creation_methods import paste
from tests.test_keyboard_mouse import summary
from tests.test_model_saved_boxes import detector, saved
from tests.test_operations import ALICE, BOB, ORG, OperationsCase, client, draw, seconds

MINUTE = 60_000
HOUR = 60 * MINUTE
T = "2026-11-13 10:00:00"
LIST = "/team-analytics-api/v1/list"


class FullViewCase(OperationsCase):
    stack_options = {"technical_accounts": ("importer",)}

    def listed(self, by: str, **query) -> dict:
        self.stack.keep_refreshing_since(at("2026-11-05 00:00:00"))
        status, body = self.stack.get(LIST, "lead", org="org7", by=by, **query)
        self.assertEqual(status, 200, body)
        return body

    def overview(self, **query) -> dict:
        status, body = self.stack.overview("lead", org="org7", **query)
        self.assertEqual(status, 200, body)
        return body

    @staticmethod
    def rows_by_id(body: dict) -> dict:
        return {row["id"]: row for row in body["rows"]}


class EveryAnnotatorTest(FullViewCase):
    def setUp(self) -> None:
        super().setUp()
        # twelve annotators in project 1 (more than the overview shows), 1..12 h; a 13th works only in project 2
        rows = [working_time(at("2026-11-12 09:00:00"), n * HOUR, user=(100 + n, f"user{n:02}"), org=ORG)
                for n in range(1, 13)]
        rows.append(working_time(at("2026-11-12 09:00:00"), 30 * MINUTE, user=(200, "zed"), org=ORG, project=2,
                                 task=2, job=2))
        self.stack.add_events(rows)

    def test_every_annotator_largest_first_with_the_whole_name_and_a_share_of_the_working_time(self):
        body = self.listed("annotators")

        self.assertEqual([row["user_name"] for row in body["rows"]],
                         [f"user{n:02}" for n in range(12, 0, -1)] + ["zed"])
        self.assertEqual(body["rows"][0]["id"], 112)
        self.assertEqual(body["rows"][0]["working_time_ms"], 12 * HOUR)
        whole = sum(n * HOUR for n in range(1, 13)) + 30 * MINUTE
        self.assertEqual(body["total"], {"count": 13, "working_time_ms": whole})
        self.assertAlmostEqual(body["rows"][0]["share"], 12 * HOUR / whole)
        self.assertAlmostEqual(sum(row["share"] for row in body["rows"]), 1)

    def test_the_list_holds_exactly_the_overview_top_rows_and_its_rest(self):
        listed = self.listed("annotators")
        overview = self.overview()["by_annotator"]

        self.assertEqual(len(listed["rows"]), len(overview["rows"]) + overview["rest"]["count"])
        self.assertEqual([row["id"] for row in listed["rows"][:len(overview["rows"])]],
                         [row["user_id"] for row in overview["rows"]])
        self.assertEqual(sum(row["working_time_ms"] for row in listed["rows"][len(overview["rows"]):]),
                         overview["rest"]["working_time_ms"])

    def test_the_project_filter_narrows_the_annotators_and_the_annotator_filter_keeps_everyone_listed(self):
        self.assertEqual(len(self.listed("annotators", project="2")["rows"]), 1)
        self.assertEqual(len(self.listed("annotators", annotator="200")["rows"]), 13)


class EveryProjectTest(FullViewCase):
    def test_every_project_with_no_project_as_0_and_the_annotator_filter_narrowing_them(self):
        self.stack.add_events([
            working_time(at("2026-11-12 09:00:00"), 3 * HOUR, user=ALICE, org=ORG, project=1),
            working_time(at("2026-11-12 13:00:00"), HOUR, user=ALICE, org=ORG, project=None, task=4, job=4),
            working_time(at("2026-11-12 10:00:00"), 2 * HOUR, user=BOB, org=ORG, project=2, task=2, job=2),
            *[working_time(at("2026-11-12 10:00:00"), MINUTE, user=BOB, org=ORG, project=10 + n, task=10 + n,
                           job=10 + n) for n in range(9)],
        ])

        body = self.listed("projects")
        self.assertEqual([(row["id"], row["working_time_ms"]) for row in body["rows"][:3]],
                         [(1, 3 * HOUR), (2, 2 * HOUR), (0, HOUR)])
        self.assertEqual(len(body["rows"]), 12)
        self.assertIsNone(body["rows"][0]["user_name"])
        overview = self.overview()["by_project"]
        self.assertEqual(len(body["rows"]), len(overview["rows"]) + overview["rest"]["count"])

        self.assertEqual([row["id"] for row in self.listed("projects", annotator=str(ALICE[0]))["rows"]], [1, 0])
        self.assertEqual(len(self.listed("projects", project="2")["rows"]), 12)


class RefusalsTest(FullViewCase):
    def test_an_unknown_list_is_a_bad_request(self):
        status, body = self.stack.get(LIST, "lead", org="org7", by="tasks")
        self.assertEqual((status, body["error"]), (400, "bad_request"))

    def test_the_access_rules_hold(self):
        status, _ = self.stack.get(LIST, "nobody", org="org7", by="annotators")
        self.assertEqual(status, 401)


class OperationsPerRowTest(FullViewCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.add_events([
            # alice, project 1: a box drawn in 10 s and a rectangle track drawn in 10 s; 2 min of working time
            client("load:job", seconds(T, 0)),
            draw(seconds(T, 10), **BOX),
            draw(seconds(T, 20), **BOX_TRACK),
            working_time(seconds(T, 20), 2 * MINUTE, user=ALICE, org=ORG),
            # bob, project 2: two boxes pasted 10 s after loading; only 5 s of working time (Other stays at 0)
            client("load:job", seconds(T, 100), user=BOB, project=2, task=2, job=2),
            paste(seconds(T, 110), 2, user=BOB, project=2, task=2, job=2, **{**BOX, "rectangle_count": 2}),
            working_time(seconds(T, 110), 5_000, user=BOB, org=ORG, project=2, task=2, job=2),
        ])

    def test_each_annotator_row_splits_its_working_time_by_operation_and_other(self):
        rows = self.rows_by_id(self.listed("annotators", shapes="all"))

        alice, bob = rows[ALICE[0]], rows[BOB[0]]
        self.assertEqual(alice["operations"]["creation"],
                         {"objects": 2, "timed_objects": 2, "time_ms": 20_000, "average_ms": 10_000})
        self.assertEqual(alice["operations"]["other"], {"time_ms": 2 * MINUTE - 20_000})
        self.assertEqual(alice["operations"]["alignment"]["average_ms"], None)
        self.assertEqual(bob["operations"]["creation"]["objects"], 2)
        self.assertEqual(bob["operations"]["other"], {"time_ms": 0}, "Other never goes below zero")

    def test_creation_splits_by_method_per_row_and_the_rows_add_up_to_the_overview(self):
        listed = self.listed("annotators", shapes="all")
        rows = self.rows_by_id(listed)

        self.assertEqual(rows[ALICE[0]]["methods"]["drawn"]["objects"], 2)
        self.assertEqual(rows[BOB[0]]["methods"]["pasted"]["objects"], 2)
        self.assertEqual(rows[BOB[0]]["methods"]["drawn"]["objects"], 0)
        overview = self.overview(shapes="all")
        creation = self.by_name(overview["operations"])["creation"]
        self.assertEqual(sum(row["operations"]["creation"]["objects"] for row in listed["rows"]),
                         creation["objects"])

    def test_bounding_boxes_count_only_single_frame_rectangles_in_every_row(self):
        listed = self.listed("projects", shapes="bounding_boxes")

        self.assertEqual(listed["shapes"], "bounding_boxes")
        self.assertFalse(listed["legacy"])
        rows = self.rows_by_id(listed)
        self.assertEqual(rows[1]["operations"]["creation"]["objects"], 1)
        self.assertEqual(rows[1]["operations"]["other"], {"time_ms": 2 * MINUTE - 10_000})
        self.assertEqual(rows[2]["operations"]["creation"]["objects"], 2)


class LegacyListTest(FullViewCase):
    def test_a_list_without_shape_tagged_work_is_legacy_and_counts_all_shapes(self):
        self.stack.add_events([
            client("load:job", seconds(T, 0)),
            draw(seconds(T, 10)),
            working_time(seconds(T, 10), MINUTE, user=ALICE, org=ORG),
        ])

        listed = self.listed("annotators", shapes="bounding_boxes")
        self.assertTrue(listed["legacy"])
        self.assertEqual(listed["shapes"], "all")
        self.assertEqual(listed["rows"][0]["operations"]["creation"]["objects"], 1)


class ModelPerRowTest(FullViewCase):
    def test_model_is_detector_boxes_per_annotator_and_also_technical_saves_per_project(self):
        self.stack.add_events([
            client("load:job", seconds(T, 0)),
            draw(seconds(T, 10), **BOX),
            detector(seconds(T, 20), 3, 3),
            working_time(seconds(T, 20), MINUTE, user=ALICE, org=ORG),
            saved("create", seconds(T, 30), 5, project=2, task=2, job=2),
        ])

        annotators = self.listed("annotators", shapes="bounding_boxes")
        self.assertEqual([(row["id"], row["model"]) for row in annotators["rows"]], [(ALICE[0], 3)])
        projects = self.rows_by_id(self.listed("projects", shapes="bounding_boxes"))
        self.assertEqual((projects[1]["model"], projects[2]["model"]), (3, 5))
        self.assertEqual(projects[2]["working_time_ms"], 0)
        filtered = self.rows_by_id(self.listed("projects", shapes="bounding_boxes", annotator=str(ALICE[0])))
        self.assertNotIn(2, filtered, "a technical account's saves are no annotator's")


class EveryHotkeyTest(FullViewCase):
    def test_every_hotkey_most_used_first_with_its_share_and_both_filters(self):
        hotkeys = {f"ACTION_{n:02}": n for n in range(1, 11)}
        self.stack.add_events([
            client("load:job", seconds(T, 0)),
            summary(seconds(T, 10), hotkeys=hotkeys, mouse={"header": 4}),
            client("load:job", seconds(T, 20), user=BOB, project=2, task=2, job=2),
            summary(seconds(T, 30), hotkeys={"ACTION_01": 100}, user=BOB, project=2, task=2, job=2),
        ])

        body = self.listed("hotkeys")
        self.assertEqual([(row["action"], row["actions"]) for row in body["rows"][:3]],
                         [("ACTION_01", 101), ("ACTION_10", 10), ("ACTION_09", 9)])
        self.assertEqual(len(body["rows"]), 10)
        self.assertEqual(body["hotkey_actions"], 155)
        self.assertAlmostEqual(body["rows"][0]["share"], 101 / 155)
        overview = self.overview()["input"]
        self.assertEqual(body["hotkey_actions"], overview["hotkey_actions"])
        self.assertEqual(len(body["rows"]), len(overview["top_hotkeys"]) + overview["rest"]["count"])

        self.assertEqual(self.listed("hotkeys", project="2")["rows"],
                         [{"action": "ACTION_01", "actions": 100, "share": 1.0}])
        self.assertEqual(len(self.listed("hotkeys", annotator=str(ALICE[0]))["rows"]), 10)


class ProcessedTest(FullViewCase):
    def test_a_period_not_wholly_processed_says_so(self):
        self.stack.add_events([working_time(at("2026-10-01 10:00:00"), HOUR, user=ALICE, org=ORG)])
        self.stack.refresh()
        status, body = self.stack.get(LIST, "lead", org="org7", by="annotators", period="year")
        self.assertEqual(status, 200, body)
        self.assertFalse(body["processed"])
        self.assertEqual(body["processed"], self.overview(period="year")["processed"])
