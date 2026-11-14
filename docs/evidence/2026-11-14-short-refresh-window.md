# A short refresh window and processed history, 2026-11-14

The Team Analytics service recomputes a trailing window of hours every ten
minutes (`TEAM_ANALYTICS_REFRESH_WINDOW_HOURS`, 48 by default) and computes
each whole day before today once, in its history step. With a window shorter
than a day, the hours of today before the window belong to neither. This file
records what ticket 18 of the defect fixes found there and what it changed.

Every run below is seam 1 (`verify/team_analytics_service.sh`): the service's
read interface against a real ClickHouse in Docker, on one host. Each run used
a frozen copy of the tree it names.

## Before the fix

The defect was first known by reading. `read/history_state.sql` looked for a
day that is not processed only among the days up to yesterday, and
`control/history_next_day.sql` offered the history step only those days. So
with a one-hour window nothing computed today's hours before the current one,
and once the days before today were done, history read as complete.

It was then seen in a run of the integration branch at `e1d92b8` with only the
new tests added (the tree of commit `167598c`), on the default ClickHouse
image: 5 tests, 4 failed. The tests set a one-hour window and a clock of
Friday 2026-11-13 15:20 UTC, so the ten-minute refresh covers 15:00 onwards.

| Test in `tests.test_history` | Result | What it saw |
| --- | --- | --- |
| `ShortWindowTest.test_an_event_from_earlier_today_is_counted_or_its_period_reads_as_not_processed` | failed | After the first refresh the week read as processed, and the 16 minutes of work stamped 10:00 were not in it (`0 != 960000`). |
| `ShortWindowTest.test_an_hour_that_left_the_window_is_computed_again_before_it_reads_as_processed` | failed | After the refresh at 16:05 the week read as processed with one of three minutes (`60000 != 180000`). The event stamped 15:55, after that hour's last refresh, was in no figure. |
| `ShortWindowTest.test_status_offers_no_period_until_todays_earlier_hours_are_computed` | failed | Status said history was complete after the first refresh. |
| `ShortWindowTest.test_todays_earlier_hours_come_first_then_the_days_before_most_recent_first` | failed | "Ready from" began at today's midnight: today's earlier hours were never a step of their own. |
| `FillTest.test_with_the_default_window_today_takes_no_step_of_its_own` | passed | With the default window the service did nine working steps and then waited. This test pins what must not change. |

## The change

- The history step treats today as its newest day while hours of today lie
  before the latest ten-minute refresh and have not been computed since they
  left the window. It computes those hours with the same calculation files as
  a refresh, ahead of the older days, and records how far it got in a new
  table of the totals database, `history_today`.
- Until it has done so, today is the day that is not processed, so "ready
  from" is the start of the latest refresh and no period that begins before it
  is offered.
- When the window moves on by an hour, that hour is computed once more by the
  history step. This is what counts the work of an hour's last minutes, which
  the hour's own refreshes had not seen.
- A window of a day or longer never begins after today's midnight, so it
  leaves no such hours, and the step and the state are as before.

The first version of the fix (`e6eeebc`) read the record of how far the step
got only when it lay in the reader's own day. By reading, two replicas whose
clocks straddle midnight would then disagree, and the one still in the old day
would repeat the step without a pause until its date changed. `996e486` takes
the newest record whatever its date. This case was reasoned, not run.

## After the fix

| Tree | ClickHouse image | Test modules | Result |
| --- | --- | --- | --- |
| `e6eeebc`, the first version of the fix | default (`cvat/clickhouse:23.12.2-debian-11-r0`) | `test_history`, `test_refresh`, `test_status`, `test_bounding_boxes`, `test_creation_methods`, `test_operations`, `test_trends`, `test_details_table`, `test_full_view`, `test_periods`, `test_cutover`, `test_shutdown`, `test_entry_point` | 164 tests, all passed |
| `20cef29`: `996e486` merged with the integration branch at `fabc1cb` | default | `test_history`, `test_refresh`, `test_status`, `test_bounding_boxes`, `test_creation_methods`, `test_shutdown`, `test_entry_point` | 71 tests, all passed |
| `20cef29` | `clickhouse/clickhouse-server:23.11-alpine` | `test_history`, `test_status` | 27 tests, all passed |

