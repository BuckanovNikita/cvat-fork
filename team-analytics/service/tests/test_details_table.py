"""Details table: every figure for every annotator, or every project, in one paged, searchable table."""

from __future__ import annotations

from tests.support import FakeUser, at, working_time
from tests.test_bounding_boxes import BOX, POLYGON, drag
from tests.test_class_change import class_change
from tests.test_creation_methods import paste, propagate
from tests.test_keyboard_mouse import summary
from tests.test_model_saved_boxes import IMPORTER, detector, saved
from tests.test_operations import ALICE, BOB, ORG, OperationsCase, client, draw, seconds

MINUTE = 60_000
HOUR = 60 * MINUTE
T = "2026-11-13 10:00:00"
P2 = {"project": 2, "task": 2, "job": 2}


class DetailsCase(OperationsCase):
    stack_options = {"technical_accounts": ("importer",)}

    def details_response(self, **query) -> tuple[int, dict]:
        self.stack.keep_refreshing_since(at("2026-11-05 00:00:00"))
        query.setdefault("org", "org7")
        return self.stack.get("/team-analytics-api/v1/details", "lead", **query)

    def details(self, **query) -> dict:
        status, body = self.details_response(**query)
        self.assertEqual(status, 200, body)
        return body

    @staticmethod
    def column(body: dict, key: str) -> list:
        return [row[key] for row in body["rows"]]


class FiguresCase(DetailsCase):
    """alice works in projects 1 and 2, bob in project 2; a technical account saves boxes in project 2."""

    def setUp(self) -> None:
        super().setUp()
        later = "2026-11-13 12:00:00"
        bob = "2026-11-13 11:00:00"
        self.stack.add_events([
            client("load:job", seconds(T, 0)),
            draw(seconds(T, 10), **BOX),  # 10 s
            paste(seconds(T, 20), 3, **{**BOX, "rectangle_count": 3}),  # 10 s
            propagate(seconds(T, 30), 2, **{**BOX, "rectangle_count": 2}),  # 10 s
            drag(seconds(T, 40), 5),
            class_change(seconds(T, 50), 2, rectangle_count=2),
            client("delete:object", seconds(T, 60), count=1, **BOX),
            detector(seconds(T, 70), 4, 5),
            summary(seconds(T, 80), {"NEXT_FRAME": 3}, {"header": 1, "canvas": 10}),
            working_time(seconds(T, 90), 2 * HOUR, user=ALICE, org=ORG),
            client("load:job", seconds(later, 0), **P2),
            draw(seconds(later, 20), **POLYGON, **P2),  # 20 s, not a box
            working_time(seconds(later, 30), 30 * MINUTE, user=ALICE, org=ORG, **P2),
            client("load:job", seconds(bob, 0), user=BOB, **P2),
            draw(seconds(bob, 5), user=BOB, **BOX, **P2),  # 5 s
            working_time(seconds(bob, 10), 3 * HOUR, user=BOB, org=ORG, **P2),
            saved("create", seconds(bob, 20), 6, **P2),
        ])


class AnnotatorRowsTest(FiguresCase):
    def test_every_figure_per_annotator_sorted_by_working_time(self):
        body = self.details(shapes="bounding_boxes")

        self.assertEqual(body["by"], "annotators")
        self.assertEqual((body["total"], body["page"], body["page_size"]), (2, 1, 10))
        self.assertFalse(body["legacy"])
        self.assertEqual(body["shapes"], "bounding_boxes")
        bob, alice = body["rows"]
        self.assertEqual(bob, {
            "id": 12, "user_name": "bob", "projects": 1, "sessions": 1, "working_time_ms": 3 * HOUR,
            "drawn": 1, "pasted": 0, "propagated": 0, "model": 0, "saved_boxes": 0, "alignments": 0,
            "class_changes": 0, "deletions": 0, "average_create_ms": 5000, "hotkey_share": None,
        })
        self.assertEqual(alice, {
            "id": 11, "user_name": "alice", "projects": 2, "sessions": 2, "working_time_ms": 2 * HOUR + 30 * MINUTE,
            "drawn": 1, "pasted": 3, "propagated": 2, "model": 4, "saved_boxes": 0, "alignments": 1,
            "class_changes": 2, "deletions": 1, "average_create_ms": 5000, "hotkey_share": 0.75,
        })

    def test_the_shape_switch_counts_every_shape(self):
        alice = self.details(shapes="all")["rows"][1]

        self.assertEqual((alice["drawn"], alice["model"]), (2, 5))
        self.assertEqual(alice["average_create_ms"], 50_000 / 7)

    def test_a_technical_account_is_no_annotator(self):
        self.assertNotIn("importer", self.column(self.details(), "user_name"))
        self.assertEqual(self.details()["technical_accounts"], 1)


