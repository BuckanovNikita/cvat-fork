"""Keyboard and mouse: hotkey actions, mouse actions, hotkey share, the most used hotkeys, and how each
operation was started, from the input summary records and the input_method field the UI logs."""

from __future__ import annotations

from datetime import datetime

from tests.support import FakeUser, StackTestCase, at, working_time
from tests.test_operations import ALICE, BOB, ORG, client, draw, seconds

SUMMARY = "team_analytics:input_summary"


def summary(when: datetime, hotkeys: dict | None = None, mouse: dict | None = None, **kwargs) -> dict:
    """The input summary record the UI writes through the job logger (a debug:info event)."""
    return client("debug:info", when, obj_name=SUMMARY, hotkeys=hotkeys or {}, mouse=mouse or {}, **kwargs)


class KeyboardMouseCase(StackTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.callers.add_user("lead", FakeUser(2, "lead", memberships={"org7": (ORG, "maintainer", True)}))

    def overview(self, **query) -> dict:
        self.stack.keep_refreshing_since(at("2026-11-05 00:00:00"))
        status, body = self.stack.overview("lead", org="org7", **query)
        self.assertEqual(status, 200, body)
        return body

    def input(self, **query) -> dict:
        return self.overview(**query)["input"]


class InputFiguresTest(KeyboardMouseCase):
    def test_hotkey_and_mouse_actions_add_up_over_summaries_and_the_canvas_is_counted_apart(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            summary(seconds(t, 60), {"NEXT_FRAME": 12, "SWITCH_DRAW_MODE_STANDARD_CONTROLS": 3},
                    {"objects_sidebar": 2, "canvas": 30}),
            summary(seconds(t, 130), {"NEXT_FRAME": 5}, {"header": 3, "popup": 1, "canvas": 4}),
        ])

        figures = self.input()

        self.assertEqual(figures["hotkey_actions"], 20)
        self.assertEqual(figures["mouse_actions"], 6)
        self.assertEqual(figures["canvas_clicks"], 34)
        self.assertAlmostEqual(figures["hotkey_share"], 20 / 26)

    def test_no_input_recorded_has_no_share(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([client("load:job", seconds(t, 0)), draw(seconds(t, 10), input_method="mouse")])

        figures = self.input()

        self.assertEqual((figures["hotkey_actions"], figures["mouse_actions"]), (0, 0))
        self.assertIsNone(figures["hotkey_share"])
        self.assertEqual(figures["top_hotkeys"], [])
        self.assertEqual(figures["rest"], {"count": 0, "actions": 0})

    def test_the_seven_most_used_hotkeys_by_action_and_one_line_for_the_rest(self):
        t = "2026-11-13 10:00:00"
        used = {f"ACTION_{n}": n for n in range(1, 11)}  # ACTION_10 used 10 times ... ACTION_1 once
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            summary(seconds(t, 60), used),
            # the same action from another summary groups with it
            summary(seconds(t, 120), {"ACTION_1": 20}),
        ])

        figures = self.input()

        self.assertEqual(figures["top_hotkeys"], [
            {"action": "ACTION_1", "actions": 21},
            {"action": "ACTION_10", "actions": 10},
            {"action": "ACTION_9", "actions": 9},
            {"action": "ACTION_8", "actions": 8},
            {"action": "ACTION_7", "actions": 7},
            {"action": "ACTION_6", "actions": 6},
            {"action": "ACTION_5", "actions": 5},
        ])
        self.assertEqual(figures["rest"], {"count": 3, "actions": 4 + 3 + 2})
        self.assertEqual(figures["hotkey_actions"], 21 + 54)

    def test_only_summary_records_inside_a_job_count(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            summary(seconds(t, 60), {"NEXT_FRAME": 2}, {"header": 1}),
            summary(seconds(t, 70), {"NEXT_FRAME": 100}, {"header": 100}, job=None, task=None, project=None),
            # another debug record with the same payload keys is not a summary
            client("debug:info", seconds(t, 80), obj_name="chunk_download_bandwidth", hotkeys={"NEXT_FRAME": 50}),
        ])

        figures = self.input()

        self.assertEqual((figures["hotkey_actions"], figures["mouse_actions"]), (2, 1))