| `55c8de0c`: the integration branch merged again at `ad7cf9e7`, with ticket 19 | default | `test_history`, `test_creation_methods`, `test_bounding_boxes`, `test_operations` | 81 tests, all passed |

The first merge brought no change to the service, only a reformatting of
CVAT's ClickHouse setup script, which the tests use to create the events
database. The second brought ticket 19's operations rule and its change to the
redo test with a one-hour window, now
`RedoAcrossWindowEdgeTest.test_a_redo_just_after_a_window_edge_adds_nothing_to_the_creation_before_it`.
It passes beside this change, as does `AlignmentWindowTest`. The 23.11 image
was not run on that last tree.

What the final runs show, by test:

- The four `ShortWindowTest` tests that failed before pass. With a one-hour
  window the week reads as not processed after the refresh, and as processed
  with the event counted after the next step. The same holds for an hour that
  has just left the window.
- `FillTest.test_with_the_default_window_today_takes_no_step_of_its_own`
  passes before and after: nine working steps, then waiting.
  `FillTest.test_history_is_processed_one_day_at_a_time_most_recent_first` is
  unchanged and passes: the same days in the same order, step by step.
- The two tests that use a one-hour window to exercise the edge between two
  refreshes pass unchanged:
  `test_bounding_boxes.AlignmentWindowTest.test_an_alignment_across_a_window_edge_is_counted_once`
  and
  `test_creation_methods.RedoAcrossWindowEdgeTest.test_a_redo_just_after_a_window_edge_still_finds_the_creation_before_it`.
- The daily recount is untouched in the code (`History.check`,
  `control/history_changed_days.sql`) and its tests pass: the three of
  `LateEventTest` and the two of `LateEventInASessionTest`.
- `test_shutdown` and `test_entry_point` start the service as deployed
  (`python -m team_analytics`), which applies the schema with the new table.

## Supplied boundaries

- The tests supply the service's clock and move it by hand. The window is set
  in the service's configuration object, not through the environment variable.
- Events are inserted into ClickHouse's `events` table directly. CVAT's
  identity answers come from a stand-in.

## Not verified

- The whole seam 1 suite on the final tree. It is left for the integration
  branch, once the tickets of this package are merged, on both images. On the
  older image only `test_history` and `test_status` were run here.
- A deployed service with `TEAM_ANALYTICS_REFRESH_WINDOW_HOURS` below 24, and
  an upgrade of an existing totals database. The new table is created by the
  same idempotent setup as the others; the tests always start from empty
  databases.
- Windows between 2 and 23 hours. Only one hour was run. That a 24-hour window
  leaves no hours of today before it follows from the arithmetic and was not
  run.
- The loaded volume with a short window.

## What a short window still does not give

These follow from the design and were read, not run. None applies to a window
of a day or longer.

- An event that reaches ClickHouse after the history step has computed its
  hour is not counted until its day is computed as a whole, after midnight.
  Until then its period reads as processed without it. Under the default
  window the next ten-minute refresh counts such an event.
- For the moment between a refresh that moved the window and the history step
  that follows it, every period reads as not processed and the page shows its
  "being processed" state.
- A session or an operation that goes on across the window's edge after the
  hour before the edge was computed is stored again in the hour it ends, and
  the earlier hour keeps its stale part until it is computed again. This was
  so before the change as well.

## Changed

`team_analytics/history.py`, `sql/control/history_next_day.sql`,
`sql/read/history_state.sql`, the new `sql/schema/041_history_today.sql` and
`sql/control/history_record_today.sql`, and `tests/test_history.py`, all under
`team-analytics/service/`. `docs/fork-specification.md` is not changed: it did
not list this limit, at `e1d92b8` or in its history.

## After the independent review

The independent review of tickets 17, 18 and 20, and what its follow-up changed, are
recorded in "Independent review" in
[`2026-11-14-refresh-lease-two-minutes.md`](2026-11-14-refresh-lease-two-minutes.md). For
this ticket: the two behaviours listed above under what a reader should know are now
known limits in `docs/fork-specification.md`; the header of
`sql/schema/041_history_today.sql` now says that replicas whose clocks straddle midnight
can answer differently for a short time; and two tests cross midnight and use two clocks.
