# Code review of the integrated branch, and its follow-up (2026-11-15)

## The review

Who and how: the `code-review` skill at its high level, run by the orchestrator's agent on
`feat/team-analytics-page` at `a6e09c6d` against local `main` (`6cedd049`), over
`git diff main...feat/team-analytics-page` (296 files). The fork's own product code was read
line by line: the service's Python and SQL, the page and logging UI, the policies, and the
build, mirror and lint scripts. The imported Helm chart and the `verify/` harness were
spot-checked. Nothing was run: every finding below came from reading.

What it found sound: every UI consumer checks `processed` before it reads a figure that can now
be null; the canvas fires the group notice and the grabbed drag synchronously, so the grabbed
object's drag is marked correctly; the policies' stock filter comes back with the worker-role
floor; the two helper policies and the ClickHouse setup file equal upstream's; no project
convention is broken.

## The nine findings, as reported

1. `team-analytics/service/sql/read/history_state.sql`. With a refresh window shorter than a
   day, `missing` becomes today whenever an hour leaves the window, and
   `HistoryState.ready_from` then drops to `trailing_from`, so the whole processed history
   reads as unprocessed. With a six-hour window and all older days computed, every hour,
   until the next history step has recomputed that hour, `covers()` is false for every
   period, `days()` gives 0 of N, status shows percent 0, no period is offered, and the
   overview, list, details and trends withhold every figure. The page flips to "not
   processed" and the progress bar to 0 % once an hour, and stays there if the today-step
   keeps failing. Only today's gap is unprocessed, but the single `missing` date cannot say so.
2. `team-analytics/service/team_analytics/history.py`. Once a cutover is stored, the
   daily-check search (and the one at every start, `service.py`) scans every record before the
   stored cutover each time. At scale it reaches its limit and fails every day, so moving the
   cutover earlier never happens; every daily check spends up to 60 s of ClickHouse time under
   the refresh lease, and every start waits up to about 28 s before the port opens. Searching
   only records recorded since the last search would bound it.
3. `team-analytics/service/team_analytics/endpoints/overview.py`. The overview runs every
   section's figure queries and only then nulls them when `processed` is false; `list.py`,
   `details.py` and `trends.py` do the same, although the history state is read first. During a
   multi-day history fill each page load runs about ten aggregates and discards them all.
4. `team-analytics/service/team_analytics/rows.py`. The overview's by-annotator and by-project
   sections each run the full `read/list_rows.sql` (per-row operations, creation methods,
   Model) where two light working-time aggregates used to run, and use only the top eight rows
   and their operation times. A rows-only variant would serve.
5. `cvat/cvat-ui/src/utils/team-analytics-logging/input-summary.ts`. A frame-navigation hotkey
   is credited only if `changeFrameAsync` calls `frameRequested()` within 100 microtasks of the
   shortcut. A handler whose chain passes an extra await (a plugin wrapper, a cvat-core change)
   or waits on the network starts the change after the turn ends, and the press is silently not
   counted. Passing the hotkey through the dispatched frame change would make this
   deterministic.
6. `team-analytics/service/team_analytics/worker.py`. `step()` calls `History.next_day()` and
   then `process_next()`, and both run `control/history_next_day.sql`: the same query twice,
   back to back, on every history step.
7. `team-analytics/service/team_analytics/status/history.py`. The status section calls
   `load_state(request.sql, request.now)` directly instead of the per-request
   `request.history()`: two read paths for the history state.
8. `team-analytics/service/sql/control/history_next_day.sql`. The today / trailing /
   today_done logic is duplicated almost line for line between that file and
   `read/history_state.sql`; a fix to one is easy to miss in the other, and then the worker and
   the readers disagree.
9. `team-analytics/service/sql/control/lock_claim.sql`. The test-only clock seam
   `ifNull({now:...}, now64(...))` is repeated twice per statement in `lock_claim.sql` and
   `lock_release.sql` and once in `lock_holder.sql`; one alias per file would keep the two
   stamps of a statement provably from one value.

## The follow-up

On branch `fix/code-review`, from `a6e09c6d`, one commit per finding. Each finding was first
checked against the code; what was run is said with it. Seam 1 ran in Docker
(`verify/team_analytics_service.sh`) on frozen copies of the tree, on the default ClickHouse
image (`cvat/clickhouse:23.12.2-debian-11-r0`) unless 23.11 is named. Probes are throwaway test
modules or test files added to a frozen copy only and never committed; what they print is
quoted here.

