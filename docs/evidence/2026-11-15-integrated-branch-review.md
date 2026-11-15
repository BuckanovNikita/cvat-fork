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

The fix first broke one thing, found by reading after the full run: the trend candidates sum
working time from the first processed bucket up to now, which was sound only while processed
buckets always ran up to now. During the waiting hour they would have summed the current,
unprocessed bucket. An assertion added to the same test (Alice's candidate `working_time_ms` is
null meanwhile) failed on `f276c3a9`: it was 7 minutes, the 1 minute of the current week
included. The fix (`fecba133`) counts the
candidates only from buckets processed up to now, as before.

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
one refresh, on `b16aa045`, which changes only the status section): the overview sent nine
figure reads (`list_rows.sql` twice, headline, sessions, time series, input, creation methods,
saved boxes, operations), the
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
lease (`History.next_day`, left without a caller, went in `6b43e581`). The day found is the day
computed, and a day another replica computed meanwhile is
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
unchanged: `tests.test_lease` passed on 23.11 and in the full run on the default image, and
`tests.test_refresh` and `tests.test_shutdown`, which take the lease on ClickHouse's own clock
(no supplied clock), passed on 23.11 on `6b43e581`. Each of the six rule-guarding tests that ticket 20 named still fails when its rule is
broken in a frozen copy of `e2108aa2`: claim not released on failure, release not retried, no
renewal, lease always held, expired claim revived, unbounded renewal join.

### The whole suite

- Seam 1, all of it, on `e2108aa2` on the default image: 318 tests, OK.
- After the candidates fix, on `6b43e581`: `tests.test_history tests.test_trends tests.test_status
  tests.test_isolation tests.test_full_view tests.test_details_table tests.test_cutover` on the
  default image, 123 tests, OK; `tests.test_lease tests.test_refresh tests.test_shutdown
  tests.test_history` on 23.11, 44 tests, OK.
- The whole suite did not run on 23.11; the orchestrator reruns it on both images after the
  merge. The merge of the integration branch that followed changed no service file.

## What the review did not look at

- Nothing was run: no test, no stack, no measurement. Every finding was a reading, and two of
  them (5 and 6) proved weaker when measured.
- The imported Helm chart and the `verify/` harness were only spot-checked.
- Production volume and live load: overview latency, the cutover search past the measured
  size, and the cost of reads on a large scope.
- The page's own behaviour during the hour a short window leaves waiting (the month picker and
  the trends gate), beyond what status sends.

## Review of the follow-ups (2026-11-15)

Who and how: a fresh agent that wrote none of them reviewed the three last follow-ups (the
logging merge `ae6bbfca`, the delivery merge `e59e841d` and the code review merge `de181cd7`)
at `de181cd7`, reading and probing with doctored bundles and renders. It changed no tracked
file, built no image and created nothing in the cluster. A second agent fixed what it found on
branch `fix/last-review`.

### The five findings and what was done

