"""Model, technical accounts and saved boxes.

Model = boxes no person drew: every single-frame rectangle a technical account saves (for the project it was
saved in) and every box the built-in detector made (for the annotator who ran it and the project). Saved boxes
= single-frame rectangles the server stored when jobs were saved, whatever their creation method.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from tests.support import at, working_time
from tests.test_operations import ALICE, BOB, ORG, OperationsCase, client, draw, seconds

IMPORTER = (99, "importer")
BOX = {"shape_type": "rectangle", "rectangle_count": 1, "object_type": "shape"}
T = "2026-11-13 10:00:00"


def saved(action: str, when: datetime, count: int, shape_type: str = "rectangle", *, resource: str = "shapes",
          user: tuple[int, str] = IMPORTER, org: int | None = ORG, project: int | None = 1, task: int | None = 1,
          job: int | None = 1) -> dict:
    """A saved-annotation row as the CVAT server writes it when a job's annotations change
    (`create|update|delete:shapes|tracks|tags`, obj_name = shape type, count = top-level objects)."""
    body = {resource: [{"id": n} for n in range(count)], "request": {"id": str(uuid.uuid4()), "user_agent": "t"}}
    return {
        "scope": f"{action}:{resource}", "source": "server", "timestamp": when, "count": count, "duration": 0,
        "obj_name": shape_type if resource != "tags" else None,
        "project_id": project, "task_id": task, "job_id": job,
        "user_id": user[0], "user_name": user[1], "user_email": f"{user[1]}@example.com",
        "org_id": org, "org_slug": None if org is None else f"org{org}",
        "payload": json.dumps(body, separators=(",", ":")),
    }


def detector(when: datetime, rectangles: int, objects: int, **kwargs) -> dict:
    """The record the annotation view sends after the built-in detector created objects."""
    return client("debug:info", when, obj_name="team_analytics:model_creation", count=objects,
                  rectangle_count=rectangles, **kwargs)


class ModelCase(OperationsCase):
    stack_options = {"technical_accounts": (99,)}

    def overview(self, **query) -> dict:
        self.stack.keep_refreshing_since(at("2026-11-05 00:00:00"))
        status, body = self.stack.overview("lead", org="org7", **query)
        self.assertEqual(status, 200, body)
        return body

    def model(self, **query) -> int:
        return self.overview(**query)["creation_methods"]["model"]["objects"]


class TechnicalAccountSavesTest(ModelCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.add_events([
            client("load:job", seconds(T, 0)),
            draw(seconds(T, 10), **BOX),  # alice draws one box in project 1
            saved("create", seconds(T, 20), 5, project=2, task=2, job=2),
            saved("create", seconds(T, 20), 2, "polygon", project=2, task=2, job=2),
            saved("create", seconds(T, 20), 1, resource="tracks", project=2, task=2, job=2),
            # updates and deletions are no creation
            saved("update", seconds(T, 30), 4, project=2, task=2, job=2),
            saved("delete", seconds(T, 40), 1, project=2, task=2, job=2),
        ])

    def test_every_single_frame_rectangle_a_technical_account_saves_is_model(self):
        self.assertEqual(self.model(shapes="bounding_boxes"), 5)

    def test_model_counts_for_the_project_the_boxes_were_saved_in(self):
        self.assertEqual(self.model(shapes="bounding_boxes", project=2), 5)
        self.assertEqual(self.model(shapes="bounding_boxes", project=1), 0)

    def test_under_all_shapes_model_is_every_object_the_technical_account_saved(self):
        self.assertEqual(self.model(shapes="all"), 8)

    def test_model_has_a_share_of_every_object_created_and_stays_out_of_creation(self):
        body = self.overview(shapes="bounding_boxes")
        methods = body["creation_methods"]

        self.assertEqual(methods["model"], {"objects": 5, "share": 5 / 6})
        self.assertEqual([row["share"] for row in methods["rows"]], [1 / 6, 0, 0])
        creation = self.by_name(body["operations"])["creation"]
        self.assertEqual((creation["objects"], methods["total"]["objects"]), (1, 1))
        self.assertEqual(methods["total"]["average_ms"], creation["average_ms"])

    def test_the_page_is_told_how_many_technical_accounts_are_configured(self):
        self.assertEqual(self.overview()["creation_methods"]["technical_accounts"], 1)

    def test_a_technical_account_is_never_an_annotator_so_an_annotator_filter_shows_none_of_its_boxes(self):
        self.assertEqual(self.model(shapes="bounding_boxes", annotator=IMPORTER[0]), 0)
        self.assertEqual(self.model(shapes="bounding_boxes", annotator=ALICE[0]), 0)


class ReuploadTest(ModelCase):
    def test_a_reupload_by_a_technical_account_counts_again(self):
        self.stack.add_events([
            saved("create", seconds(T, 0), 5),
            # a re-upload replaces everything: the server deletes all and creates all again
            saved("delete", seconds(T, 600), 5),
            saved("create", seconds(T, 600), 5),
        ])
        self.stack.refresh()  # computing the same hours again counts nothing twice

        self.assertEqual(self.model(shapes="bounding_boxes"), 10)


class OtherOrganizationTest(ModelCase):
    def test_saves_in_another_organization_are_not_counted(self):
        self.stack.add_events([saved("create", seconds(T, 0), 5, org=8), detector(seconds(T, 5), 2, 2, org=8)])

        self.assertEqual(self.model(shapes="bounding_boxes"), 0)
        self.assertEqual(self.overview()["saved_boxes"]["boxes"], 0)


class TechnicalAccountsLeftOutTest(ModelCase):
    def test_a_technical_account_is_absent_from_annotators_sessions_and_working_time(self):
        self.stack.add_events([
            client("load:job", seconds(T, 0)),
            draw(seconds(T, 10), **BOX),
            working_time(seconds(T, 10), 60_000, user=ALICE, org=ORG),
            client("load:job", seconds(T, 0), user=IMPORTER),
            draw(seconds(T, 10), user=IMPORTER, **BOX),
            working_time(seconds(T, 10), 600_000, user=IMPORTER, org=ORG),
            saved("create", seconds(T, 20), 5),
        ])

        body = self.overview()

        self.assertEqual([row["user_name"] for row in body["by_annotator"]["rows"]], ["alice"])
        self.assertEqual(body["headline"]["annotators"], 1)
        self.assertEqual([row["user_name"] for row in body["sessions"]["by_annotator"]], ["alice"])
        self.assertEqual(body["operations"]["working_time_ms"], 60_000)
        self.assertEqual(sum(point["working_time_ms"] for point in body["time_series"]["buckets"]), 60_000)
        self.assertEqual([row["user_name"] for row in body["saved_boxes"]["by_annotator"]], [])


class ConfiguredListTest(ModelCase):
    """The list is configuration: the same events read with another list give other figures."""

    stack_options = {"technical_accounts": ()}

    def test_without_the_account_in_the_list_its_saves_are_not_model_and_it_is_an_annotator(self):
        self.stack.add_events([
            working_time(seconds(T, 10), 600_000, user=IMPORTER, org=ORG),
            saved("create", seconds(T, 20), 5),
        ])

        body = self.overview(shapes="bounding_boxes")

        self.assertEqual(body["creation_methods"]["model"]["objects"], 0)
        self.assertEqual(body["creation_methods"]["technical_accounts"], 0)
        self.assertEqual([row["user_name"] for row in body["by_annotator"]["rows"]], ["importer"])
        self.assertEqual(body["saved_boxes"]["by_annotator"],
                         [{"user_id": IMPORTER[0], "user_name": "importer", "boxes": 5}])

    def test_a_change_of_the_list_applies_to_past_hours_on_the_next_read(self):
        self.stack.add_events([
            working_time(seconds(T, 10), 600_000, user=IMPORTER, org=ORG),
            saved("create", seconds(T, 20), 5),
        ])
        self.assertEqual(self.model(shapes="bounding_boxes"), 0)

        # the worker reads the list for every answer; the stored totals stay as they are
        self.stack.technical_accounts = (IMPORTER[0],)
        status, body = self.stack.overview("lead", org="org7", shapes="bounding_boxes")

        self.assertEqual(status, 200, body)
        self.assertEqual(body["creation_methods"]["model"]["objects"], 5)
        self.assertEqual(body["creation_methods"]["technical_accounts"], 1)
        self.assertEqual(body["by_annotator"]["rows"], [])
        self.assertEqual(body["saved_boxes"]["by_annotator"], [])


class TechnicalAccountByIdTest(ModelCase):
    """The list holds user ids: a technical account stays technical under every name it had, and another user
    who has one of its names is a person."""

    def test_a_renamed_technical_account_is_technical_in_every_hour(self):
        self.stack.add_events([
            working_time(at("2026-11-12 10:00:10"), 600_000, user=(99, "ingest-bot"), org=ORG),
            saved("create", at("2026-11-12 10:00:20"), 3, user=(99, "ingest-bot")),
            working_time(seconds(T, 10), 600_000, user=IMPORTER, org=ORG),
            saved("create", seconds(T, 20), 5),
            working_time(seconds(T, 10), 300_000, user=ALICE, org=ORG),
        ])

        body = self.overview(shapes="bounding_boxes")

        self.assertEqual(body["creation_methods"]["model"]["objects"], 8)
        self.assertEqual([row["user_name"] for row in body["by_annotator"]["rows"]], ["alice"])
        self.assertEqual(body["saved_boxes"]["by_annotator"], [])
        status, details = self.stack.get("/api/team-analytics/details", "lead", org="org7")
        self.assertEqual(status, 200, details)
        self.assertEqual([row["user_name"] for row in details["rows"]], ["alice"])

    def test_another_user_with_a_technical_accounts_name_is_a_person(self):
        namesake = (98, "importer")
        self.stack.add_events([
            working_time(seconds(T, 10), 600_000, user=namesake, org=ORG),
            saved("create", seconds(T, 20), 4, user=namesake),
            saved("create", seconds(T, 20), 5),  # the technical account itself
        ])

        body = self.overview(shapes="bounding_boxes")

        self.assertEqual(body["creation_methods"]["model"]["objects"], 5)
        self.assertEqual([(row["user_id"], row["user_name"]) for row in body["by_annotator"]["rows"]],
                         [(98, "importer")])
        self.assertEqual(body["saved_boxes"]["by_annotator"], [{"user_id": 98, "user_name": "importer", "boxes": 4}])


class DetectorTest(ModelCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.add_events([
            client("load:job", seconds(T, 0)),
            draw(seconds(T, 10), **BOX),
            # alice runs the detector in project 1: three boxes and a tag
            detector(seconds(T, 20), 3, 4),
            # bob runs it in project 2: two boxes
            client("load:job", seconds(T, 0), user=BOB, project=2, task=2, job=2),
            detector(seconds(T, 30), 2, 2, user=BOB, project=2, task=2, job=2),
            # the technical account saves in project 1
            saved("create", seconds(T, 40), 6),
        ])

    def test_detector_boxes_are_model(self):
        self.assertEqual(self.model(shapes="bounding_boxes"), 3 + 2 + 6)
        self.assertEqual(self.model(shapes="all"), 4 + 2 + 6)

    def test_detector_boxes_count_for_the_annotator_who_ran_it_and_nothing_a_technical_account_saved_does(self):
        self.assertEqual(self.model(shapes="bounding_boxes", annotator=ALICE[0]), 3)
        self.assertEqual(self.model(shapes="bounding_boxes", annotator=BOB[0]), 2)

    def test_detector_boxes_count_for_the_project_beside_the_technical_accounts_saves(self):
        self.assertEqual(self.model(shapes="bounding_boxes", project=1), 3 + 6)
        self.assertEqual(self.model(shapes="bounding_boxes", project=2), 2)

    def test_detector_boxes_are_not_creations_by_people(self):
        body = self.overview(shapes="bounding_boxes")

        self.assertEqual(self.by_name(body["operations"])["creation"]["objects"], 1)
        self.assertEqual(body["creation_methods"]["total"]["objects"], 1)


class SavedBoxesTest(ModelCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.add_events([
            saved("create", seconds(T, 0), 4, user=ALICE),
            saved("create", seconds(T, 5), 3, "polygon", user=ALICE),  # not a box
            saved("create", seconds(T, 5), 1, resource="tracks", user=ALICE),  # not single-frame
            saved("update", seconds(T, 6), 4, user=ALICE),
            saved("delete", seconds(T, 7), 1, user=ALICE),
            saved("create", seconds(T, 10), 2, user=BOB, project=2, task=2, job=2),
            saved("create", seconds(T, 20), 5, project=2, task=2, job=2),  # the technical account
            # a save outside any job (e.g. a task-level import) still belongs to its project
            saved("create", seconds(T, 30), 1, user=BOB, project=2, task=2, job=None),
        ])

    def test_saved_boxes_are_every_single_frame_rectangle_the_server_stored(self):
        self.assertEqual(self.overview()["saved_boxes"]["boxes"], 4 + 2 + 5 + 1)

    def test_saved_boxes_per_annotator_leave_the_technical_account_out(self):
        self.assertEqual(self.overview()["saved_boxes"]["by_annotator"], [
            {"user_id": ALICE[0], "user_name": "alice", "boxes": 4},
            {"user_id": BOB[0], "user_name": "bob", "boxes": 3},
        ])

    def test_saved_boxes_per_project_include_every_method(self):
        self.assertEqual(self.overview()["saved_boxes"]["by_project"], [
            {"project_id": 2, "boxes": 8},
            {"project_id": 1, "boxes": 4},
        ])

    def test_saved_boxes_follow_the_project_and_annotator_filters_and_not_the_shape_switch(self):
        self.assertEqual(self.overview(project=2)["saved_boxes"]["boxes"], 8)
        self.assertEqual(self.overview(project=2)["saved_boxes"]["by_annotator"],
                         [{"user_id": BOB[0], "user_name": "bob", "boxes": 3}])
        self.assertEqual(self.overview(annotator=ALICE[0])["saved_boxes"]["boxes"], 4)
        self.assertEqual(self.overview(shapes="all")["saved_boxes"]["boxes"],
                         self.overview(shapes="bounding_boxes")["saved_boxes"]["boxes"])


class TechnicalAccountFilterTest(ModelCase):
    """An annotator filter on a technical account's id (a shared link can carry one): the account is no annotator,
    so every figure of people and every saved-box figure is empty, on the overview, the full views and the details
    alike."""

    def setUp(self) -> None:
        super().setUp()
        self.stack.add_events([
            client("load:job", seconds(T, 0)),
            draw(seconds(T, 10), **BOX),  # alice draws one box in project 1
            working_time(seconds(T, 10), 600_000, user=ALICE, org=ORG),
            saved("create", seconds(T, 20), 4, user=ALICE),
            # the technical account works, draws, runs the detector and saves in project 2
            client("load:job", seconds(T, 0), user=IMPORTER, project=2, task=2, job=2),
            draw(seconds(T, 15), user=IMPORTER, project=2, task=2, job=2, **BOX),
            working_time(seconds(T, 15), 600_000, user=IMPORTER, org=ORG, project=2, task=2, job=2),
            detector(seconds(T, 25), 2, 2, user=IMPORTER, project=2, task=2, job=2),
            saved("create", seconds(T, 30), 5, project=2, task=2, job=2),
        ])

    def get(self, endpoint: str, **query) -> dict:
        status, body = self.stack.get("/api/team-analytics/" + endpoint, "lead", org="org7", **query)
        self.assertEqual(status, 200, body)
        return body

    def test_without_a_filter_its_saved_boxes_count_in_total_and_for_their_project(self):
        boxes = self.overview(shapes="bounding_boxes")["saved_boxes"]
        self.assertEqual(boxes["boxes"], 9)
        self.assertEqual(boxes["by_project"], [{"project_id": 2, "boxes": 5}, {"project_id": 1, "boxes": 4}])

    def test_the_overview_under_its_id_is_empty(self):
        body = self.overview(shapes="bounding_boxes", annotator=IMPORTER[0])
        self.assertEqual(body["saved_boxes"], {"boxes": 0, "by_annotator": [], "by_project": []})
        self.assertEqual(body["headline"], {"annotators": 0, "projects": 0})
        # the rows by annotator drop their own filter, as the full view does: every annotator stays
        # listed so another can be picked, and the technical account is never one of them
        self.assertEqual([row["user_id"] for row in body["by_annotator"]["rows"]], [ALICE[0]])
        self.assertEqual(body["by_project"]["rows"], [])
        self.assertEqual(body["creation_methods"]["model"]["objects"], 0)
        self.assertEqual(body["creation_methods"]["total"]["objects"], 0)
        self.assertEqual(self.by_name(body["operations"])["creation"]["objects"], 0)

    def test_the_full_views_under_its_id_list_no_project_and_no_technical_account(self):
        self.overview()  # refreshed and processed
        self.assertEqual(self.get("list", by="projects", annotator=IMPORTER[0])["rows"], [])
        # the list by annotators drops its own filter: every annotator stays listed, the account is none
        annotators = self.get("list", by="annotators", annotator=IMPORTER[0])["rows"]
        self.assertEqual([row["id"] for row in annotators], [ALICE[0]])

    def test_the_details_under_its_id_list_no_project_and_no_technical_account(self):
        self.overview()  # refreshed and processed
        projects = self.get("details", by="projects", annotator=IMPORTER[0])
        self.assertEqual((projects["rows"], projects["total"]), ([], 0))
        annotators = self.get("details", annotator=IMPORTER[0])
        self.assertEqual([row["user_name"] for row in annotators["rows"]], ["alice"])


class LegacyPeriodTest(ModelCase):
    def test_a_legacy_period_has_its_saved_boxes(self):
        self.stack.add_events([
            client("load:job", seconds(T, 0)),
            draw(seconds(T, 10)),  # no shape fields: recorded before shape tagging
            working_time(seconds(T, 10), 60_000, user=ALICE, org=ORG),
            saved("create", seconds(T, 20), 3, user=ALICE),
        ])

        body = self.overview(shapes="bounding_boxes")

        self.assertTrue(body["operations"]["legacy"])
        self.assertEqual(body["saved_boxes"]["boxes"], 3)

    def test_in_a_legacy_period_model_covers_all_shapes_like_the_creation_methods(self):
        self.stack.add_events([
            client("load:job", seconds(T, 0)),
            draw(seconds(T, 10)),
            saved("create", seconds(T, 20), 3),
            saved("create", seconds(T, 20), 2, "polygon"),
        ])

        methods = self.overview(shapes="bounding_boxes")["creation_methods"]

        self.assertEqual((methods["shapes"], methods["model"]["objects"]), ("all", 5))
