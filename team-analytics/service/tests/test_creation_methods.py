"""Creation methods: drawn, pasted and propagated objects counted on their own, each with its average time."""

from __future__ import annotations

from tests.support import at, working_time
from tests.test_operations import ALICE, BOB, ORG, OperationsCase, client, draw, seconds

BOX = {"shape_type": "rectangle", "rectangle_count": 1, "object_type": "shape"}
POLYGON = {"shape_type": "polygon", "rectangle_count": 0, "object_type": "shape"}


def paste(end, count: int = 1, **kwargs) -> dict:
    return client("paste:object", end, count=count, **kwargs)


def propagate(end, count: int = 1, **kwargs) -> dict:
    return client("propagate:object", end, count=count, **kwargs)


def undo(end, **kwargs) -> dict:
    return client("action:undo", end, count=1, name="Created objects", frame=0, **kwargs)


def redo(end, **kwargs) -> dict:
    return client("action:redo", end, count=1, name="Created objects", frame=0, **kwargs)


class MethodsCase(OperationsCase):
    def overview(self, **query) -> dict:
        self.stack.keep_refreshing_since(at("2026-11-05 00:00:00"))
        status, body = self.stack.overview("lead", org="org7", **query)
        self.assertEqual(status, 200, body)
        return body

    def methods(self, **query) -> dict:
        return self.figures(self.overview(**query))

    @staticmethod
    def figures(body: dict) -> dict:
        return {row["method"]: (row["objects"], row["timed_objects"], row["time_ms"], row["average_ms"])
                for row in body["creation_methods"]["rows"]}

    def assertMethodsAddUpToCreation(self, body: dict) -> None:
        creation = self.by_name(body["operations"])["creation"]
        rows = body["creation_methods"]["rows"]
        total = body["creation_methods"]["total"]
        for key in ("objects", "timed_objects", "time_ms"):
            self.assertEqual(sum(row[key] for row in rows), creation[key], key)
            self.assertEqual(total[key], creation[key], key)
        self.assertEqual(total["average_ms"], creation["average_ms"])


class CountsAndTimesTest(MethodsCase):
    def setUp(self) -> None:
        super().setUp()
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10)),  # 10 s
            draw(seconds(t, 16)),  # 6 s
            paste(seconds(t, 20), count=2),  # 4 s for two objects
            propagate(seconds(t, 30), count=4),  # 10 s for four objects
            # an idle pause: counted, left out of the average
            paste(seconds(t, 200)),
        ])

    def test_drawn_pasted_and_propagated_are_counted_separately_each_with_its_average_time(self):
        self.assertEqual(self.methods(), {
            "drawn": (2, 2, 16_000, 8_000),
            "pasted": (3, 2, 4_000, 2_000),
            "propagated": (4, 4, 10_000, 2_500),
        })

    def test_the_methods_are_listed_in_a_fixed_order_with_shares_of_the_three(self):
        rows = self.overview()["creation_methods"]["rows"]

        self.assertEqual([row["method"] for row in rows], ["drawn", "pasted", "propagated"])
        self.assertEqual([row["share"] for row in rows], [2 / 9, 3 / 9, 4 / 9])

    def test_one_average_for_all_three_is_the_average_of_the_creation_operation(self):
        body = self.overview()

        self.assertEqual(body["creation_methods"]["total"],
                         {"objects": 9, "timed_objects": 8, "time_ms": 30_000, "average_ms": 3_750})
        self.assertMethodsAddUpToCreation(body)


class EmptyTest(MethodsCase):
    def test_no_creation_gives_three_rows_of_zeros_without_averages_or_shares(self):
        rows = self.overview()["creation_methods"]["rows"]

        self.assertEqual([(row["method"], row["objects"], row["average_ms"], row["share"]) for row in rows], [
            ("drawn", 0, None, None), ("pasted", 0, None, None), ("propagated", 0, None, None)])