1. The bundle check could be fooled by a link on the `rules` directory (each policy reported
   equal, the bundle holding none) and by two spellings of one name (`rules/issues.rego` and
   `rules//issues.rego`). Fixed (`b2fbc3e5`): `verify/policy_bundle.sh` refuses any entry that is
   neither a regular file nor a directory, wherever it sits, compares names after normalising
   them, and refuses a name that leaves the bundle. Before: both reviewer bundles passed
   `policy_bundle.sh check` and `run.sh check-bundle`. After: both refused ("NOT FILE rules
   (link …)", "TWICE rules/issues.rego"), on both commands, in both orders of the doubled name.
   The real fork bundle (from `cvat/server:v2.82.0-fork-policies`) passes; the real stock bundle
   and the earlier review's mixed, old, one-file, link, doubled, empty and non-archive bundles
   fail as before, each with its earlier reason; `check-stock cvat-v2.82.0-widened` passes the
   stock bundle and fails the fork one on the two policies only.
2. While an hour waits for the history step under a window shorter than a day, status reports
   no month and no complete week. Recorded, no code change. The specification's sentence now
   says such a period reads as "not processed yet", and the limit says what a person sees for
   that hour: no month offered and the trends card saying none are ready, while an earlier month
   or week asked for directly still answers as processed.
3. The hotkeys list skipped its filter check for a period not processed: a bad annotator,
   project or shapes value got 200 with null figures. Fixed test first (`b04c09f6`): the values
   are judged before the processed branch. The new test in `tests.test_full_view` failed on the
   integration tip for the three hotkeys cases of the unprocessed Year ("(200, None) != (400,
   'bad_request')") and passes after the fix, with the processed week and the two other kinds.
4. The render guard judged only where objects land and what they pull. Fixed (`e7b12b32`): it
   also refuses, in any object at any depth, a Service other than ClusterIP or with external IPs,
   host networking, PID or IPC, a host port, a host path volume, privileged mode, added
   capabilities, and a RoleBinding to a ClusterRole or to a subject other than a ServiceAccount
   of the stack's namespace. The genuine render holds none of these (its Services are all
   ClusterIP, headless ones included; its only binding is Grafana's, to its own Role and service
   account; its security contexts drop capabilities), so nothing the chart needs is refused.
   `apply_service` and `apply_proxy` now pass their manifests through the guard before applying
   them; `run.sh render-service` and `render-proxy` print them. The README says what the guard
   refuses in place of "nothing cluster-wide is created". Shown: the reviewer's LoadBalancer,
   host Pod and cluster-admin binding renders refused, each naming every item; NodePort and
   ExternalName Services, host PID and added capabilities in a CronJob, and a binding to a User
   refused; a headless Service and a service account without a namespace accepted. The genuine
   render (`run.sh render`, then `check-render`) is accepted, and so is that render with the
   service's and the proxy's manifests appended. Each launcher render alone, read by kubectl
   and judged as `apply_service` and `apply_proxy` judge it (no backend check), is accepted;
   a copy with the service's type set to NodePort, and one with the proxy's set to
   LoadBalancer, are refused. The reviewer's other renders that its report
   lists as refused are still refused; three it does not list (a repeated key, an empty
   namespace, a tagged image without a pull policy) are accepted, as kubectl reads them.
5. A failed check in `build-server.sh` removed the image under `IMAGE`, even for a failure
   unrelated to it. Fixed (`fe4e3b9b`): on failure the script removes only an untagged build of
   this run, tags nothing, saves nothing, exits 1, and says that the tag still names the earlier
   build, with its ID, which this run did not check. Shown on throwaway tags (no pull, no push,
   build network off, all removed afterwards): a base made from the stock image with a changed
   `utils.rego`, and an earlier good image under a throwaway target tag. The integration tip's
   script exited 1 and removed the target tag; the new one exited 1 ("DIFFERS rules/utils.rego"),
   the target kept `4b38c649ae96`, and the failed build was removed.
   `cvat/server:v2.82.0-fork-policies` kept `4b38c649ae96` throughout, and the new script,
   run once at the end on the real base, rebuilt it with both checks passing and the same ID,
   `4b38c649ae96`. BUILD-1 and the upgrade procedure describe the new behaviour.

### What held

The reviewer found sound the history state under a waiting hour, the worker under the lease,
the figure queries' envelopes, the lease statements' stamps, the navigation hotkey's budget, the
guard against every earlier doctored render, `check-issue-policies` on both sides, the password
on standard input and the restart rule (its report lists how each was established).

### Not checked

No stack was started: the guard on the service and the proxy inside a real `up` did not run.
`SAVE=1` was not run. The waiting hour of finding 2 was not seen in a browser. The whole seam 1
suite was not rerun here, only `tests.test_full_view` on the default image.

## Review of the final run's tooling (2026-11-15)

