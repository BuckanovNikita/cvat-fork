"""Bounding boxes against all shapes, and alignments counted once per run of adjustments to one object."""

from __future__ import annotations

from datetime import timedelta

from tests.support import at, working_time
from tests.test_operations import ALICE, BOB, ORG, OperationsCase, client, draw, seconds

BOX = {"shape_type": "rectangle", "rectangle_count": 1, "object_type": "shape"}
BOX_TRACK = {"shape_type": "rectangle", "rectangle_count": 0, "object_type": "track"}
POLYGON = {"shape_type": "polygon", "rectangle_count": 0, "object_type": "shape"}
BROWSER = 1234567890


def adjust(scope: str, end, ref: int | None, frame: int = 0, *, duration_ms: int = 500, shape: dict = BOX,
           browser: int = BROWSER, **kwargs) -> dict:
    """A drag:object or resize:object of one object as the new UI logs it (object_ref and frame)."""
    payload = dict(shape, frame=frame, client_id=browser)
    if ref is not None:
        payload["object_ref"] = ref
    return client(scope, end, duration=duration_ms, **payload, **kwargs)


def drag(end, ref: int | None, frame: int = 0, **kwargs) -> dict:
    return adjust("drag:object", end, ref, frame, **kwargs)


def resize(end, ref: int | None, frame: int = 0, **kwargs) -> dict:
    return adjust("resize:object", end, ref, frame, **kwargs)


class ShapeSwitchTest(OperationsCase):
    def setUp(self) -> None:
        super().setUp()
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10), **BOX),  # a bounding box, 10 s
            draw(seconds(t, 20), **BOX_TRACK),  # a rectangle track: all shapes only, 10 s
            draw(seconds(t, 30), **POLYGON),  # 10 s
            # a pasted selection of three rectangles (two single-frame) and a polyline, 20 s
            client("paste:object", seconds(t, 50), count=4, shape_type="mixed", rectangle_count=2,
                   object_type="mixed"),
            client("delete:object", seconds(t, 60), count=2, shape_type="mixed", rectangle_count=1,
                   object_type="shape"),
            drag(seconds(t, 70), 5),
            drag(seconds(t, 80), 6, shape=POLYGON),
            working_time(at(t), 200_000, user=ALICE, org=ORG),
        ])

    def figures(self, **query) -> dict:
        operations = self.operations(**query)
        return {name: (row["objects"], row["timed_objects"], row["time_ms"])
                for name, row in self.by_name(operations).items()}

    def test_bounding_boxes_are_single_frame_rectangles(self):
        figures = self.figures(shapes="bounding_boxes")

        self.assertEqual(figures["creation"], (3, 3, 20_000))  # the box and half of the pasted selection
        self.assertEqual(figures["alignment"], (1, 1, 10_000))
        self.assertEqual(figures["deletion"], (1, 1, 5_000))

    def test_all_shapes_include_tracks_and_other_shapes(self):
        figures = self.figures(shapes="all")

        self.assertEqual(figures["creation"], (7, 7, 50_000))
        self.assertEqual(figures["alignment"], (2, 2, 20_000))
        self.assertEqual(figures["deletion"], (2, 2, 10_000))

    def test_other_is_the_working_time_not_spent_on_bounding_box_operations(self):
        operations = self.operations(shapes="bounding_boxes")
        other = self.by_name(operations)["other"]

        self.assertEqual(other["time_ms"], 200_000 - 35_000)
        self.assertEqual(operations["active_time_ms"], 200_000)

    def test_the_figures_say_which_shapes_they_cover(self):
        self.assertEqual(self.operations(shapes="bounding_boxes")["shapes"], "bounding_boxes")
        self.assertEqual(self.operations(shapes="all")["shapes"], "all")

    def test_without_a_switch_the_service_reports_all_shapes(self):
        operations = self.operations()

        self.assertEqual(operations["shapes"], "all")
        self.assertEqual(self.by_name(operations)["creation"]["objects"], 7)

    def test_an_unknown_switch_value_is_refused(self):
        self.stack.keep_refreshing_since(at("2026-11-05 00:00:00"))
        status, body = self.stack.overview("lead", org="org7", shapes="boxes")

        self.assertEqual(status, 400, body)
        self.assertEqual(body["error"], "bad_request")


class LegacyShapesTest(OperationsCase):
    def test_a_legacy_period_shows_all_shapes_even_when_bounding_boxes_are_asked_for(self):
        self.stack.add_events([
            client("load:job", at("2026-11-13 10:00:00")),
            draw(at("2026-11-13 10:00:05")),
            draw(at("2026-11-13 10:00:10")),
        ])

        operations = self.operations(shapes="bounding_boxes")

        self.assertTrue(operations["legacy"])
        self.assertEqual(operations["shapes"], "all")
        self.assertEqual(self.by_name(operations)["creation"]["objects"], 2)

    def test_a_period_with_only_other_shapes_is_not_legacy_and_has_no_bounding_boxes(self):
        self.stack.add_events([
            client("load:job", at("2026-11-13 10:00:00")),
            draw(at("2026-11-13 10:00:05"), **POLYGON),
        ])

        operations = self.operations(shapes="bounding_boxes")

        self.assertFalse(operations["legacy"])
        self.assertEqual(operations["shapes"], "bounding_boxes")
        self.assertEqual(self.by_name(operations)["creation"]["objects"], 0)


