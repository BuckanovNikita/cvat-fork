"""Operations and time per operation, all shapes, from the events the stock UI writes."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from tests.support import FakeUser, StackTestCase, at, working_time

ORG = 7
ALICE = (11, "alice")
BOB = (12, "bob")


def client(scope: str, when: datetime, *, user: tuple[int, str] = ALICE, org: int | None = ORG,
           project: int | None = 1, task: int | None = 1, job: int | None = 1, count: int | None = None,
           duration: int = 0, obj_name: str | None = None, obj_id: int | None = None, **payload) -> dict:
    """A client event as the stock UI logs it through the job logger (payload JSON with spaces)."""
    body = {"client_id": 1234567890, "is_active": True, **payload}
    return {
        "scope": scope, "source": "client", "timestamp": when, "count": count, "duration": duration,
        "obj_name": obj_name, "obj_id": obj_id,
        "project_id": project, "task_id": task, "job_id": job,
        "user_id": user[0], "user_name": user[1], "user_email": f"{user[1]}@example.com",
        "org_id": org, "org_slug": None if org is None else f"org{org}",
        "payload": json.dumps(body),
    }


def draw(end: datetime, seconds: float = 2, **kwargs) -> dict:
    """draw:object is logged when drawing ends; duration is how long the drawing took."""
    return client("draw:object", end, count=1, duration=int(seconds * 1000), **kwargs)


def seconds(text: str, offset: float) -> datetime:
    return at(text) + timedelta(seconds=offset)


class OperationsCase(StackTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.callers.add_user("lead", FakeUser(2, "lead", memberships={"org7": (ORG, "maintainer", True)}))

    def operations(self, **query) -> dict:
        self.stack.keep_refreshing_since(at("2026-11-05 00:00:00"))
        status, body = self.stack.overview("lead", org="org7", **query)
        self.assertEqual(status, 200, body)
        return body["operations"]

    @staticmethod
    def by_name(operations: dict) -> dict:
        return {row["operation"]: row for row in operations["rows"]}


class CountingTest(OperationsCase):
    def test_counts_objects_drawn_pasted_propagated_deleted_and_each_drag_or_resize(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10)),
            client("paste:object", seconds(t, 20), count=3),
            client("propagate:object", seconds(t, 30), count=4),
            client("drag:object", seconds(t, 40), duration=500, obj_id=5),
            client("resize:object", seconds(t, 50), duration=500, obj_id=5),
            client("delete:object", seconds(t, 60), count=2),
            client("delete:object", seconds(t, 70), count=1),
            # zoom and frame changes are no operation
            client("zoom:image", seconds(t, 80), count=1),
        ])

        ops = self.by_name(self.operations())

        self.assertEqual([ops[name]["objects"] for name in ("creation", "alignment", "class_change", "deletion")],
                         [8, 2, 0, 3])

    def test_a_creation_undone_and_redone_is_one_creation_and_no_deletion(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10)),
            client("action:undo", seconds(t, 15), count=1, name="Created objects", frame=0),
            client("action:redo", seconds(t, 20), count=1, name="Created objects", frame=0),
            # undoing and redoing something else is no operation
            client("action:undo", seconds(t, 25), count=1, name="Changed lock", frame=0),
            client("action:redo", seconds(t, 26), count=1, name="Changed lock", frame=0),
        ])

        ops = self.by_name(self.operations())

        self.assertEqual(ops["creation"]["objects"], 1)
        self.assertEqual(ops["deletion"]["objects"], 0)
        self.assertEqual(ops["alignment"]["objects"], 0)

    def test_an_undone_creation_still_counts(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10)),
            client("action:undo", seconds(t, 15), count=1, name="Created objects", frame=0),
        ])

        ops = self.by_name(self.operations())

        self.assertEqual((ops["creation"]["objects"], ops["creation"]["time_ms"]), (1, 10_000))
        self.assertEqual(ops["deletion"]["objects"], 0)


class TimePerOperationTest(OperationsCase):
    def test_time_runs_from_the_previous_action_to_the_end_of_the_operation(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            # 8 s finding and deciding, then 4 s of drawing: 12 s
            draw(seconds(t, 12), seconds=4),
            client("zoom:image", seconds(t, 20), count=1),
            # 6 s after the zoom
            draw(seconds(t, 26), seconds=1),
            client("delete:object", seconds(t, 30), count=2),
        ])

        ops = self.by_name(self.operations())

        self.assertEqual(ops["creation"]["time_ms"], 18_000)
        self.assertEqual(ops["creation"]["average_ms"], 9_000)
        # two objects deleted in 4 s: 2 s per object
        self.assertEqual(ops["deletion"]["time_ms"], 4_000)
        self.assertEqual(ops["deletion"]["average_ms"], 2_000)

    def test_a_pause_over_100_seconds_is_dropped_and_its_action_left_out_of_the_average(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10)),
            # 100.5 s of nothing: an idle pause
            draw(seconds(t, 110.5)),
            # exactly 100 s is still a measured gap
            draw(seconds(t, 210.5)),
        ])

        creation = self.by_name(self.operations())["creation"]

        self.assertEqual(creation["objects"], 3)
        self.assertEqual(creation["timed_objects"], 2)
        self.assertEqual(creation["time_ms"], 110_000)
        self.assertEqual(creation["average_ms"], 55_000)

    def test_navigation_while_drawing_gives_its_time_to_the_drawing(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            client("zoom:image", seconds(t, 5), count=1),
            # drawing started at 6 s; the zoom and the frame change happen while drawing
            client("zoom:image", seconds(t, 8), count=1),
            client("change:frame", seconds(t, 9), count=1, duration=300, **{"from": 0, "to": 1, "step": 1}),
            draw(seconds(t, 12), seconds=6),
            # an alignment covers its drag in the same way
            client("zoom:image", seconds(t, 14), count=1),
            client("drag:object", seconds(t, 16), duration=3000, obj_id=1),
        ])

        ops = self.by_name(self.operations())

        # from the zoom at 5 s, the action before the drawing, to its end at 12 s
        self.assertEqual(ops["creation"]["time_ms"], 7_000)
        self.assertEqual(ops["alignment"]["time_ms"], 4_000)

    def test_the_previous_action_may_lie_outside_a_job(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            # back on the task page, then into the job again
            client("click:element", seconds(t, 200), project=None, task=None, job=None),
            draw(seconds(t, 210)),
        ])

        creation = self.by_name(self.operations())["creation"]

        self.assertEqual((creation["objects"], creation["timed_objects"], creation["time_ms"]), (1, 1, 10_000))

    def test_an_operation_at_the_start_of_a_refresh_window_counts_its_time_once(self):
        # the refresh window starts on a whole hour; the previous action lies before it
        self.stack.add_events([
            client("load:job", at("2026-11-13 09:59:50")),
            draw(at("2026-11-13 10:00:05")),
        ])
        self.stack.keep_refreshing_since(at("2026-11-05 00:00:00"))
        # history up to the 14th first, so the week is processed; the refresh below then writes the hours read
        self.stack.now = at("2026-11-15 09:20:00")
        self.stack.settle()
        self.stack.refresh(at("2026-11-15 09:20:00"))  # window 2026-11-13 10:00 .. 2026-11-15 10:00

        status, body = self.stack.overview("lead", org="org7")
        self.assertEqual(status, 200, body)
        creation = self.by_name(body["operations"])["creation"]
        self.assertEqual((creation["objects"], creation["time_ms"]), (1, 15_000))


class OtherTest(OperationsCase):
    def batch_across_a_project_switch_and_an_hour_boundary(self, working_time_at: datetime) -> None:
        # One batch: work in project 1 until 10:59:50, then project 2 from 11:00:10. The server credits
        # the whole batch's working time to the first event's job and hour; the operations go to the
        # project and hour where they ended.
        self.stack.add_events([
            client("load:job", at("2026-11-13 10:59:00")),
            draw(at("2026-11-13 10:59:30")),
            client("load:job", at("2026-11-13 10:59:50"), project=2, task=2, job=2),
            draw(at("2026-11-13 11:00:10"), project=2, task=2, job=2),
            client("delete:object", at("2026-11-13 11:00:40"), count=1, project=2, task=2, job=2),
            working_time(working_time_at, 100_000, user=ALICE, org=ORG),
        ])

    def test_other_is_working_time_not_spent_on_an_operation(self):
        self.batch_across_a_project_switch_and_an_hour_boundary(at("2026-11-13 10:59:00"))

        operations = self.operations()
        ops = self.by_name(operations)

        # creation 30 s + 20 s, deletion 30 s; working time 100 s
        self.assertEqual(ops["creation"]["time_ms"], 50_000)
        self.assertEqual(ops["deletion"]["time_ms"], 30_000)
        self.assertEqual(ops["other"]["time_ms"], 20_000)
        self.assertEqual(operations["working_time_ms"], 100_000)
        self.assertEqual(operations["active_time_ms"], 100_000)
        self.assertEqual([ops[name]["share"] for name in ("creation", "alignment", "class_change", "deletion", "other")],
                         [0.5, 0, 0, 0.3, 0.2])

    def test_other_never_goes_below_zero(self):
        # the batch's working time is stamped before the period, so the period holds operations only
        self.batch_across_a_project_switch_and_an_hour_boundary(at("2026-11-06 23:59:00"))

        operations = self.operations()
        ops = self.by_name(operations)

        self.assertEqual(ops["other"]["time_ms"], 0)
        self.assertEqual(operations["working_time_ms"], 0)
        self.assertEqual(operations["active_time_ms"], 80_000)
        self.assertAlmostEqual(sum(row["share"] for row in operations["rows"]), 1.0)

    def test_with_a_redo_the_shares_still_add_up_and_other_is_not_below_zero(self):
        # no working time in the period: the operations are all of the active time
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10)),  # 10 s
            client("action:undo", seconds(t, 15), count=1, name="Created objects", frame=0),
            client("action:redo", seconds(t, 20), count=1, name="Created objects", frame=0),
            client("delete:object", seconds(t, 24), count=1),  # 4 s since the redo
        ])

        operations = self.operations()
        ops = self.by_name(operations)

        self.assertEqual(ops["other"]["time_ms"], 0)
        self.assertEqual(operations["working_time_ms"], 0)
        self.assertEqual(operations["active_time_ms"], 14_000)
        self.assertAlmostEqual(sum(row["share"] for row in operations["rows"]), 1.0)

    def test_other_is_computed_for_the_filtered_project_and_never_below_zero(self):
        # the batch's 100 s of working time is credited to project 1, where it started
        self.batch_across_a_project_switch_and_an_hour_boundary(at("2026-11-13 10:59:00"))

        first = self.operations(project="1")
        # project 1: creation 30 s, the rest of the 100 s is Other
        self.assertEqual((self.by_name(first)["creation"]["time_ms"], self.by_name(first)["other"]["time_ms"]),
                         (30_000, 70_000))
        self.assertEqual(first["working_time_ms"], 100_000)

        second = self.operations(project="2")
        ops = self.by_name(second)
        # project 2: creation 20 s and deletion 30 s, with no working time of its own
        self.assertEqual((ops["creation"]["time_ms"], ops["deletion"]["time_ms"], ops["other"]["time_ms"]),
                         (20_000, 30_000, 0))
        self.assertEqual(second["active_time_ms"], 50_000)
        self.assertAlmostEqual(sum(row["share"] for row in second["rows"]), 1.0)


class PeriodAndScopeTest(OperationsCase):
    stack_options = {"technical_accounts": ("importer",)}

    def test_figures_cover_the_period_and_the_organization_only(self):
        self.stack.add_events([
            client("load:job", at("2026-11-06 23:59:50")),
            draw(at("2026-11-06 23:59:55")),  # before the week (from 2026-11-07 00:00 UTC)
            draw(at("2026-11-07 00:00:05")),
            client("load:job", at("2026-11-13 10:00:00"), org=8),
            draw(at("2026-11-13 10:00:05"), org=8),  # another organization
            client("load:job", at("2026-11-13 11:00:00"), user=(99, "importer")),
            draw(at("2026-11-13 11:00:05"), user=(99, "importer")),  # a technical account
            client("load:job", at("2026-11-13 12:00:00"), job=None),
            client("delete:object", at("2026-11-13 12:00:05"), count=1, job=None),  # outside a job
        ])

        ops = self.by_name(self.operations())

        self.assertEqual((ops["creation"]["objects"], ops["creation"]["time_ms"]), (1, 10_000))
        self.assertEqual(ops["deletion"]["objects"], 0)

    def test_a_month_holds_only_its_own_operations_and_working_time(self):
        self.stack.add_events([
            client("load:job", at("2026-10-31 23:59:50")),
            draw(at("2026-10-31 23:59:58")),  # October in UTC
            draw(at("2026-11-01 00:00:04")),  # November
            working_time(at("2026-10-31 23:59:50"), 8_000, user=ALICE, org=ORG),
        ])
        self.stack.keep_refreshing_since(at("2026-10-29 00:00:00"))

        def creation_and_other(month: str) -> tuple:
            status, body = self.stack.overview("lead", org="org7", period="month", month=month)
            self.assertEqual(status, 200, body)
            ops = self.by_name(body["operations"])
            return ops["creation"]["objects"], ops["creation"]["time_ms"], ops["other"]["time_ms"]

        self.assertEqual(creation_and_other("2026-10"), (1, 8_000, 0))
        # November has the second drawing but no working time: Other stays at zero
        self.assertEqual(creation_and_other("2026-11"), (1, 6_000, 0))


class LegacyPeriodTest(OperationsCase):
    def test_a_period_without_shape_tagged_events_is_a_legacy_period(self):
        self.stack.add_events([client("load:job", at("2026-11-13 10:00:00")), draw(at("2026-11-13 10:00:05"))])

        self.assertTrue(self.operations()["legacy"])

    def test_one_shape_tagged_event_ends_the_legacy_period(self):
        self.stack.add_events([
            client("load:job", at("2026-11-13 10:00:00")),
            draw(at("2026-11-13 10:00:05"), shape_type="polygon", rectangle_count=0, object_type="shape",
                 input_method="mouse"),
        ])

        operations = self.operations()

        self.assertFalse(operations["legacy"])
        self.assertEqual(self.by_name(operations)["creation"]["objects"], 1)

    def test_a_period_with_no_job_work_is_not_a_legacy_period(self):
        self.assertFalse(self.operations()["legacy"])

    def test_working_time_without_shape_tagged_events_is_a_legacy_period(self):
        self.stack.add_events([working_time(at("2026-11-13 10:00:00"), 60_000, user=ALICE, org=ORG)])

        self.assertTrue(self.operations()["legacy"])

    def test_a_filter_that_leaves_no_job_work_is_not_a_legacy_period(self):
        self.stack.add_events([
            client("load:job", at("2026-11-13 10:00:00")),
            draw(at("2026-11-13 10:00:05")),
            working_time(at("2026-11-13 10:00:00"), 60_000, user=ALICE, org=ORG),
        ])

        self.assertTrue(self.operations()["legacy"])
        self.assertFalse(self.operations(project="2")["legacy"])


class FiltersTest(OperationsCase):
    """The operations figures follow the project and annotator filters, Other included."""

    def setUp(self) -> None:
        super().setUp()
        self.stack.add_events([
            # alice in project 1: a drawing (10 s) and a deletion (4 s); 60 s of working time
            client("load:job", at("2026-11-13 10:00:00")),
            draw(at("2026-11-13 10:00:10")),
            client("delete:object", at("2026-11-13 10:00:14"), count=1),
            working_time(at("2026-11-13 10:00:00"), 60_000, user=ALICE, org=ORG, project=1, task=1, job=1),
            # alice in project 2: a drawing (20 s); 100 s of working time
            client("load:job", at("2026-11-13 10:30:00"), project=2, task=2, job=2),
            draw(at("2026-11-13 10:30:20"), project=2, task=2, job=2),
            working_time(at("2026-11-13 10:30:00"), 100_000, user=ALICE, org=ORG, project=2, task=2, job=2),
            # bob in project 1: a drawing (30 s); 50 s of working time
            client("load:job", at("2026-11-13 11:00:00"), user=BOB, job=3),
            draw(at("2026-11-13 11:00:30"), user=BOB, job=3),
            working_time(at("2026-11-13 11:00:00"), 50_000, user=BOB, org=ORG, project=1, task=1, job=3),
        ])

    def figures(self, **query) -> tuple:
        operations = self.operations(**query)
        ops = self.by_name(operations)
        return (ops["creation"]["objects"], ops["creation"]["time_ms"], ops["deletion"]["objects"],
                ops["deletion"]["time_ms"], ops["other"]["time_ms"], operations["working_time_ms"])

    def test_no_filter_covers_the_whole_scope(self):
        self.assertEqual(self.figures(), (3, 60_000, 1, 4_000, 146_000, 210_000))

    def test_a_project_filter_keeps_that_projects_operations_and_working_time(self):
        self.assertEqual(self.figures(project="1"), (2, 40_000, 1, 4_000, 66_000, 110_000))

    def test_an_annotator_filter_keeps_that_persons_operations_and_working_time(self):
        self.assertEqual(self.figures(annotator="11"), (2, 30_000, 1, 4_000, 126_000, 160_000))

    def test_both_filters_keep_that_persons_work_in_that_project(self):
        self.assertEqual(self.figures(project="1", annotator="11"), (1, 10_000, 1, 4_000, 46_000, 60_000))
