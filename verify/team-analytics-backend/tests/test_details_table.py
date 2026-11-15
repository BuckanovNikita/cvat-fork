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
P3 = {"project": 3, "task": 3, "job": 3}


class DetailsCase(OperationsCase):
    stack_options = {"technical_accounts": ("importer",)}

    def details_response(self, **query) -> tuple[int, dict]:
        self.stack.keep_refreshing_since(at("2026-11-05 00:00:00"))
        query.setdefault("org", "org7")
        return self.stack.get("/api/team-analytics/details", "lead", **query)

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


class TechnicalAccountOnlyProjectTest(FiguresCase):
    """Beside the figures above, a technical account saves boxes and polygons into project 3, where no person worked."""

    def setUp(self) -> None:
        super().setUp()
        self.stack.add_events([
            saved("create", seconds(T, 100), 7, **P3),
            saved("create", seconds(T, 100), 2, "polygon", **P3),
        ])

    def test_the_project_has_a_row_with_no_working_time_its_saved_boxes_and_its_model_boxes(self):
        body = self.details(by="projects", shapes="bounding_boxes")

        self.assertEqual(body["total"], 3)
        self.assertEqual(body["rows"][2], {
            "id": 3, "user_name": None, "annotators": 0, "sessions": 0, "working_time_ms": 0,
            "drawn": 0, "pasted": 0, "propagated": 0, "model": 7, "saved_boxes": 7, "alignments": 0,
            "class_changes": 0, "deletions": 0, "average_create_ms": None, "hotkey_share": None,
        })
        # under All shapes Model is every object the technical account saved; saved boxes stay boxes
        every_shape = self.details(by="projects", shapes="all")["rows"][2]
        self.assertEqual((every_shape["id"], every_shape["model"], every_shape["saved_boxes"]), (3, 9, 7))

    def test_the_project_is_among_the_ids_the_page_searches_by_name_in_the_tables_order(self):
        body = self.details(by="projects")

        self.assertEqual(body["project_ids"], [2, 1, 3])
        self.assertEqual(body["project_ids"], self.column(body, "id"))

    def test_a_technical_account_is_no_annotator_so_an_annotator_filter_on_it_lists_no_project(self):
        body = self.details(by="projects", annotator=IMPORTER[0])

        self.assertEqual((body["total"], body["rows"], body["project_ids"]), (0, [], []))

    def test_the_technical_account_is_still_no_row_of_the_table_by_annotator(self):
        annotators = self.details()

        self.assertEqual((annotators["total"], self.column(annotators, "user_name")), (2, ["bob", "alice"]))
        self.assertEqual(self.details(search="importer")["total"], 0)
        # nobody worked in the project, so the table by annotator narrowed to it is empty
        self.assertEqual(self.details(project=3)["rows"], [])

    def test_search_and_the_project_filter_treat_the_row_like_any_other(self):
        # the page matches project names itself and sends the ids; they come back in the table's order
        self.assertEqual(self.column(self.details(by="projects", ids="3"), "id"), [3])
        self.assertEqual(self.column(self.details(by="projects", ids="3,1"), "id"), [1, 3])
        # the table's own filter is not applied: every project stays listed for picking, this one selected or not
        self.assertEqual(self.column(self.details(by="projects", project=3), "id"), [2, 1, 3])
        # an annotator filter narrows the table to that annotator's projects, so not to this one
        self.assertEqual(self.column(self.details(by="projects", annotator=ALICE[0]), "id"), [1, 2])

    def test_such_a_project_of_another_organization_does_not_appear(self):
        self.stack.callers.add_user("admin", FakeUser(1, "admin", groups=["admin"]))
        self.stack.add_events([saved("create", seconds(T, 110), 5, org=8, project=9, task=9, job=9)])

        body = self.details(by="projects")

        self.assertEqual((self.column(body, "id"), body["project_ids"]), ([2, 1, 3], [2, 1, 3]))
        self.assertEqual(self.details(by="projects", ids="9")["rows"], [])
        # the save is stored: instance scope, which holds every organization, lists its project
        status, everything = self.stack.get("/api/team-analytics/details", "admin", by="projects")
        self.assertEqual((status, self.column(everything, "id")), (200, [2, 1, 3, 9]))


class TechnicalAccountOnlyProjectPagingTest(DetailsCase):
    """Ten projects with working time and an eleventh where only a technical account saved boxes."""

    def setUp(self) -> None:
        super().setUp()
        self.stack.add_events([
            *(working_time(seconds(T, n), n * MINUTE, user=ALICE, org=ORG, project=100 + n, task=n, job=n)
              for n in range(1, 11)),
            saved("create", seconds(T, 60), 4, project=200, task=200, job=200),
        ])

    def test_it_is_the_last_row_and_pages_like_any_other(self):
        first = self.details(by="projects")
        second = self.details(by="projects", page=2)
        past_the_end = self.details(by="projects", page=9)

        self.assertEqual((first["total"], first["page"]), (11, 1))
        self.assertEqual(self.column(first, "id"), list(range(110, 100, -1)))
        self.assertEqual(first["project_ids"], [*range(110, 100, -1), 200])
        self.assertEqual((second["page"], self.column(second, "id")), (2, [200]))
        self.assertEqual((past_the_end["page"], self.column(past_the_end, "id")), (2, [200]))


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


class ProcessedTest(DetailsCase):
    def test_a_period_not_wholly_processed_says_so(self):
        self.stack.add_events([
            working_time(at("2026-11-03 10:00:00"), HOUR, user=ALICE, org=ORG),
            working_time(at("2026-11-12 10:00:00"), HOUR, user=ALICE, org=ORG),
        ])
        self.stack.refresh()  # the trailing 48 h only

        def answer(**query) -> dict:
            status, body = self.stack.get("/api/team-analytics/details", "lead", org="org7", period="month",
                                          **query)
            self.assertEqual(status, 200, body)
            return body

        for kind in ("annotators", "projects"):
            body = answer(by=kind)
            self.assertFalse(body["processed"])
            # no figures, only the envelope: the kind of table, its page size and the legacy flags
            self.assertEqual({key: body[key] for key in ("by", "page_size", "legacy", "partly_legacy", "cutover",
                                                         "shapes")},
                             {"by": kind, "page_size": 10, "legacy": True, "partly_legacy": False, "cutover": None,
                              "shapes": "all"})
            self.assertEqual((body["page"], body["total"], body["rows"]), (None, None, None))
            # every key outside the envelope is null, so a field added later is withheld too
            self.assertLessEqual({key for key, value in body.items() if value is not None},
                                 {"by", "page_size", "processed", "technical_accounts", "legacy", "partly_legacy",
                                  "cutover", "shapes"})
        self.assertIsNone(answer(by="projects")["project_ids"])

        for _ in range(20):  # history: one day per step
            self.stack.engine.step()
        body = answer()
        self.assertTrue(body["processed"])
        self.assertEqual((body["page"], body["total"]), (1, 1))
        self.assertEqual(self.column(body, "working_time_ms"), [2 * HOUR])
        self.assertEqual(answer(by="projects")["project_ids"], [1])


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