class ProjectRowsTest(FiguresCase):
    def test_every_figure_per_project_sorted_by_working_time(self):
        body = self.details(by="projects", shapes="bounding_boxes")

        self.assertEqual((body["by"], body["total"]), ("projects", 2))
        self.assertEqual(body["project_ids"], [2, 1])  # in the table's order
        two, one = body["rows"]
        self.assertEqual(two, {
            "id": 2, "user_name": None, "annotators": 2, "sessions": 2, "working_time_ms": 3 * HOUR + 30 * MINUTE,
            "drawn": 1, "pasted": 0, "propagated": 0, "model": 6, "saved_boxes": 6, "alignments": 0,
            "class_changes": 0, "deletions": 0, "average_create_ms": 5000, "hotkey_share": None,
        })
        self.assertEqual(one, {
            "id": 1, "user_name": None, "annotators": 1, "sessions": 1, "working_time_ms": 2 * HOUR,
            "drawn": 1, "pasted": 3, "propagated": 2, "model": 4, "saved_boxes": 0, "alignments": 1,
            "class_changes": 2, "deletions": 1, "average_create_ms": 5000, "hotkey_share": 0.75,
        })


class FiltersTest(FiguresCase):
    def test_annotators_follow_the_project_filter_and_all_stay_listed_under_an_annotator_filter(self):
        in_two = self.details(project=2, shapes="bounding_boxes")
        picked = self.details(annotator=11, shapes="bounding_boxes")

        self.assertEqual(self.column(in_two, "user_name"), ["bob", "alice"])
        self.assertEqual(self.column(in_two, "working_time_ms"), [3 * HOUR, 30 * MINUTE])
        # alice's session at 12:00 touched project 2; what she drew there was a polygon
        self.assertEqual((in_two["rows"][1]["sessions"], in_two["rows"][1]["drawn"]), (1, 0))
        self.assertEqual(self.column(picked, "user_name"), ["bob", "alice"])

    def test_projects_follow_the_annotator_filter_and_all_stay_listed_under_a_project_filter(self):
        alices = self.details(by="projects", annotator=11, shapes="bounding_boxes")
        picked = self.details(by="projects", project=1)

        self.assertEqual(self.column(alices, "id"), [1, 2])
        self.assertEqual(self.column(alices, "working_time_ms"), [2 * HOUR, 30 * MINUTE])
        # under an annotator filter only her detector boxes are Model, not what a technical account saved
        self.assertEqual(self.column(alices, "model"), [4, 0])
        self.assertEqual(self.column(alices, "annotators"), [1, 1])
        self.assertEqual(self.column(picked, "id"), [2, 1])

    def test_the_period_applies(self):
        self.stack.add_events([working_time(at("2026-10-14 10:00:00"), HOUR, user=BOB, org=ORG)])
        self.stack.keep_refreshing_since(at("2026-10-10 00:00:00"))

        october = self.details(period="month", month="2026-10")

        self.assertEqual(self.column(october, "user_name"), ["bob"])
        self.assertEqual(self.column(october, "working_time_ms"), [HOUR])