class AlignmentTest(OperationsCase):
    t = "2026-11-13 10:00:00"

    def alignments(self, **query) -> tuple[int, int, int]:
        row = self.by_name(self.operations(shapes="all", **query))["alignment"]
        return row["objects"], row["timed_objects"], row["time_ms"]

    def test_three_drags_on_a_box_another_box_then_the_first_again_are_three_alignments(self):
        t = self.t
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            drag(seconds(t, 5), 1),
            resize(seconds(t, 10), 1),
            drag(seconds(t, 15), 1),
            drag(seconds(t, 20), 2),
            drag(seconds(t, 25), 1),
        ])

        self.assertEqual(self.alignments(), (3, 3, 25_000))

    def test_a_frame_change_ends_an_alignment(self):
        t = self.t
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            drag(seconds(t, 5), 1, frame=0),
            client("change:frame", seconds(t, 7), count=1, **{"from": 0, "to": 1, "step": 1}),
            drag(seconds(t, 10), 1, frame=1),
        ])

        self.assertEqual(self.alignments()[0], 2)

    def test_an_operation_on_another_object_ends_an_alignment(self):
        t = self.t
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            drag(seconds(t, 5), 1),
            draw(seconds(t, 8), seconds=1, **BOX),
            drag(seconds(t, 10), 1),
        ])

        self.assertEqual(self.alignments()[0], 2)

    def test_a_redo_of_a_creation_ends_an_alignment(self):
        t = self.t
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            drag(seconds(t, 5), 1),
            client("action:redo", seconds(t, 8), count=1, name="Created objects", frame=0),
            drag(seconds(t, 10), 1),
        ])

        # 5 s to the first drag and 2 s from the redo to the second; the 3 s before the redo are no alignment's
        self.assertEqual(self.alignments(), (2, 2, 7_000))

    def test_zooming_between_drags_of_the_same_box_does_not_end_the_alignment(self):
        t = self.t
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            drag(seconds(t, 5), 1),
            client("zoom:image", seconds(t, 7), count=1),
            drag(seconds(t, 10), 1),
        ])

        self.assertEqual(self.alignments()[0], 1)

    def test_the_time_of_an_alignment_runs_from_the_action_before_its_first_drag_to_its_last(self):
        t = self.t
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            drag(seconds(t, 10), 1, duration_ms=2_000),
            client("zoom:image", seconds(t, 14), count=1),
            resize(seconds(t, 30), 1, duration_ms=3_000),
            # after the alignment: Other
            client("zoom:image", seconds(t, 45), count=1),
        ])

        self.assertEqual(self.alignments(), (1, 1, 30_000))

    def test_the_same_reference_in_another_browser_or_job_is_another_object(self):
        t = self.t
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            drag(seconds(t, 5), 1),
            drag(seconds(t, 10), 1, browser=999),
            drag(seconds(t, 15), 1, job=2),
        ])

        self.assertEqual(self.alignments()[0], 3)

    def test_two_people_adjusting_at_the_same_time_each_have_their_own_alignments(self):
        t = self.t
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            client("load:job", seconds(t, 0), user=BOB),
            drag(seconds(t, 5), 1),
            drag(seconds(t, 6), 3, user=BOB),
            drag(seconds(t, 10), 1),
            drag(seconds(t, 11), 3, user=BOB),
        ])

        self.assertEqual(self.alignments()[0], 2)
        self.assertEqual(self.alignments(annotator="11")[0], 1)

    def test_legacy_drags_and_resizes_each_count_as_one_alignment(self):
        t = self.t
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            client("drag:object", seconds(t, 5), duration=500, obj_id=40),
            client("drag:object", seconds(t, 10), duration=500, obj_id=40),
            client("resize:object", seconds(t, 15), duration=500, obj_id=40),
        ])

        self.assertEqual(self.alignments(), (3, 3, 15_000))

    def test_a_pause_longer_than_the_session_gap_ends_an_alignment(self):
        t = self.t
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            drag(seconds(t, 5), 1),
            drag(seconds(t, 400), 1),
        ])

        self.assertEqual(self.alignments()[0], 2)

    def test_an_alignment_of_a_bounding_box_counts_under_bounding_boxes_only_for_a_box(self):
        t = self.t
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            drag(seconds(t, 5), 1),
            drag(seconds(t, 10), 1),
            drag(seconds(t, 15), 2, shape=BOX_TRACK),
        ])

        row = self.by_name(self.operations(shapes="bounding_boxes"))["alignment"]
        self.assertEqual((row["objects"], row["time_ms"]), (1, 10_000))


