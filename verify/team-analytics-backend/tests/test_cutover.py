"""The cutover to the new activity logging: the first shape-tagged event on the instance decides which periods
are legacy (all of it before), partly legacy (it falls inside) or not legacy (all of it after), whatever the
scope holds. It is known from the first answer after a worker made the engine ready (the schema, then a search of
the recorded events: jobs._make_ready), and it moves to an earlier hour when an earlier shape-tagged event turns
up, never to a later one."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from cvat.apps.team_analytics.core.scope import Scope

from tests.support import NOW, FakeUser, StackTestCase, at, clickhouse_client, working_time
from tests.test_bounding_boxes import BOX
from tests.test_operations import client, draw

ORG_A, ORG_B = 7, 8
ALICE = (11, "alice")
BRUNO = (21, "bruno")
API = "/api/team-analytics/"
CUTOVER = "2026-11-02T10:00:00+00:00"  # the hour of the first shape-tagged event (org A)
EARLIER = "2026-10-25T10:00:00+00:00"  # the hour of a shape-tagged event that turns up later


class CutoverCase(StackTestCase):
    stack_options = {"refresh_window_hours": 400 * 24}

    def setUp(self) -> None:
        super().setUp()
        callers = self.stack.callers
        callers.add_user("lead-a", FakeUser(2, "lead-a", groups=["admin"], memberships={"org-a": (ORG_A, "maintainer", True)}))
        callers.add_user("lead-b", FakeUser(3, "lead-b", groups=["admin"], memberships={"org-b": (ORG_B, "maintainer", True)}))

    def get(self, endpoint: str, session: str = "lead-a", **query) -> dict:
        query.setdefault("org", "org-a" if session == "lead-a" else "org-b")
        status, body = self.stack.get(API + endpoint, session, **query)
        self.assertEqual(status, 200, body)
        return body

    def operations(self, session: str = "lead-a", **query) -> dict:
        return self.get("overview", session, **query)["operations"]

    @staticmethod
    def created(operations: dict) -> int:
        return next(row["objects"] for row in operations["rows"] if row["operation"] == "creation")

    def restart(self) -> None:
        """A worker makes a new engine ready on the stack's databases, as the first job does when it finds no
        readiness mark (the first job ever, or after the cache was emptied). Steps go to the new engine from here
        on."""
        self.stack.engine = self.stack.new_engine()

    def settle(self) -> None:
        """Steps until the engine has nothing more to do: all of history, and the daily check when it is due."""
        for _ in range(60):
            if self.stack.engine.step() >= 1:
                return
        self.fail("the engine kept working")

    def process_this_week(self) -> None:
        for _ in range(10):
            if self.get("overview", period="week")["processed"]:
                return
            self.stack.engine.step()
        self.fail("this week was never processed")


class WithCutoverTest(CutoverCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.add_events([
            # organization A: the stock UI in October, the new logging from 2 November 10:00 on
            working_time(at("2026-10-20 10:00:00"), 3_600_000, user=ALICE, org=ORG_A),
            client("load:job", at("2026-10-20 10:00:00")),
            draw(at("2026-10-20 10:00:10")),
            draw(at("2026-10-20 10:00:20")),
            client("load:job", at("2026-11-02 10:30:00")),
            draw(at("2026-11-02 10:30:10"), input_method="mouse", **BOX),
            # an operation logged without a shape type after the cutover (a 3D job)
            client("load:job", at("2026-11-10 10:00:00")),
            draw(at("2026-11-10 10:00:10")),
            # organization B, this week only: review work (working time) and a 3D job, never a tagged event
            working_time(at("2026-11-11 10:00:00"), 1_800_000, user=BRUNO, org=ORG_B),
            client("load:job", at("2026-11-11 11:00:00"), user=BRUNO, org=ORG_B),
            draw(at("2026-11-11 11:00:10"), user=BRUNO, org=ORG_B),
        ])
        self.stack.refresh()

    def test_status_reports_the_cutover(self):
        self.assertEqual(self.get("status")["cutover"], {"at": CUTOVER})
        self.assertEqual(self.get("status", "lead-b")["cutover"], {"at": CUTOVER})

    def test_a_period_that_ends_before_the_cutover_is_legacy(self):
        operations = self.operations(period="month", month="2026-10", shapes="bounding_boxes")
        self.assertEqual((operations["legacy"], operations["partly_legacy"], operations["shapes"]),
                         (True, False, "all"))
        self.assertEqual(self.created(operations), 2)

    def test_a_period_that_holds_the_cutover_is_partly_legacy_and_keeps_the_shape_switch(self):
        boxes = self.operations(period="month", month="2026-11", shapes="bounding_boxes")
        self.assertEqual((boxes["legacy"], boxes["partly_legacy"], boxes["cutover"], boxes["shapes"]),
                         (False, True, CUTOVER, "bounding_boxes"))
        self.assertEqual(self.created(boxes), 1, "only the bounding box drawn after the cutover")
        self.assertEqual(self.created(self.operations(period="month", month="2026-11", shapes="all")), 2)

    def test_a_period_after_the_cutover_is_never_legacy_even_without_tagged_events_in_its_scope(self):
        for session in ("lead-a", "lead-b"):
            with self.subTest(session=session):
                operations = self.operations(session, shapes="bounding_boxes")
                self.assertEqual((operations["legacy"], operations["partly_legacy"], operations["shapes"]),
                                 (False, False, "bounding_boxes"))
                self.assertEqual(self.created(operations), 0)
                methods = self.get("overview", session, shapes="bounding_boxes")["creation_methods"]
                self.assertEqual(methods["shapes"], "bounding_boxes")

    def test_details_and_full_view_decide_by_the_same_cutover(self):
        for endpoint in ("details", "list?by=annotators"):
            path, _, by = endpoint.partition("?by=")
            extra = {"by": by} if by else {}
            with self.subTest(endpoint=endpoint):
                week_b = self.get(path, "lead-b", shapes="bounding_boxes", **extra)
                self.assertEqual((week_b["legacy"], week_b["partly_legacy"], week_b["shapes"]),
                                 (False, False, "bounding_boxes"))
                october = self.get(path, period="month", month="2026-10", shapes="bounding_boxes", **extra)
                self.assertEqual((october["legacy"], october["partly_legacy"], october["shapes"]), (True, False, "all"))
                november = self.get(path, period="month", month="2026-11", shapes="bounding_boxes", **extra)
                self.assertEqual((november["legacy"], november["partly_legacy"], november["cutover"]),
                                 (False, True, CUTOVER))

    def test_an_empty_period_that_holds_the_cutover_is_neither_legacy_nor_partly_legacy(self):
        # a project with no job work at all: the period holds the cutover, its scope holds nothing
        empty = {"period": "month", "month": "2026-11", "project": "999", "shapes": "bounding_boxes"}
        answers = {
            "overview": self.operations(**empty),
            "details": self.get("details", **empty),
            "list": self.get("list", by="annotators", **empty),
        }
        for endpoint, body in answers.items():
            with self.subTest(endpoint=endpoint):
                self.assertEqual((body["legacy"], body["partly_legacy"]), (False, False))

    def test_trend_buckets_are_marked_by_the_cutover(self):
        monthly = self.get("trends", step="month", shapes="bounding_boxes")
        starts = [bucket["start"] for bucket in monthly["buckets"]]
        points = dict(zip(starts, monthly["lines"][0]["points"], strict=True))
        self.assertEqual(monthly["shapes"], "bounding_boxes")
        self.assertTrue(points["2026-10-01"]["legacy"])
        self.assertIsNone(points["2026-10-01"]["boxes"])
        # the month that holds the cutover is not legacy: its boxes are the tagged ones
        self.assertFalse(points["2026-11-01"]["legacy"])
        self.assertEqual(points["2026-11-01"]["boxes"], 1)

        weekly_b = self.get("trends", "lead-b", shapes="bounding_boxes")
        last = weekly_b["lines"][0]["points"][-1]
        self.assertEqual((weekly_b["buckets"][-1]["start"], last["legacy"], last["boxes"]), ("2026-11-09", False, 0))
        self.assertTrue(last["hotkey_recorded"])

    def test_a_table_keeps_the_legacy_content_of_the_rows_it_lists_while_its_own_filter_is_set(self):
        october = {"period": "month", "month": "2026-10", "shapes": "bounding_boxes"}
        november = {"period": "month", "month": "2026-11", "shapes": "bounding_boxes"}
        # the page filtered to a project, or an annotator, without work: the overview is empty, so not legacy
        for own in ({"project": "999"}, {"annotator": "999"}):
            with self.subTest(overview=own):
                empty = self.operations(**october, **own)
                self.assertEqual((empty["legacy"], empty["partly_legacy"]), (False, False))
        # a table lists every row of its own dimension whatever that filter says, and is labelled by those rows
        for endpoint in ("details", "list"):
            for by, own, listed in (("projects", {"project": "999"}, [1]), ("annotators", {"annotator": "999"}, [11])):
                with self.subTest(endpoint=endpoint, by=by):
                    table = self.get(endpoint, by=by, **october, **own)
                    self.assertEqual([row["id"] for row in table["rows"]], listed)
                    self.assertEqual((table["legacy"], table["partly_legacy"], table["shapes"]), (True, False, "all"))
                    holding = self.get(endpoint, by=by, **november, **own)
                    self.assertEqual((holding["legacy"], holding["partly_legacy"], holding["cutover"]),
                                     (False, True, CUTOVER))
            # the filter on the other dimension does narrow the table: nothing listed, nothing legacy
            with self.subTest(endpoint=endpoint, by="annotators", other="project"):
                narrowed = self.get(endpoint, by="annotators", project="999", **october)
                self.assertEqual((narrowed["rows"], narrowed["legacy"], narrowed["partly_legacy"]), ([], False, False))


class WhileHistoryIsProcessedTest(CutoverCase):
    """History fills newest first, but a processed period is labelled by the real cutover from the start."""

    stack_options = {}  # the trailing 48 h refresh, history one day per step

    def setUp(self) -> None:
        super().setUp()
        self.stack.add_events([
            working_time(at("2026-10-20 10:00:00"), 3_600_000, user=ALICE, org=ORG_A),
            client("load:job", at("2026-10-20 10:00:00")),
            draw(at("2026-10-20 10:00:10")),
            # the real cutover, days before the trailing hours
            client("load:job", at("2026-11-02 10:30:00")),
            draw(at("2026-11-02 10:30:10"), input_method="mouse", **BOX),
            # this week: untagged work on Tuesday, tagged work on Thursday (inside the trailing hours)
            working_time(at("2026-11-10 10:00:00"), 3_600_000, user=ALICE, org=ORG_A),
            client("load:job", at("2026-11-10 10:00:00")),
            draw(at("2026-11-10 10:00:10")),
            client("load:job", at("2026-11-12 10:00:00")),
            draw(at("2026-11-12 10:00:10"), input_method="mouse", **BOX),
        ])

    def test_a_processed_period_is_labelled_by_the_real_cutover_before_history_reaches_it(self):
        self.stack.refresh()
        self.process_this_week()
        self.assertEqual(self.get("status")["cutover"], {"at": CUTOVER})
        week = self.operations(period="week", shapes="bounding_boxes")
        self.assertEqual((week["legacy"], week["partly_legacy"], week["cutover"]), (False, False, CUTOVER))


class AtStartTest(CutoverCase):
    """The worker looks for the cutover in the recorded events when it makes the engine ready."""

    stack_options = {}  # the trailing 48 h refresh, history one day per step

    def test_a_service_started_on_recorded_tagged_events_knows_the_cutover_on_its_first_answer(self):
        self.stack.add_events([
            client("load:job", at("2026-11-02 10:30:00")),
            draw(at("2026-11-02 10:30:10"), input_method="mouse", **BOX),
        ])
        self.restart()
        first = self.get("status")
        self.assertIsNone(first["refresh"]["last_success_at"], "no refresh has run")
        self.assertEqual(first["cutover"], {"at": CUTOVER})
        self.assertEqual(self.operations(period="month", month="2026-11")["cutover"], CUTOVER)

    def test_tagged_work_that_has_not_reached_the_stored_totals_yields_a_cutover(self):
        self.stack.add_events([
            # the new logging began days before the trailing hours
            client("load:job", at("2026-11-02 10:30:00")),
            draw(at("2026-11-02 10:30:10"), input_method="mouse", **BOX),
            # since then only work that is never tagged (a 3D job)
            working_time(at("2026-11-12 10:00:00"), 3_600_000, user=ALICE, org=ORG_A),
            client("load:job", at("2026-11-12 10:00:00")),
            draw(at("2026-11-12 10:00:10")),
        ])
        self.restart()
        self.stack.refresh()
        self.process_this_week()  # history is still days away from 2 November: no tagged hour is stored
        self.assertFalse(self.get("status")["history"]["complete"])
        self.assertEqual(self.get("status")["cutover"], {"at": CUTOVER})
        week = self.operations(period="week", shapes="bounding_boxes")
        self.assertEqual((week["legacy"], week["partly_legacy"], week["cutover"], week["shapes"]),
                         (False, False, CUTOVER, "bounding_boxes"))

    def test_an_event_dated_in_the_future_is_not_the_cutover(self):
        self.stack.add_events([
            client("load:job", at("2026-11-20 10:00:00")),
            draw(at("2026-11-20 10:00:10"), input_method="mouse", **BOX),
        ])
        self.restart()
        self.assertEqual(self.get("status")["cutover"], {"at": None})

        # so it does not stand in the way of the real one, which the refresh that first stores tagged work finds
        self.stack.add_events([
            client("load:job", at("2026-11-13 10:00:00")),
            draw(at("2026-11-13 10:00:10"), input_method="mouse", **BOX),
        ])
        self.stack.refresh()
        self.assertEqual(self.get("status")["cutover"], {"at": "2026-11-13T10:00:00+00:00"})

    def test_a_service_started_before_cvat_created_its_events_table_still_starts(self):
        events = clickhouse_client(self.stack.events_db)
        events.command("RENAME TABLE events TO events_not_yet")
        self.restart()
        self.assertEqual(self.get("status")["cutover"], {"at": None})

        events.command("RENAME TABLE events_not_yet TO events")
        self.stack.add_events([
            client("load:job", at("2026-11-02 10:30:00")),
            draw(at("2026-11-02 10:30:10"), input_method="mouse", **BOX),
        ])
        self.stack.refresh()
        self.settle()
        self.assertEqual(self.get("status")["cutover"], {"at": CUTOVER})

    def test_two_replicas_that_find_the_cutover_at_once_leave_one_value(self):
        self.stack.add_events([
            client("load:job", at("2026-11-02 10:30:00")),
            draw(at("2026-11-02 10:30:10"), input_method="mouse", **BOX),
            client("load:job", at("2026-11-12 10:00:00")),
            draw(at("2026-11-12 10:00:10"), input_method="mouse", **BOX),
        ])
        together = threading.Barrier(2)

        def start(_: int):
            together.wait(30)
            return self.stack.new_engine()

        with ThreadPoolExecutor(max_workers=2) as pool:
            replicas = list(pool.map(start, range(2)))

        def each_replica_reports_the_cutover(when: str) -> None:
            for number, replica in enumerate(replicas):
                with self.subTest(when=when, replica=number):
                    status, body = self.stack.answer("status", Scope(ORG_A, 0, ""), {}, replica.now)
                    self.assertEqual(status, 200, body)
                    self.assertEqual(body["cutover"], {"at": CUTOVER})

        each_replica_reports_the_cutover("after the start")
        self.stack.engine = replicas[1]
        self.stack.refresh()
        self.settle()
        each_replica_reports_the_cutover("after a refresh, history and the daily check")


class SlowSearchCase(CutoverCase):
    """A cutover search slower than its limit (one second here) is stopped by ClickHouse, and the worker goes on
    without it as it does when the search fails."""

    stack_options = {"config_options": {"cutover_search_at_start_s": 1, "cutover_search_in_check_s": 1}}

    def add_tagged_work_read_slowly(self, since: str) -> None:
        """Adds sixteen bounding boxes drawn one a minute from `since` on (the cutover, for a search that finishes),
        and from then on makes every statement that reads the events' payload, the cutover search among them, take
        half a second per recorded event. Each event is a part of its own, with merges stopped, so that ClickHouse
        sleeps for one row at a time (it refuses more than three seconds of sleep per block): with the two threads
        of the test ClickHouse the search takes about four seconds, four times its limit. Real time, so a slow
        host only makes the search slower."""
        events = clickhouse_client(self.stack.events_db)
        events.command("SYSTEM STOP MERGES events")
        for n in range(16):
            self.stack.add_events([draw(at(since) + timedelta(minutes=n), input_method="mouse", **BOX)])
        events.command("RENAME TABLE events TO events_recorded")
        events.command("CREATE VIEW events AS SELECT * EXCEPT (payload), if(sleepEachRow(0.5) = 0, payload, payload) "
                       "AS payload FROM events_recorded")

    def assert_no_statement_left_running(self) -> None:
        """Waits until nothing that reads this test's events runs in ClickHouse."""
        server = clickhouse_client()
        pattern = f"%{self.stack.events_db}.events%"
        deadline = time.monotonic() + 60
        while server.query("SELECT count() FROM system.processes WHERE query LIKE {p:String} "
                           "AND query NOT LIKE '%system.processes%'", parameters={"p": pattern}).result_rows[0][0]:
            self.assertLess(time.monotonic(), deadline, "a statement over the events is still running")
            time.sleep(0.2)