Who and how: a fresh agent that wrote none of it reviewed `de181cd7..236b3878` (the final run,
ticket 27, and its follow-ups) at `236b3878`. It read the code, the documents and the run's
logs, called the render guard and the bundle check on doctored inputs, and looked at the
screenshots. It ran no stack and changed nothing. It found seven Low findings and nothing that
makes a product figure wrong or lets a fix step pass with its fix absent on the paths the run
reached. They were answered on branch `fix/security-review` (the security review's branch),
while its own live stack was up (see `2026-11-15-security-review.md`, part four), and each fix
in the tooling was shown by rerunning its step on that stack.

1. **`unprocessed` left its marker event when a judged read failed** (the delete sat in a later
   `finally`). Fixed (`b3140b78`): the marker is deleted in a `finally` that covers everything
   from its INSERT on, the wait after the lease's release included. Shown: `run.sh check-fixes
   unprocessed` passed (marker on 2026-09-09, week bucket 2026-09-07 and month bucket 2026-09
   not processed with null values for both callers, lease released after 8 s, the days
   processed 25 s later), and the events table then held 0 rows of the marker. The failure
   path itself was not provoked.
2. **Its trend judgement dropped out when no weekly bucket held the probe day.** Fixed
   (`b3140b78`) by failing, not skipping: the step now fails when either trend step has no
   bucket for the probe day. The probe's placement is unchanged, so on a kept stack whose
   reruns walk the probe out of the twelve weeks the step fails and says so. Shown on the same
   run: both buckets were found and judged.
3. **The held-key judgement and two documents.** Recorded, documents changed (`2ef266b2`). With
   every key-down moving a frame, only the press at the last frame tells the counting rule from
   its absence. The final run's evidence now carries dated notes saying that part one's
   `gestures` row and its 13:10 restatement are the plan, superseded by part two and ticket 13
   (no fewer frames than key-downs required; the grabbed drag allowed at most once). The fork
   specification says the held-key step was meant to catch a stale last shown frame and what
   the run showed instead.
4. **The end-to-end `check-fixes` account mixed runs.** Fixed in the evidence (`2ef266b2`): it
   now quotes `fix-all.log` (marker 2026-09-06, bucket 2026-08-31, 30 s, 3 052 events) and
   gives the single-step runs' figures in brackets where they differ.
5. **The seed check accepted volume annotators in every organization.** Fixed (`b3140b78`):
   they are accepted only in the volume organization (`ta-org-v`, or the one `TA_VOLUME_ORG`
   names). Shown by the cheapest path, `stack_api.py seed` (the check alone) on the stack after
   its volume load: `ta-org-v` held its owner and 100 volume annotators, `ta-org-a`, `-b` and
   `-c` exactly their seeded members, and the check passed. A misplaced annotator was not
   staged.
6. **The guard let an Ingress through and refused a harmless key.** Of the reviewer's three
   cases, judged with the guard as it now is: the wildcard-host Ingress is refused (the Ingress
   allowlist of the security review, `295658cc` and `c30e08fa`); a ConfigMap with a data key
   `hostPath` is still refused, a false refusal that stays; `allowPrivilegeEscalation: true` is
   still accepted. The guard's docstring and the stack README now list the host checks as the
   only ones of their kind and say both of the latter (`2ef266b2`).
7. **Two judgements passed on what they did not see.** Fixed (`b3140b78`): `gestures` refuses
   a hotkey in the summaries under a name not pressed, copy and paste (`COPY_SHAPE`,
   `PASTE_SHAPE`) aside; `technical-project` first requires the same annotator search to find
   `ta-worker-c`, who works in that organization in `up`'s final run, before it accepts that the
   search for `ta-bot` finds nothing. Shown: `check-fixes technical-project` passed
   (`ta-worker-c` found, `ta-bot` not listed, the project's row as before), and `check-fixes
   gestures` passed with summaries `SAVE_JOB 2, COPY_SHAPE 1, PASTE_SHAPE 1, NEXT_FRAME 66`, 66
   frames shown, figures creation 5, drawn 3, pasted 2, deletion 0, alignment 5, hotkey actions
   70.

Not done here: ticket 27 is not ticked again; nothing in it changed.

### Second pass of the review of the final run's tooling (2026-11-15)

The same reviewer, under the same rules, reviewed `236b3878..02e5423d`: the answers above
and the answers to the security review (`docs/evidence/2026-11-15-security-review.md`). It
changed no tracked file and used no cluster.

- All seven findings are answered as this section says, checked against the code and the
  logs of the reruns. No answer broke a step. For finding 1 the failure path itself was not
  provoked; for finding 5 a misplaced annotator was not staged.
- One note on finding 7: the search for `ta-worker-c` finds that person only while `up`'s
  final run lies within the last seven days, so on an older kept stack `technical-project`
  fails, not passes.
- The security answers: the idle limit applies to each wait on the socket, so it does not
  cut a slow answer while the service computes; it would cut a proxy that keeps idle
  connections longer than 120 s. The reviewer ran `tests.test_http` on the default
  ClickHouse image (`Ran 5 tests`, `OK`), and read that the test fails without the fix. The
  guard accepted the genuine chart, service, proxy and Ingress renders in the replay and on
  the live `up`. One more harmless false refusal: a ConfigMap data key named `volumes`.
- No new finding.
- Not checked: an `up` on a stack already in place with the changed guard (the render does
  not depend on the data); the idle defaults of the proxies of a real deployment.

With this, ticket 27's review criterion is met: the policies
(`docs/evidence/2026-11-14-policies-role-floor.md`) and the access rules and reads were each
reviewed on their own, the refresh, the page, the logging, the delivery and the whole branch
were reviewed in turn, the security review covered the fork's own work as a whole, and this
review covered what came after the last of those. Every finding is fixed or recorded in the
evidence of its review.