class RedoTest(MethodsCase):
    """A redo is no creation: it adds no object to any creation method, and its time is Other."""

    def test_draw_undo_redo_is_one_drawn_creation_and_the_redos_time_is_other(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10)),  # 10 s
            undo(seconds(t, 15)),
            redo(seconds(t, 20)),  # 5 s since the undo: no operation's time
            working_time(at(t), 100_000, user=ALICE, org=ORG),
        ])

        body = self.overview(shapes="all")

        self.assertEqual(self.figures(body), {
            "drawn": (1, 1, 10_000, 10_000),
            "pasted": (0, 0, 0, None),
            "propagated": (0, 0, 0, None),
        })
        ops = self.by_name(body["operations"])
        self.assertEqual((ops["creation"]["objects"], ops["creation"]["time_ms"]), (1, 10_000))
        self.assertEqual(ops["other"]["time_ms"], 90_000)
        self.assertEqual((ops["creation"]["share"], ops["other"]["share"]), (0.1, 0.9))
        self.assertMethodsAddUpToCreation(body)

    def test_a_redo_after_a_paste_or_a_propagation_adds_no_object_to_any_method(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 5)),  # 5 s
            paste(seconds(t, 10), count=2),  # 5 s for two objects
            undo(seconds(t, 15)),
            redo(seconds(t, 20)),
            propagate(seconds(t, 32), count=3),  # 12 s since the redo, for three objects
            undo(seconds(t, 36)),
            redo(seconds(t, 40)),
            working_time(at(t), 100_000, user=ALICE, org=ORG),
        ])

        body = self.overview(shapes="all")

        self.assertEqual(self.figures(body), {
            "drawn": (1, 1, 5_000, 5_000),
            "pasted": (2, 2, 5_000, 2_500),
            "propagated": (3, 3, 12_000, 4_000),
        })
        # the two redos' 5 s and 4 s are in Other with the rest of the working time
        self.assertEqual(self.by_name(body["operations"])["other"]["time_ms"], 78_000)
        self.assertMethodsAddUpToCreation(body)

    def test_a_redo_without_an_earlier_creation_is_no_creation(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            redo(seconds(t, 20)),
        ])

        body = self.overview(shapes="all")

        self.assertEqual({method: figures[0] for method, figures in self.figures(body).items()},
                         {"drawn": 0, "pasted": 0, "propagated": 0})
        self.assertEqual(self.by_name(body["operations"])["creation"]["objects"], 0)

    def test_a_redo_in_another_job_or_by_another_annotator_is_no_creation(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            paste(seconds(t, 10)),
            client("load:job", seconds(t, 12), job=2),
            redo(seconds(t, 20), job=2),
            client("load:job", seconds(t, 1), user=BOB),
            redo(seconds(t, 30), user=BOB),
        ])

        figures = self.methods(shapes="all")
        self.assertEqual((figures["drawn"][0], figures["pasted"][0], figures["propagated"][0]), (0, 1, 0))

    def test_a_redo_long_after_the_creation_is_no_creation(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            paste(seconds(t, 10)),
            undo(seconds(t, 300)),
            redo(seconds(t, 311)),
        ])

        figures = self.methods(shapes="all")
        self.assertEqual((figures["drawn"][0], figures["pasted"][0], figures["propagated"][0]), (0, 1, 0))


class ShapeSwitchTest(MethodsCase):
    def setUp(self) -> None:
        super().setUp()
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10), **BOX),  # 10 s
            draw(seconds(t, 20), **POLYGON),  # 10 s
            # four objects, two of them single-frame rectangles: 20 s, half of it to the boxes
            paste(seconds(t, 40), count=4, shape_type="mixed", rectangle_count=2, object_type="mixed"),
            propagate(seconds(t, 46), count=3, shape_type="rectangle", rectangle_count=3, object_type="shape"),
            undo(seconds(t, 50)),
            # a redo is no creation under either switch
            redo(seconds(t, 55)),
        ])

    def test_bounding_boxes_count_only_single_frame_rectangles_per_method(self):
        self.assertEqual(self.methods(shapes="bounding_boxes"), {
            "drawn": (1, 1, 10_000, 10_000),
            "pasted": (2, 2, 10_000, 5_000),
            "propagated": (3, 3, 6_000, 2_000),
        })

    def test_all_shapes_split_every_kind_of_object_by_method(self):
        self.assertEqual(self.methods(shapes="all"), {
            "drawn": (2, 2, 20_000, 10_000),
            "pasted": (4, 4, 20_000, 5_000),
            "propagated": (3, 3, 6_000, 2_000),
        })

    def test_under_either_switch_the_methods_add_up_to_creation_and_say_which_shapes_they_cover(self):
        for shapes in ("bounding_boxes", "all"):
            with self.subTest(shapes=shapes):
                body = self.overview(shapes=shapes)
                self.assertMethodsAddUpToCreation(body)
                self.assertEqual(body["creation_methods"]["shapes"], shapes)