class SlowSearchAtStartTest(SlowSearchCase):
    def test_a_service_whose_search_at_start_is_too_slow_starts_and_reports_no_cutover(self):
        self.add_tagged_work_read_slowly("2026-11-12 11:00:00")
        self.restart()
        self.assertEqual(self.get("status")["cutover"], {"at": None})
        self.assert_no_statement_left_running()
        self.assertEqual(self.get("status")["cutover"], {"at": None}, "the search went on after the worker gave up")


class SlowSearchInDailyCheckTest(SlowSearchCase):
    def test_a_daily_check_whose_search_is_too_slow_ends_without_it(self):
        # untagged work only: the start and the first daily check find no cutover
        self.stack.add_events([client("load:job", at("2026-11-12 10:00:00")), draw(at("2026-11-12 10:00:10"))])
        self.stack.refresh()
        self.settle()
        # a day later, after the refresh that is due: tagged work of the last minutes, which the next refresh would
        # store, but which is in no day that history computes or the daily check counts
        self.stack.now = NOW + timedelta(days=1)
        self.stack.engine.step()
        self.add_tagged_work_read_slowly("2026-11-14 15:00:00")
        self.settle()  # the day before, then the daily check, whose search reads too slowly; then it waits
        self.assertEqual(self.get("status")["cutover"], {"at": None})
        self.assert_no_statement_left_running()
        self.assertEqual(self.get("status")["cutover"], {"at": None}, "the search went on after the worker gave up")