class ScopeTest(KeyboardMouseCase):
    stack_options = {"technical_accounts": ("robot",)}

    def test_filters_by_project_and_annotator_and_technical_accounts_are_left_out(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            summary(seconds(t, 60), {"NEXT_FRAME": 4}, {"header": 1}, project=1),
            summary(seconds(t, 70), {"NEXT_FRAME": 8}, {"header": 2}, project=2, task=2, job=2),
            client("load:job", seconds(t, 0), user=BOB),
            summary(seconds(t, 60), {"UNDO": 16}, {"header": 4}, user=BOB),
            summary(seconds(t, 60), {"UNDO": 1000}, {"header": 1000}, user=(99, "robot")),
            # another organization
            summary(seconds(t, 60), {"UNDO": 500}, {"header": 500}, org=8),
        ])

        self.assertEqual(self.input()["hotkey_actions"], 28)
        self.assertEqual(self.input(project=2)["hotkey_actions"], 8)
        self.assertEqual(self.input(annotator=BOB[0])["mouse_actions"], 4)
        self.assertEqual(self.input(project=1, annotator=ALICE[0])["top_hotkeys"],
                         [{"action": "NEXT_FRAME", "actions": 4}])


class InputMethodTest(KeyboardMouseCase):
    def test_creation_class_change_and_deletion_split_by_the_method_that_started_them(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10), input_method="hotkey", shape_type="rectangle", object_type="shape",
                 rectangle_count=1),
            draw(seconds(t, 20), input_method="mouse", shape_type="rectangle", object_type="shape",
                 rectangle_count=1),
            client("paste:object", seconds(t, 30), count=3, input_method="hotkey", shape_type="rectangle",
                   object_type="shape", rectangle_count=3),
            client("debug:info", seconds(t, 40), obj_name="team_analytics:class_change", count=2,
                   input_method="hotkey", shape_type="rectangle", object_type="shape", rectangle_count=2),
            client("delete:object", seconds(t, 50), count=4, input_method="mouse", shape_type="rectangle",
                   object_type="shape", rectangle_count=4),
            client("drag:object", seconds(t, 60), duration=300, input_method="mouse", shape_type="rectangle",
                   object_type="shape", rectangle_count=1, object_ref=1, frame=0),
            # a legacy event has no input method: it is in neither part of the split
            client("delete:object", seconds(t, 70), count=1),
        ])

        rows = {row["operation"]: row for row in self.overview(shapes="all")["operations"]["rows"]}

        self.assertEqual((rows["creation"]["hotkey_objects"], rows["creation"]["mouse_objects"]), (4, 1))
        self.assertEqual((rows["class_change"]["hotkey_objects"], rows["class_change"]["mouse_objects"]), (2, 0))
        self.assertEqual((rows["deletion"]["hotkey_objects"], rows["deletion"]["mouse_objects"]), (0, 4))
        self.assertEqual(rows["deletion"]["objects"], 5)
        self.assertEqual((rows["alignment"]["hotkey_objects"], rows["alignment"]["mouse_objects"]), (0, 1))
        self.assertEqual((rows["other"]["hotkey_objects"], rows["other"]["mouse_objects"]), (0, 0))

    def test_the_split_follows_the_shape_switch(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            client("paste:object", seconds(t, 10), count=3, input_method="hotkey", shape_type="mixed",
                   object_type="shape", rectangle_count=1),
        ])

        boxes = self.overview(shapes="bounding_boxes")["operations"]["rows"][0]
        every = self.overview(shapes="all")["operations"]["rows"][0]

        self.assertEqual((boxes["objects"], boxes["hotkey_objects"]), (1, 1))
        self.assertEqual((every["objects"], every["hotkey_objects"]), (3, 3))

    def test_a_summary_written_just_before_an_operation_does_not_take_its_time(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            # the click that deletes is an active moment: the summary is logged just before the deletion
            summary(seconds(t, 9.99), {"NEXT_FRAME": 1}, {"objects_sidebar": 1}),
            client("delete:object", seconds(t, 10), count=1, input_method="mouse", shape_type="rectangle",
                   object_type="shape", rectangle_count=1),
            working_time(seconds(t, 10), 10_000, user=ALICE, org=ORG),
        ])

        deletion = self.overview()["operations"]["rows"][3]

        self.assertEqual(deletion["operation"], "deletion")
        self.assertEqual(deletion["time_ms"], 10_000)
