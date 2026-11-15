"""Periods: Week, Two weeks, Month (any earlier month, the current one to date) and Year, in the viewer's
time zone, and working time laid out per day (per week for Year)."""

from tests.support import FakeUser, StackTestCase, at, working_time

ORG = 7
ALICE = (11, "alice")
BOB = (12, "bob")
# One refresh covers more than a year, so a test needs no history fill.
WIDE = {"refresh_window_hours": 400 * 24}


class PeriodCase(StackTestCase):
    stack_options = WIDE

    def setUp(self) -> None:
        super().setUp()
        self.stack.callers.add_user("lead", FakeUser(2, "lead", groups=["admin"], memberships={"org7": (ORG, "maintainer", True)}))

    def overview(self, **query) -> dict:
        status, body = self.stack.overview("lead", org="org7", **query)
        self.assertEqual(status, 200, body)
        return body

    def total_ms(self, **query) -> int:
        return sum(row["working_time_ms"] for row in self.overview(**query)["by_annotator"]["rows"])

    def refused(self, **query) -> dict:
        status, body = self.stack.overview("lead", org="org7", **query)
        self.assertEqual(status, 400, body)
        self.assertNotIn("by_annotator", body)
        return body


class PeriodSpanTest(PeriodCase):
    """Today is Friday 2026-11-13 (15:20 UTC)."""

    def test_two_weeks_are_the_last_14_days_ending_today(self):
        self.stack.add_events([
            working_time(at("2026-10-30 23:59:00"), 1_000, user=ALICE, org=ORG),
            working_time(at("2026-10-31 00:00:00"), 20_000, user=ALICE, org=ORG),
            working_time(at("2026-11-13 15:10:00"), 300_000, user=ALICE, org=ORG),
        ])
        self.stack.refresh()
        self.assertEqual(self.total_ms(period="two_weeks"), 320_000)
        period = self.overview(period="two_weeks")["period"]
        self.assertEqual((period["name"], period["first_day"], period["last_day"]),
                         ("two_weeks", "2026-10-31", "2026-11-13"))

    def test_week_is_still_the_last_7_days(self):
        self.stack.add_events([
            working_time(at("2026-11-06 23:59:00"), 1_000, user=ALICE, org=ORG),
            working_time(at("2026-11-07 00:00:00"), 20_000, user=ALICE, org=ORG),
        ])
        self.stack.refresh()
        self.assertEqual(self.total_ms(period="week"), 20_000)
        self.assertEqual(self.total_ms(), 20_000)  # Week is the default

    def test_the_current_month_runs_from_its_first_day_to_date(self):
        self.stack.add_events([
            working_time(at("2026-10-31 23:59:00"), 1_000, user=ALICE, org=ORG),
            working_time(at("2026-11-01 00:00:00"), 20_000, user=ALICE, org=ORG),
            working_time(at("2026-11-13 15:10:00"), 300_000, user=ALICE, org=ORG),
        ])
        self.stack.refresh()
        self.assertEqual(self.total_ms(period="month", month="2026-11"), 320_000)
        self.assertEqual(self.total_ms(period="month"), 320_000)  # no month named: the current one
        period = self.overview(period="month", month="2026-11")["period"]
        self.assertEqual(period["month"], "2026-11")
        self.assertEqual((period["first_day"], period["last_day"]), ("2026-11-01", "2026-11-13"))
        self.assertTrue(period["to_date"])

    def test_an_earlier_month_is_that_whole_calendar_month(self):
        self.stack.add_events([
            working_time(at("2026-09-30 23:59:00"), 1_000, user=ALICE, org=ORG),
            working_time(at("2026-10-01 00:00:00"), 20_000, user=ALICE, org=ORG),
            working_time(at("2026-10-31 23:59:00"), 300_000, user=ALICE, org=ORG),
            working_time(at("2026-11-01 00:00:00"), 4_000_000, user=ALICE, org=ORG),
        ])
        self.stack.refresh()
        self.assertEqual(self.total_ms(period="month", month="2026-10"), 320_000)
        period = self.overview(period="month", month="2026-10")["period"]
        self.assertEqual((period["first_day"], period["last_day"], period["to_date"]),
                         ("2026-10-01", "2026-10-31", False))

    def test_a_month_follows_the_viewers_time_zone(self):
        # November in Asia/Tokyo (UTC+9) starts 2026-10-31 15:00 UTC.
        self.stack.add_events([
            working_time(at("2026-10-31 14:59:00"), 1_000, user=ALICE, org=ORG),
            working_time(at("2026-10-31 15:00:00"), 20_000, user=ALICE, org=ORG),
        ])
        self.stack.refresh()
        self.assertEqual(self.total_ms(period="month", month="2026-11", tz="Asia/Tokyo"), 20_000)
        self.assertEqual(self.total_ms(period="month", month="2026-10", tz="Asia/Tokyo"), 1_000)
        self.assertEqual(self.total_ms(period="month", month="2026-11", tz="UTC"), 0)

    def test_no_later_month_than_the_current_one_can_be_chosen(self):
        self.assertEqual(self.refused(period="month", month="2026-12")["error"], "bad_request")
        # in Asia/Tokyo it is already 2026-11-14, still November; in Pacific/Kiritimati (UTC+14) too
        self.overview(period="month", month="2026-11", tz="Pacific/Kiritimati")

    def test_a_malformed_month_is_refused(self):
        for month in ("2026-13", "2026-1", "November", "2026-11-01", "0000-05", "1969-12", "2026-00"):
            with self.subTest(month=month):
                self.refused(period="month", month=month)

    def test_year_is_the_last_twelve_months_ending_today(self):
        self.stack.add_events([
            working_time(at("2025-11-13 23:59:00"), 1_000, user=ALICE, org=ORG),
            working_time(at("2025-11-14 00:00:00"), 20_000, user=ALICE, org=ORG),
            working_time(at("2026-11-13 15:10:00"), 300_000, user=ALICE, org=ORG),
        ])
        self.stack.refresh()
        self.assertEqual(self.total_ms(period="year"), 320_000)
        period = self.overview(period="year")["period"]
        self.assertEqual((period["first_day"], period["last_day"]), ("2025-11-14", "2026-11-13"))

    def test_there_is_no_custom_range(self):
        for query in ({"period": "custom"}, {"period": "day"}, {"period": ""}):
            with self.subTest(**query):
                self.refused(**query)

    def test_an_unknown_time_zone_is_refused_and_a_legacy_alias_is_accepted(self):
        self.refused(tz="Mars/Olympus")
        self.overview(tz="Asia/Calcutta")