class MovedCutoverTest(CutoverCase):
    """An earlier shape-tagged event that turns up after the cutover was stored moves it; a later one never does."""

    stack_options = {}  # the trailing 48 h refresh, history one day per step

    def setUp(self) -> None:
        super().setUp()
        self.stack.add_events([
            working_time(at("2026-10-20 10:00:00"), 3_600_000, user=ALICE, org=ORG_A),
            client("load:job", at("2026-10-20 10:00:00")),
            draw(at("2026-10-20 10:00:10")),
            # the week from 26 October lies between the hour the cutover moves to and the hour it moves from
            client("load:job", at("2026-10-28 10:00:00")),
            draw(at("2026-10-28 10:00:10")),
            client("load:job", at("2026-11-02 10:30:00")),
            draw(at("2026-11-02 10:30:10"), input_method="mouse", **BOX),
            client("load:job", at("2026-11-12 10:00:00")),
            draw(at("2026-11-12 10:00:10"), input_method="mouse", **BOX),
        ])
        self.stack.refresh()
        self.settle()  # all of history and the first daily check

    def late_event(self, day: str) -> None:
        self.stack.add_events([
            client("load:job", at(f"{day} 10:00:00")),
            draw(at(f"{day} 10:00:10"), input_method="mouse", **BOX),
        ])

    def next_day(self) -> None:
        """A day passes, and the engine does everything that is due then, the daily check included."""
        self.stack.now += timedelta(days=1)
        self.settle()

    def labels(self) -> dict:
        october = self.operations(period="month", month="2026-10", shapes="bounding_boxes")
        weekly = self.get("trends", shapes="bounding_boxes")
        week = dict(zip([bucket["start"] for bucket in weekly["buckets"]], weekly["lines"][0]["points"], strict=True))
        return {
            "cutover": self.get("status")["cutover"]["at"],
            "october": (october["legacy"], october["partly_legacy"], october["cutover"], october["shapes"]),
            "week of 26 October": week["2026-10-26"]["legacy"],
        }

    def test_an_earlier_tagged_event_that_arrives_later_moves_the_cutover_at_the_next_daily_check(self):
        before = {"cutover": CUTOVER, "october": (True, False, CUTOVER, "all"), "week of 26 October": True}
        self.assertEqual(self.labels(), before)

        self.late_event("2026-10-25")
        self.stack.now = NOW + timedelta(minutes=10)
        self.settle()  # a ten-minute refresh: the daily check ran less than a day ago
        self.assertEqual(self.labels(), before)

        self.next_day()
        # the periods between the two hours are relabelled: October now holds the cutover, the week is after it
        self.assertEqual(self.labels(), {
            "cutover": EARLIER, "october": (False, True, EARLIER, "bounding_boxes"), "week of 26 October": False,
        })
        boxes = self.operations(period="month", month="2026-10", shapes="bounding_boxes")
        self.assertEqual(self.created(boxes), 1, "the bounding box of 25 October")

    def test_a_later_tagged_event_never_moves_the_cutover(self):
        self.late_event("2026-11-05")
        self.next_day()
        self.assertEqual(self.get("status")["cutover"], {"at": CUTOVER})
        self.restart()
        self.assertEqual(self.get("status")["cutover"], {"at": CUTOVER})

    def test_a_wrongly_early_event_is_undone_by_removing_it_and_then_the_stored_value(self):
        self.late_event("2026-10-25")  # an event with a wrong date
        self.next_day()
        self.assertEqual(self.get("status")["cutover"], {"at": EARLIER})

        # removing the stored value alone is not enough: the same event is found again
        clickhouse_client(self.stack.totals_db).command("TRUNCATE TABLE cutover")
        self.restart()
        self.assertEqual(self.get("status")["cutover"], {"at": EARLIER})

        # the event first, then the stored value
        clickhouse_client(self.stack.events_db).command(
            "ALTER TABLE events DELETE WHERE toDate(timestamp) = '2026-10-25'", settings={"mutations_sync": 2})
        clickhouse_client(self.stack.totals_db).command("TRUNCATE TABLE cutover")
        self.restart()
        self.assertEqual(self.get("status")["cutover"], {"at": CUTOVER})
        self.next_day()  # the day is counted again without the event
        self.assertEqual(self.labels(),
                         {"cutover": CUTOVER, "october": (True, False, CUTOVER, "all"), "week of 26 October": True})


