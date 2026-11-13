"""Class change: the UI's `team_analytics:class_change` debug records counted as the fourth operation."""

from __future__ import annotations

from tests.support import at, working_time
from tests.test_bounding_boxes import BOX, BOX_TRACK, POLYGON, drag
from tests.test_operations import ALICE, ORG, OperationsCase, client, draw, seconds

CLASS_CHANGE = "team_analytics:class_change"


def class_change(when, count: int = 1, **payload) -> dict:
    """A class change record as the UI logs it: a debug:info event through the job logger."""
    fields = dict(BOX, input_method="mouse")
    fields.update(payload)
    return client("debug:info", when, count=count, obj_name=CLASS_CHANGE, **fields)


class ClassChangeCountingTest(OperationsCase):
    def setUp(self) -> None:
        super().setUp()
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10), **BOX),  # creation, 10 s
            class_change(seconds(t, 14)),  # one box, 4 s
            class_change(seconds(t, 20)),  # changed back: counts again, 6 s
            # three selected objects: two single-frame rectangles and a polygon, 12 s
            class_change(seconds(t, 32), count=3, shape_type="mixed", rectangle_count=2, object_type="shape",
                         input_method="hotkey"),
            class_change(seconds(t, 40), **BOX_TRACK),  # a rectangle track: all shapes only, 8 s
            working_time(at(t), 100_000, user=ALICE, org=ORG),
        ])

    def test_each_object_of_a_class_change_counts_and_a_change_back_counts_again(self):
        row = self.by_name(self.operations(shapes="all"))["class_change"]

        self.assertEqual(row["objects"], 6)
        self.assertEqual(row["timed_objects"], 6)
        self.assertEqual(row["time_ms"], 30_000)
        self.assertEqual(row["average_ms"], 5_000)

    def test_class_change_takes_its_share_of_working_time(self):
        operations = self.operations(shapes="all")
        rows = self.by_name(operations)

        self.assertEqual([row["operation"] for row in operations["rows"]],
                         ["creation", "alignment", "class_change", "deletion", "other"])
        self.assertEqual(operations["active_time_ms"], 100_000)
        self.assertAlmostEqual(rows["class_change"]["share"], 0.30)
        self.assertEqual(rows["other"]["time_ms"], 100_000 - 40_000)

    def test_under_bounding_boxes_only_single_frame_rectangles_count(self):
        row = self.by_name(self.operations(shapes="bounding_boxes"))["class_change"]

        # the two single boxes, and two of the three selected objects with 2/3 of that change's 12 s
        self.assertEqual(row["objects"], 4)
        self.assertEqual(row["time_ms"], 4_000 + 6_000 + 8_000)


class OtherDebugRecordsTest(OperationsCase):
    def test_other_debug_records_are_no_operation(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10), **BOX),
            client("debug:info", seconds(t, 20), count=1, obj_name="team_analytics:model_creation",
                   rectangle_count=1),
            client("debug:info", seconds(t, 30), obj_name="team_analytics:input_summary"),
            client("debug:info", seconds(t, 40), obj_name="chunk_download_bandwidth", job=None),
        ])

        rows = self.by_name(self.operations(shapes="all"))

        self.assertEqual([rows[name]["objects"] for name in ("creation", "alignment", "class_change", "deletion")],
                         [1, 0, 0, 0])

    def test_a_class_change_record_outside_a_job_is_no_operation(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10), **BOX),
            class_change(seconds(t, 20), job=None, task=None, project=None),
        ])

        self.assertEqual(self.by_name(self.operations(shapes="all"))["class_change"]["objects"], 0)


class ClassChangeAndAlignmentTest(OperationsCase):
    def test_a_class_change_between_two_drags_of_one_box_ends_the_alignment(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            drag(seconds(t, 10), 5),
            class_change(seconds(t, 15)),
            drag(seconds(t, 20), 5),
        ])

        rows = self.by_name(self.operations(shapes="all"))

        self.assertEqual(rows["alignment"]["objects"], 2)
        self.assertEqual(rows["class_change"]["objects"], 1)


class LegacyClassChangeTest(OperationsCase):
    def test_a_legacy_period_has_no_class_change_and_stays_legacy(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10)),
            client("delete:object", seconds(t, 20), count=1),
        ])

        operations = self.operations(shapes="bounding_boxes")

        self.assertTrue(operations["legacy"])
        self.assertEqual(self.by_name(operations)["class_change"]["objects"], 0)

    def test_a_class_change_record_ends_the_legacy_period(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10)),
            class_change(seconds(t, 20), **POLYGON),
        ])

        operations = self.operations(shapes="all")

        self.assertFalse(operations["legacy"])
        self.assertEqual(self.by_name(operations)["class_change"]["objects"], 1)