### Finding 1: true; fixed

Checked by a test first. The new
`tests.test_history.ShortWindowTest.test_an_hour_waiting_for_the_history_step_leaves_the_days_before_today_processed`
uses a one-hour window and events on 20 October, 5 November and 13 November. It settles, then
moves the clock to 16:05 and refreshes, so the hour from 15:00 waits for the history step. On
the tree before the fix (`b16aa045` plus the test) it failed: status said 0 of 25 days and
0 %, which is the reported effect. The fix (`c5357ae3`): `read/history_state.sql` now returns
the newest missing day before today apart from `waiting_from`, where today's waiting hours
begin. `HistoryState.covers(start, end)` keeps a period or trend bucket that ends at or before
`waiting_from` processed. The day count keeps the days before today. A period that holds the
waiting hours reads as not processed, as story 6 requires. `ready_from` keeps its meaning, the
earliest moment from which every hour up to now is processed. With the fix the test passes:
24 of 25 days, 96 %, October processed with its 2 minutes, the eleven earlier trend weeks
processed and the current one not, the week not processed, then complete after the history
step. Every other test of ticket 18 and the refresh review's midnight and two-clock tests pass
unchanged.

Left as it was, and written into the fork specification's short-window limit: status still
counts `earliest_month`, `complete_weeks`, `ready_from` and `ready_from_day` from `ready_from`.
So for that hour no month is offered and no complete week is counted, and the page hides
trends. `earliest_month` cannot express "earlier months, but not the current one", and the page
reads it that way, so changing it would have needed page changes.

### Finding 2: true; recorded

CVAT's `events` table (`cvat/components/analytics/clickhouse/init.py` and its two migrations)
has `timestamp`, when the event happened as the client stamped it, and nothing that says when
the row arrived. Part metadata is not a sound substitute, since parts merge. The remedy cannot
be built on that table, so no code changed. Both call sites log the failure with
`log.exception` (`service.py` `setup`, `history.py` `check`), and nothing else reports it. The
fork specification's limit now says that, once a cutover is stored on an instance past the
limit, every search at start and in every daily check is stopped there, that an earlier record
then never moves the cutover, and that the only sign is the logged error. The 2026-11-15
measurement in `2026-11-14-cutover-search-cost.md` stands as the size at which this begins.

### Finding 3: true; fixed

Checked by a probe that counted the SQL files each read sends (a month not processed, after
one refresh, tree `b16aa045`): the overview sent ten figure reads (`list_rows.sql` twice,
headline, sessions, time series, input, creation methods, saved boxes, operations), the
hotkeys list `list_hotkeys.sql`, and the details table `details.sql` beside
`details_scope.sql`. The fix (`0346b65a`) decides `processed` first. The same probe on the fixed
tree: the overview sends only `overview_operations.sql`, whose own read gives the legacy flags.
The hotkeys list sends no figure read. The details table sends only `details_scope.sql`, which
gives the flags. Left as they were, because their envelope comes from their figure read: the
list's rows by annotator and by project (`list_rows.sql` gives `legacy`, `job_work` and
`all_shapes`), and the trends (each point's `legacy` and `hotkey_recorded`, and `shapes`, come
from `trends.sql`; the candidates name everyone even while no bucket is processed). The guards
are the withholding tests, which pass unchanged and assert every key:
`tests.test_history.FillTest.test_a_period_not_wholly_processed_carries_no_figures_only_its_envelope`,
`tests.test_full_view.ProcessedTest`, `tests.test_details_table.ProcessedTest` and the trends'
withholding test. There is no red test: the answers did not change, only the reads behind them.

### Finding 4: true; recorded

The probe above shows `list_rows.sql` run twice by the overview. Removing the per-row methods
and Model inside the same statement would need a switch in the statement's text, and ClickHouse
does not promise to skip the parts the switch turns off. A second, lighter statement would be
the forked query the spec rules out, since one shared read is what keeps the overview's split
equal to the full view's. So no code changed. The fork specification lists the cost as known
and not measured at scale. Overview latency is out of this spec's scope.

### Finding 5: partly true; recorded