class WithoutCutoverTest(CutoverCase):
    def test_without_any_shape_tagged_event_a_period_with_job_work_is_legacy(self):
        self.stack.add_events([
            client("load:job", at("2026-11-13 10:00:00")),
            draw(at("2026-11-13 10:00:05")),
        ])
        self.stack.refresh()
        operations = self.operations(shapes="bounding_boxes")
        self.assertEqual((operations["legacy"], operations["partly_legacy"], operations["cutover"], operations["shapes"]),
                         (True, False, None, "all"))
        self.assertEqual(self.get("status")["cutover"], {"at": None})
        # every trend bucket is before the (unknown) cutover: the trends count all shapes
        trends = self.get("trends", shapes="bounding_boxes")
        last = trends["lines"][0]["points"][-1]
        self.assertEqual((trends["shapes"], last["legacy"], last["boxes"]), ("all", True, 1))

    def test_no_cutover_is_found_at_start_or_by_the_daily_check_without_a_shape_tagged_event(self):
        self.stack.add_events([
            client("load:job", at("2026-11-05 10:00:00")),
            draw(at("2026-11-05 10:00:05")),
            client("load:job", at("2026-11-13 10:00:00")),
            draw(at("2026-11-13 10:00:05")),
        ])
        self.restart()
        self.assertEqual(self.get("status")["cutover"], {"at": None})
        self.stack.refresh()
        self.settle()  # the daily check has run
        self.assertEqual(self.get("status")["cutover"], {"at": None})
        for period in ({"period": "week"}, {"period": "month", "month": "2026-11"}):
            with self.subTest(period=period):
                operations = self.operations(shapes="bounding_boxes", **period)
                self.assertEqual((operations["legacy"], operations["partly_legacy"], operations["cutover"],
                                  operations["shapes"]), (True, False, None, "all"))

    def test_an_empty_period_is_not_legacy(self):
        self.stack.refresh()
        operations = self.operations()
        self.assertEqual((operations["legacy"], operations["partly_legacy"]), (False, False))