class PagingAndSearchTest(DetailsCase):
    def setUp(self) -> None:
        super().setUp()
        # 23 annotators: annotator n worked n minutes, in project 100 + n % 3
        self.stack.add_events([
            working_time(seconds(T, n), n * MINUTE, user=(100 + n, f"user{n:02d}"), org=ORG, project=100 + n % 3)
            for n in range(1, 24)
        ])

    def test_ten_rows_a_page_with_the_count_of_rows(self):
        first = self.details()
        third = self.details(page=3)

        self.assertEqual((first["page"], first["total"]), (1, 23))
        self.assertEqual(self.column(first, "user_name"), [f"user{n:02d}" for n in range(23, 13, -1)])
        self.assertEqual((third["page"], self.column(third, "user_name")), (3, ["user03", "user02", "user01"]))

    def test_a_page_past_the_end_gives_the_last_page(self):
        body = self.details(page=9)

        self.assertEqual((body["page"], len(body["rows"])), (3, 3))

    def test_search_narrows_annotators_by_name_ignoring_case(self):
        body = self.details(search="USER1")

        self.assertEqual(body["total"], 10)
        self.assertEqual(self.column(body, "user_name")[:2], ["user19", "user18"])

    def test_project_ids_come_in_the_tables_order_so_the_page_can_page_a_name_search(self):
        body = self.details(by="projects")

        # project 102 has the most working time (100 min), then 101 (92), then 100 (84)
        self.assertEqual(body["project_ids"], [102, 101, 100])
        self.assertEqual(body["project_ids"], self.column(body, "id"))
        # a page of ids asked in that order comes back in the same order
        self.assertEqual(self.column(self.details(by="projects", ids="101,100"), "id"), [101, 100])

    def test_search_text_is_matched_literally(self):
        self.assertEqual(self.details(search="user_")["total"], 0)
        self.assertEqual(self.details(search="%")["rows"], [])

    def test_projects_are_narrowed_to_the_ids_the_page_matched(self):
        self.assertEqual(self.column(self.details(by="projects", ids="100,102"), "id"), [102, 100])
        self.assertEqual(self.details(by="projects", ids="")["total"], 0)
        self.assertEqual(self.details(by="projects")["total"], 3)

    def test_bad_queries_are_refused(self):
        for query in ({"by": "tasks"}, {"page": "0"}, {"page": "x"}, {"by": "projects", "ids": "1,a"}):
            status, body = self.details_response(**query)
            self.assertEqual((status, body["error"]), (400, "bad_request"), query)

    def test_a_worker_is_refused(self):
        self.stack.cvat.add_user("worker", FakeUser(3, "worker", memberships={"org7": (ORG, "worker", True)}))

        status, body = self.stack.get("/team-analytics-api/v1/details", "worker", org="org7")

        self.assertEqual((status, body["error"]), (403, "forbidden"))


class ProcessedTest(DetailsCase):
    def test_a_period_not_wholly_processed_says_so(self):
        self.stack.add_events([
            working_time(at("2026-11-03 10:00:00"), HOUR, user=ALICE, org=ORG),
            working_time(at("2026-11-12 10:00:00"), HOUR, user=ALICE, org=ORG),
        ])
        self.stack.refresh()  # the trailing 48 h only

        def processed() -> bool:
            status, body = self.stack.get("/team-analytics-api/v1/details", "lead", org="org7", period="month")
            self.assertEqual(status, 200, body)
            return body["processed"]

        self.assertFalse(processed())
        for _ in range(20):  # history: one day per step
            self.stack.service.step()
        self.assertTrue(processed())


class LegacyTest(DetailsCase):
    def setUp(self) -> None:
        super().setUp()
        # events of the stock UI: no shape type, no class change, no input records
        self.stack.add_events([
            client("load:job", seconds(T, 0)),
            draw(seconds(T, 10)),
            client("paste:object", seconds(T, 20), count=2),
            working_time(seconds(T, 30), HOUR, user=ALICE, org=ORG),
            saved("create", seconds(T, 40), 3, user=ALICE),
            saved("create", seconds(T, 40), 7),  # by the technical account
        ])

    def test_a_legacy_period_counts_all_shapes_and_has_saved_boxes(self):
        annotators = self.details(shapes="bounding_boxes")
        projects = self.details(by="projects", shapes="bounding_boxes")

        self.assertTrue(annotators["legacy"])
        self.assertEqual(annotators["shapes"], "all")
        alice = annotators["rows"][0]
        self.assertEqual((alice["drawn"], alice["pasted"], alice["saved_boxes"]), (1, 2, 3))
        self.assertEqual(projects["rows"][0]["saved_boxes"], 10)

    def test_an_empty_period_is_not_legacy(self):
        body = self.details(period="month", month="2026-09")

        self.assertEqual((body["legacy"], body["total"], body["rows"]), (False, 0, []))
        self.assertEqual(self.details(by="projects", period="month", month="2026-09")["project_ids"], [])