class WorkingTimeOverThePeriodTest(PeriodCase):
    def series(self, **query) -> dict:
        return self.overview(**query)["time_series"]

    def test_a_week_has_one_bucket_per_day_with_empty_days_as_zero(self):
        self.stack.add_events([
            working_time(at("2026-11-09 10:00:00"), 600_000, user=ALICE, org=ORG),
            working_time(at("2026-11-09 23:30:00"), 60_000, user=BOB, org=ORG),
            working_time(at("2026-11-13 08:00:00"), 300_000, user=ALICE, org=ORG),
            working_time(at("2026-11-13 08:00:00"), 999_000, user=ALICE, org=8),  # another organization
        ])
        self.stack.refresh()
        series = self.series(period="week")
        self.assertEqual(series["unit"], "day")
        self.assertEqual(
            [(bucket["start"], bucket["working_time_ms"]) for bucket in series["buckets"]],
            [("2026-11-07", 0), ("2026-11-08", 0), ("2026-11-09", 660_000), ("2026-11-10", 0),
             ("2026-11-11", 0), ("2026-11-12", 0), ("2026-11-13", 300_000)],
        )

    def test_days_follow_the_viewers_time_zone(self):
        # 2026-11-12 16:00 UTC is 2026-11-13 01:00 in Asia/Tokyo, where today is 2026-11-14.
        self.stack.add_events([working_time(at("2026-11-12 16:00:00"), 600_000, user=ALICE, org=ORG)])
        self.stack.refresh()
        tokyo = {bucket["start"]: bucket["working_time_ms"] for bucket in self.series(tz="Asia/Tokyo")["buckets"]}
        utc = {bucket["start"]: bucket["working_time_ms"] for bucket in self.series(tz="UTC")["buckets"]}
        self.assertEqual(list(tokyo), [f"2026-11-{day:02d}" for day in range(8, 15)])
        self.assertEqual((tokyo["2026-11-13"], tokyo["2026-11-12"]), (600_000, 0))
        self.assertEqual((utc["2026-11-12"], utc["2026-11-13"]), (600_000, 0))

    def test_a_zone_offset_by_half_an_hour_still_gets_one_bucket_per_day_adding_up_to_the_period(self):
        self.stack.add_events([
            working_time(at(f"2026-11-{day:02d} {hour:02d}:10:00"), 1_000 * day + hour, user=ALICE, org=ORG)
            for day in range(5, 14) for hour in (0, 12, 18, 23)
        ])
        self.stack.refresh()
        body = self.overview(tz="Asia/Kolkata")
        buckets = body["time_series"]["buckets"]
        self.assertEqual([bucket["start"] for bucket in buckets], [f"2026-11-{day:02d}" for day in range(7, 14)])
        self.assertEqual(sum(bucket["working_time_ms"] for bucket in buckets),
                         sum(row["working_time_ms"] for row in body["by_annotator"]["rows"]))

    def test_an_earlier_month_has_one_bucket_per_calendar_day(self):
        self.stack.add_events([working_time(at("2026-10-31 12:00:00"), 600_000, user=ALICE, org=ORG)])
        self.stack.refresh()
        buckets = self.series(period="month", month="2026-10")["buckets"]
        self.assertEqual(len(buckets), 31)
        self.assertEqual((buckets[0]["start"], buckets[-1]["start"]), ("2026-10-01", "2026-10-31"))
        self.assertEqual(buckets[-1]["working_time_ms"], 600_000)

    def test_year_is_laid_out_in_monday_weeks(self):
        self.stack.add_events([
            working_time(at("2025-11-14 10:00:00"), 1_000, user=ALICE, org=ORG),  # Friday, the first day
            working_time(at("2025-11-16 23:00:00"), 2_000, user=ALICE, org=ORG),  # Sunday, same week
            working_time(at("2025-11-17 00:00:00"), 30_000, user=ALICE, org=ORG),  # Monday, the next week
            working_time(at("2026-11-09 00:00:00"), 400_000, user=ALICE, org=ORG),  # Monday of this week
            working_time(at("2026-11-13 15:00:00"), 5_000_000, user=ALICE, org=ORG),  # today
        ])
        self.stack.refresh()
        series = self.series(period="year")
        self.assertEqual(series["unit"], "week")
        buckets = series["buckets"]
        # the first week is cut at the period's first day; the others start on Mondays
        self.assertEqual(len(buckets), 53)
        self.assertEqual([(b["start"], b["working_time_ms"]) for b in buckets[:3]],
                         [("2025-11-14", 3_000), ("2025-11-17", 30_000), ("2025-11-24", 0)])
        self.assertEqual((buckets[-1]["start"], buckets[-1]["working_time_ms"]), ("2026-11-09", 5_400_000))