class LegacyTest(MethodsCase):
    def test_a_legacy_period_shows_the_methods_for_all_shapes(self):
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10)),
            paste(seconds(t, 20), count=2),
        ])

        body = self.overview(shapes="bounding_boxes")

        self.assertEqual(body["creation_methods"]["shapes"], "all")
        self.assertEqual({method: figures[0] for method, figures in self.figures(body).items()},
                         {"drawn": 1, "pasted": 2, "propagated": 0})
        self.assertMethodsAddUpToCreation(body)


class FiltersAndPeriodTest(MethodsCase):
    def setUp(self) -> None:
        super().setUp()
        t = "2026-11-13 10:00:00"
        self.stack.add_events([
            client("load:job", seconds(t, 0)),
            draw(seconds(t, 10), **BOX),
            paste(seconds(t, 20), count=2, project=2, task=2, job=2, **BOX),
            client("load:job", seconds(t, 0), user=BOB),
            propagate(seconds(t, 30), count=5, user=BOB, **BOX),
            # last month: outside the week
            client("load:job", at("2026-10-31 10:00:00")),
            draw(at("2026-10-31 10:00:05"), **BOX),
        ])

    def overview(self, **query) -> dict:
        self.stack.keep_refreshing_since(at("2026-10-30 00:00:00"))
        status, body = self.stack.overview("lead", org="org7", **query)
        self.assertEqual(status, 200, body)
        return body

    def counts(self, **query) -> dict:
        body = self.overview(**query)
        self.assertMethodsAddUpToCreation(body)
        return {method: figures[0] for method, figures in self.figures(body).items()}

    def test_the_period_bounds_the_methods(self):
        self.assertEqual(self.counts(), {"drawn": 1, "pasted": 2, "propagated": 5})
        self.assertEqual(self.counts(period="month", month="2026-10"), {"drawn": 1, "pasted": 0, "propagated": 0})

    def test_a_project_filter_keeps_that_projects_creations(self):
        self.assertEqual(self.counts(project="2"), {"drawn": 0, "pasted": 2, "propagated": 0})

    def test_an_annotator_filter_keeps_that_annotators_creations(self):
        self.assertEqual(self.counts(annotator=str(BOB[0])), {"drawn": 0, "pasted": 0, "propagated": 5})


class RedoAcrossWindowEdgeTest(MethodsCase):
    stack_options = {"refresh_window_hours": 1}

    def test_a_redo_just_after_a_window_edge_adds_nothing_to_the_creation_before_it(self):
        self.stack.add_events([
            client("load:job", at("2026-11-13 09:57:00")),
            propagate(at("2026-11-13 09:58:00"), count=2),
            undo(at("2026-11-13 09:59:00")),
            redo(at("2026-11-13 10:01:00")),
        ])
        self.stack.refresh(at("2026-11-13 09:20:00"))  # window 09:00 .. 10:00
        self.stack.refresh(at("2026-11-13 10:20:00"))  # window 10:00 .. 11:00
        # the history step computes today's hours up to 10:00, so the period is processed (the edge stays)
        self.stack.settle()

        status, body = self.stack.overview("lead", org="org7", shapes="all")
        self.assertEqual(status, 200, body)
        figures = self.figures(body)
        self.assertEqual((figures["drawn"][0], figures["propagated"][0]), (0, 2))