Measured at seam 2 with a probe built on `verify/team-analytics-logging/frame-navigation.test.cjs`.
It delays the search key's annotation search by extra awaits, or by one `setTimeout(0)`, and
reads the summary:

| Delay before the search answers | Frame change | `SEARCH_FORWARD` counted |
| --- | --- | --- |
| none, 1, 3, 10 or 40 extra awaits | 3 to 6 | 1 |
| 120 extra awaits | 3 to 6 | 0 |
| one timer | 3 to 6 | 0 |

So one extra await, a plugin wrapper say, does not lose the press: the turn lasts 100
microtasks. A chain past that, or any wait outside the microtask queue (the network, a timer),
does lose it. The fork specification's frame-navigation limit already named the network wait
for frame meta. It now also says that a few more awaits change nothing, and that a longer
chain, or one that waits outside the microtask queue, counts nothing. No code changed: the
deterministic remedy needs hooks in upstream handlers.

### Finding 6: true, but the query is cheap; fixed

The probe counted `control/history_next_day.sql` twice in every history step on `b16aa045`. A
second probe ran the statement over a million raw events: the server's summary reports
5 rows read in about 8 ms, for `read/history_state.sql` too. The count and the earliest
timestamp come from table metadata, so "the same scan twice" overstates it. The fix
(`11465f99`) is small anyway: the worker takes the lease and then runs `process_next`, which
reads the next day once. If there is no day, the daily check runs when it is due, in the same
lease. The day found is the day computed, and a day another replica computed meanwhile is
found done, as before. The probe counts one run per step on the fixed tree. One cost moved: a
step with nothing to do now claims the lease to find that out, about once per refresh
interval. The fork specification says so. Guards, all passing unchanged: ticket 18's step
counts (`FillTest.test_with_the_default_window_today_takes_no_step_of_its_own`, the order
tests) and `RefreshPriorityTest`, whose second test holds one replica inside `process_next`
under the lease.

### Finding 7: true; fixed

`status/history.py` called `load_state` itself (seen in the code). It now takes
`request.history()` (`b16aa045`), so `service.Request.history` is the only caller of
`load_state`. The answers do not change, so no red test is possible. `tests.test_status`,
`tests.test_history` and `tests.test_isolation` are the guards, and they pass.

### Finding 8: true; recorded with a pin

`team_analytics/sql.py` substitutes only database names (`string.Template`). It has no way to
share a fragment between files, and none was added. Each of the two files now names the other
and the parts that must stay in step (`a63998a8`).
`tests.test_history.ShortWindowTest.test_an_hour_that_left_the_window_is_computed_again_before_it_reads_as_processed`
pins their agreement: a one-hour window, an hour just out of the window, read before and after
the history step. Shown on frozen copies of `e2108aa2`, each with one file broken:
- the readers never see today waiting (`read/history_state.sql`): the test fails, since the week
  reads as processed with 1 minute where 3 are due (`60000 != 180000`);
- the worker never computes today (`control/history_next_day.sql`): the test fails, since the
  week never reads as processed.

### Finding 9: true; fixed

`lock_claim.sql` and `lock_release.sql` now take the expression once, as `stamp`, through
`INSERT ... SELECT` (`e2108aa2`). `lock_holder.sql` uses it once and is unchanged. Behaviour is
unchanged: `tests.test_lease` passed on 23.11 (11 tests) and in the full run on the default
image. Each of the six rule-guarding tests that ticket 20 named still fails when its rule is
broken in a frozen copy of `e2108aa2`: claim not released on failure, release not retried, no
renewal, lease always held, expired claim revived, unbounded renewal join.

### The whole suite

Seam 1, all of it, on tree `e2108aa2` (the branch head before these documents) on the default
image: 318 tests, OK. On 23.11 only `tests.test_lease` ran; the orchestrator reruns the whole
suite on both images after the merge.

## What the review did not look at

- Nothing was run: no test, no stack, no measurement. Every finding was a reading, and two of
  them (5 and 6) proved weaker when measured.
- The imported Helm chart and the `verify/` harness were only spot-checked.
- Production volume and live load: overview latency, the cutover search past the measured
  size, and the cost of reads on a large scope.
- The page's own behaviour during the hour a short window leaves waiting (the month picker and
  the trends gate), beyond what status sends.