def group_move(end, objects: int, *, rectangles: int | None = None, duration_ms: int = 500,
               shape_type: str = "rectangle", grabbed: int | None = 1, frame: int = 0,
               browser: int = BROWSER) -> list[dict]:
    """A group move as the new UI logs it: one drag:object for the gesture with the objects moved in
    its count, then, when the gesture began on an object, CVAT's own drag of that object marked as
    grabbed, 1 ms later. `grabbed=None` is a move of the selection box (no grabbed object)."""
    events = [client("drag:object", end, count=objects, duration=duration_ms, group="move",
                     shape_type=shape_type, object_type="shape",
                     rectangle_count=objects if rectangles is None else rectangles,
                     frame=frame, input_method="mouse", client_id=browser)]
    if grabbed is not None:
        events.append(adjust("drag:object", end + timedelta(milliseconds=1), grabbed, frame,
                             duration_ms=duration_ms, browser=browser, group="grabbed",
                             input_method="mouse"))
    return events


class GroupMoveTest(OperationsCase):
    """A group move is one alignment for each object moved, sharing the gesture's time equally.

    The gesture takes 5 s and begins 1 s after the job was opened: its time is the 6 s since then.
    """

    t = "2026-11-13 10:00:00"

    def alignment(self, shapes: str = "all") -> dict:
        return self.by_name(self.operations(shapes=shapes))["alignment"]

    def test_a_group_drag_of_three_boxes_over_six_seconds_is_three_alignments_of_two_seconds(self):
        t = self.t
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            *group_move(seconds(t, 6), 3, duration_ms=5_000),
        ])

        row = self.alignment()
        self.assertEqual((row["objects"], row["timed_objects"], row["time_ms"]), (3, 3, 6_000))
        self.assertEqual(row["average_ms"], 2_000)
        self.assertEqual(row["mouse_objects"], 3)

    def test_the_grabbed_drag_at_the_same_millisecond_is_not_counted_again(self):
        t = self.t
        group, grabbed = group_move(seconds(t, 6), 3, duration_ms=5_000)
        grabbed["timestamp"] = group["timestamp"]
        self.stack.add_events([client("load:job", seconds(t, 0)), group, grabbed])

        row = self.alignment()
        self.assertEqual((row["objects"], row["timed_objects"], row["time_ms"]), (3, 3, 6_000))

    def test_moving_the_selection_box_counts_the_same_way(self):
        t = self.t
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            *group_move(seconds(t, 6), 3, duration_ms=5_000, grabbed=None),
        ])

        row = self.alignment()
        self.assertEqual((row["objects"], row["timed_objects"], row["time_ms"]), (3, 3, 6_000))

    def test_a_group_of_boxes_and_other_shapes_counts_only_its_boxes_under_bounding_boxes(self):
        t = self.t
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            *group_move(seconds(t, 6), 3, rectangles=2, shape_type="mixed", duration_ms=5_000),
        ])

        boxes = self.alignment(shapes="bounding_boxes")
        self.assertEqual((boxes["objects"], boxes["time_ms"]), (2, 4_000))
        everything = self.alignment()
        self.assertEqual((everything["objects"], everything["time_ms"]), (3, 6_000))

    def test_a_drag_a_group_move_including_the_box_and_another_drag_are_three_alignments_of_it(self):
        t = self.t
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            drag(seconds(t, 5), 1),
            # boxes 1 and 2 moved together, box 1 grabbed
            *group_move(seconds(t, 10), 2, duration_ms=2_000, grabbed=1),
            drag(seconds(t, 15), 1),
        ])

        # three alignments of box 1 and one of box 2; only the 1 ms after the group event is no alignment's
        row = self.alignment()
        self.assertEqual((row["objects"], row["timed_objects"], row["time_ms"]), (4, 4, 14_999))


class AlignmentWindowTest(OperationsCase):
    """An alignment that crosses the edge of a refresh window is counted once, in the window of its end."""

    stack_options = {"refresh_window_hours": 1}

    def test_an_alignment_across_a_window_edge_is_counted_once(self):
        self.stack.add_events([
            client("load:job", at("2026-11-13 09:59:40")),
            drag(at("2026-11-13 09:59:50"), 1),
            drag(at("2026-11-13 10:00:05"), 1),
            drag(at("2026-11-13 10:00:20"), 1),
        ])
        self.stack.refresh(at("2026-11-13 09:20:00"))  # window 09:00 .. 10:00
        self.stack.refresh(at("2026-11-13 10:20:00"))  # window 10:00 .. 11:00
        # the history step computes today's hours up to 10:00, so the period is processed (the edge stays)
        self.stack.settle()

        status, body = self.stack.overview("lead", org="org7", shapes="all")
        self.assertEqual(status, 200, body)
        row = self.by_name(body["operations"])["alignment"]
        self.assertEqual((row["objects"], row["time_ms"]), (1, 40_000))
