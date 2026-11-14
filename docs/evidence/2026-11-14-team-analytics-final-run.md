# Team Analytics final run, 2026-11-14

The final run of Team Analytics (ticket 18) on the disposable test stack, with both images
built from the integrated branch. This file records what ran, the outcomes and what remains
unverified. It separates live outcomes from tests with supplied boundaries. Times are UTC.

## Revisions and images

| Item | Value |
| --- | --- |
| Branch | `ta/18-final-run-docs`, from `feat/team-analytics-page` at `c3ee2e3` (tickets 01-17 merged) |
| Evidence run tree | `bfffb23` (all product fixes and tooling committed before the run) |
| UI image | `cvat/ui:v2.82.0-team-analytics-ta18-5b38488`, `./build-ui.sh` at `5b38488`; `cvat/` unchanged between `5b38488` and `bfffb23` |
| Service image | `cvat/team-analytics:v2.82.0-ta18-bfffb23`, `./build-team-analytics-service.sh` at `bfffb23` |
| Stack | upstream chart of `02bd74f` (v2.82.0), namespace `cvat-ta-it-nkt`, `http://localhost:8490`, refresh every 60 s, technical account `ta-bot` |

## Evidence run

```bash
export TA_UI_IMAGE=cvat/ui:v2.82.0-team-analytics-ta18-5b38488 \
       TA_SERVICE_IMAGE=cvat/team-analytics:v2.82.0-ta18-bfffb23
verify/team-analytics-stack/run.sh down   # start from no namespace
TA_SCREENSHOT_DIR=<dir> verify/team-analytics-stack/run.sh up   # fresh stack
verify/team-analytics-stack/run.sh up     # the same stack again
verify/team-analytics-stack/run.sh down
```

| Step | Time | Outcome | Log |
| --- | --- | --- | --- |
| `up` on a fresh namespace | 04:36:57-04:44:04 | exit 0, "final run passed" | [`run-up1.log`](2026-11-14-team-analytics-final-run/run-up1.log) |
| `up` again on that stack | 04:44:04-04:50:21 | exit 0, "final run passed"; volume not loaded twice, a new project annotated; the restarted service refreshed within a minute | [`run-up2.log`](2026-11-14-team-analytics-final-run/run-up2.log) |
| `down` | 04:50:21-04:51:14 | exit 0, "nothing of cvat-ta-it-nkt remains" | [`run-down.log`](2026-11-14-team-analytics-final-run/run-down.log) |

The logs leave out rollout progress lines. The screenshots in the same directory come from the
first `up`. The figures below come from the first `up`; the second run showed the same counts.
Earlier runs on kept stacks (02:40-04:30) found the defects listed below. An earlier `up`,
`up`, `down` sequence, before the shutdown fix, failed on the second `up`.

### Real UI in a real browser (live)

`ta-worker-c` signed in through CVAT's login form in headless Chrome. The run drove the
annotation view of a new 4-frame job with DevTools input events:

- two rectangles: one from the controls sidebar, one with the draw-mode hotkey `N`;
- two drags of the first box;
- Ctrl+C and Ctrl+V, then a click to place the copy;
- Ctrl+B on the second box, accepting the dialog's 3 copies;
- Ctrl+2 to change the first box's class;
- Delete on the pasted box;
- `F F F D D` and Ctrl+S;
- leaving through the header's Tasks link, with the browser closed 5 s later.

Outcomes:

- The UI sent three `POST /api/events` requests, and the stock server answered each with 201.
- The events table held the following rows for the project:

  | Rows | Payload |
  | --- | --- |
  | `draw:object` x2 | `shape_type rectangle`, `rectangle_count 1`, `object_type shape`; `input_method` `mouse` and `hotkey` |
  | `drag:object` x2 | the same fields plus `object_ref 1`, `frame 0`, `input_method mouse` |
  | `paste:object` (count 1), `propagate:object` (count 3, `rectangle_count 3`), `delete:object` (count 1) | `input_method hotkey` |
  | `debug:info` `team_analytics:class_change` (count 1) | `input_method hotkey` |
  | `team_analytics:input_summary` | hotkeys `SWITCH_DRAW_MODE_STANDARD_CONTROLS 1, COPY_SHAPE 1, PASTE_SHAPE 1, PROPAGATE_OBJECT 1, SWITCH_LABEL_2 1, DELETE_OBJECT_STANDARD_WORKSPACE 1, NEXT_FRAME 3, PREV_FRAME 2, SAVE_JOB 1`; mouse `controls_sidebar 1, popup 1, canvas 2, modal 1, other 1` |

  The hotkey counts are exactly the keys the script pressed.
- Stock logging was unchanged. These client scopes arrived: `load:job`, `load:workspace`,
  `click:element`, `copy:object`, `change:frame`, `save:job` and the operation events. Every
  client row kept its `client_id`. CVAT wrote 2 `send:working_time` rows (20 071 ms). The save
  wrote `create:shapes` with 5 rectangles: the 2 drawn and 3 propagated, the pasted box being
  deleted.
- **Detector use was not driven by the real UI.** The stack has no model function (nuclio is
  off). The run sent one `team_analytics:model_creation` record (count 3, `rectangle_count 2`)
  through the real `POST /api/events` as `ta-worker-c`. Its payload took the shape of the class
  change record the real UI had just sent. The server accepted it, and it arrived in ClickHouse.
- `ta-bot`, a technical account, saved 3 rectangles through `PATCH
  /api/jobs/{id}/annotations?action=create`, which wrote a server `create:shapes` row.

The service figures for that project came from its scheduled refresh, 27 s after the load.
They were read with `project=<id>`, `period=week` and All shapes:

| Figure | Expected (from the script's actions) | Service | Page |
| --- | --- | --- | --- |
| Creation / drawn / pasted / propagated | 6 / 2 / 1 / 3 | 6 / 2 / 1 / 3 | 6 / 2 / 1 / 3 |
| Alignment (two drags of one box in a row) | 1 | 1 | 1 |
| Class change / deletion | 1 / 1 | 1 / 1 | 1 / 1 |
| Model, All shapes (3 saved by ta-bot + 3 by detector) | 6 | 6 | 6 |
| Model, Bounding boxes (3 + 2 rectangles) | 5 | 5 | - |
| Saved boxes: total / ta-worker-c (from the job's annotations API) | 8 / 5 | 8 / 5 | - |
| Sessions | 1 | 1 | 1 |
| Working time (sum of `send:working_time`) | 20 071 ms | 20 071 ms (by annotator, by project, current trend week) | - |
| Hotkey actions; every action count (full list) | 12; as pressed | 12; equal | 12 |
| Started by hotkey / mouse | creation 5/1, alignment mouse only, class change and deletion hotkey | same | - |

Operation shares added up to 100 %.

### Loaded volume (synthetic events, live service)

`final_run.py load-volume` wrote 7 000 rows directly into the `events` table for organization
`ta-org-v`. They cover 100 annotators with long names and 40 real CVAT projects with names
of 100+ characters, one work session per annotator per week over ten weeks. The events are
`load:job`, `draw:object`, an input summary, `send:working_time` and `create:shapes`.
**These figures come from loaded events, not from real UI actions.** The expected values
were computed from the generator's design:

- current week: 100 annotators, 40 projects, 100 sessions, 9 000 000 ms of working time and
  session time; 300 drawn at 30 s each (290 under Bounding boxes, after 10 polygons); 290
  saved boxes; 697 hotkey actions, 100 mouse actions, 600 canvas clicks. All matched.
- history: the service processed the older days by itself (status `history.complete`), and
  all trend buckets were `processed`.
- trends: weekly working time per Monday week matched for the scope and for two compared
  annotators.
- full list: 100 annotators; details by project: 40 rows; top 8 plus a remainder by
  annotator (92) and by project (32).

### Access with real accounts (live)

Each case called five endpoints (`overview`, `status`, `trends`, `details`, `list`) with the
account's own CVAT session:

| Account, organization | Result |
| --- | --- |
| `ta-admin`, none / `ta-org-a` / `ta-org-v` | 200 |
| `ta-owner`, `ta-org-a`; `ta-maintainer`, `ta-org-a`; `ta-maintainer-b`, `ta-org-b`; `ta-bot` (maintainer), `ta-org-c` | 200 |
| `ta-supervisor`, `ta-worker`, `ta-outsider`, `ta-worker-c` in their own or the named organization | 403 `forbidden` |
| `ta-maintainer-b` and `ta-owner-b` naming `ta-org-a` (another organization) | 403 `forbidden` |
| `ta-outsider` and `ta-worker` with no organization | 403 `forbidden` |
| `ta-maintainer` with no organization | 403 `organization_required` |
| anonymous | 401 |

With `ta-org-a` named, `ta-admin` saw only that organization's annotators. The tracer check
(ticket 03) repeated the overview matrix and its browser part: the header link for
`ta-maintainer`, no link and "not available" for `ta-worker`, and 403 from the service.

### Page in a browser (live)

The page was checked in headless Chrome at 1400 px:

- **Period:** Year gave 53 weekly bars and `period=year` in the address. Week came back.
- **Filters:** a project row set `project=` and showed 3 annotators. An annotator row set
  `annotator=` and showed "1 of 3". Both chips cleared, back to 100.
- **Full view:** the annotators full view (`view=annotators`) listed 100 rows without
  overflow. "Back to overview" returned.
- **Trends:** two annotators were added from the search, giving two lines and a legend per
  chart.
- **Length:** the overview was 3186 px with 100 annotators and 40 projects, against 2678 px
  for `ta-org-c` (one annotator, several projects).
- **Overflow:** no element stuck out of its card, and the page did not scroll sideways.
- **Project names:** the long names came from CVAT (`id` filter), not `Project #id`.

At 400 px the page stayed within the window and its 13 cards formed one column. The three
wide tables scrolled sideways, and nothing stuck out of its card, with the trend values
tables opened. CVAT's own header keeps the app 1025 px wide, which is upstream behaviour on
every page.

### Service stopped (live)

With the Deployment scaled to 0, `ta-owner-c` saw the error panel ("Team analytics could not
be loaded"). `ta-worker-c` drew a box in another job and saved it: one shape on the server and
no error notice. The service was then scaled back and rolled out.

## Defects found and fixed in this ticket

All four were fixed test-first. Each red was observed before its fix.

1. **Closing input summary waited for the periodic save** (`3b29af0`). The summary written as
   the annotation view closed reached the cvat-core logger after the closing save had read its
   buffer. It left only with CVAT's next periodic save (90 s), so closing the tab sooner lost it.
   This was seen live: without the 90 s wait, no summary arrived. Red in seam 2:
   `verify/team-analytics-logging/closing-summary.test.cjs` renders `annotation-page.tsx`, and
   the job logger goes through cvat-core's real plugin wrapper; nothing was POSTed at close.
   The evidence run closed the browser 5 s after leaving the job, and the summary arrived.
2. **Cards did not stack in a narrow window** (`e456e22`). CVAT's `#root` minimum width of
   1024 px kept the page at two columns. The browser check at 400 px failed with card lefts
   32/513 and passed after the fix. Seam 3 renders no layout, so the only test is the live
   browser check.
3. **Opened trend values stuck out of a narrow card** (`5b38488`). The live browser check at
   400 px failed with the values opened and two annotators compared, and passed after the fix.
4. **A stopped replica could hold up refreshes for 30 minutes** (`bfffb23`). In a repeated `up`
   (04:13-04:16), the service had been restarted by the previous run's service-down phase. It
   then ran no refresh for more than two minutes ("0 scheduled refreshes since the load"), and
   the tracer check failed. Static reading showed the cause: the process died on SIGTERM
   without running `finally`, so a step in progress left its lease claim live for
   `LEASE_S` = 1800 s. That namespace was already deleted, so the leftover claim itself was
   not observed. A later diagnostic `up`, `up` on a kept stack passed, with no unreleased
   claim in `refresh_lock`, which fits a race. Red in seam 1: `tests/test_shutdown.py` stops a
   replica busy with 300 days of history with SIGTERM, and a second replica processed no day
   in 30 s ("4 not greater than 4"). After the fix the service finishes the step, releases the
   lease and exits; the test and `tests.test_entry_point` pass, and so did the final `up`,
   `up`, `down`.

## Checks with supplied boundaries (tests)

| Check | Result |
| --- | --- |
| Seam 2, `node --test verify/team_analytics_logging.cjs` | 53 tests, all pass (after `3b29af0`) |
| Seam 3, `node --test verify/team_analytics_page.cjs` | 191 tests, all pass |
| Type check, `tsc -p cvat-ui/tsconfig.json` | exit 0 (workspace packages resolve to the main checkout's sources) |
| Seam 1, `verify/team_analytics_service.sh` (default `cvat/clickhouse:23.12.2-debian-11-r0`) at `c3ee2e3` (before the shutdown fix) | 230 tests, OK, exit 0 |
| Seam 1 at `bfffb23` (with `tests/test_shutdown.py`), run alongside the final stack runs | 231 tests, OK, exit 0 (1810 s alongside the stack) |
| Ruff on `final_run.py`, `stack_api.py` | clean; `seed_users.py` was already unformatted before this ticket and was left as it was |

## Independent access review

Three reviewers who did not write the code read the access rules at `e7da2e4` (lenses:
identity, scope, edge), and a separate skeptic checked each finding. The fixes are on
branch `ta/review-fixes`; each was reproduced by a failing test first unless noted.

| Finding | Severity | Resolution |
| --- | --- | --- |
| A1 = A6: request bodies never read, so a body on a kept-alive connection was answered as a second request | medium (server-side desync confirmed; a figure leak depends on the proxy and was not shown) | Resolved in `5cb3705`: bodies up to 64 KiB are read and dropped, anything else closes the connection after the one answer. `tests/test_http.py` failed first (two answers on one socket). |
| A2: with no organization, only CVAT's first page of 100 memberships was read | low | Resolved in `d2e4463`: asked once per reading role with CVAT's `role` filter. The stand-in CVAT now pages like CVAT. The test with 101 newer worker memberships failed first (`forbidden`). |
| A3: a malformed 200 from CVAT gave 500 | low (hardening) | Resolved in `d2e4463`: answer shapes are checked before caching; a bad one is 503 `cvat_unavailable`. Ten malformed answers failed first (500, or 200 for `groups: "administrators"`). |
| A4: status `history` shows the instance-wide first day and day counts to an organization maintainer | low | **Accepted, not fixed.** The spec does not scope processing state by organization, and no names, identifiers or figures of another organization are shown. |
| A5: no committed isolation tests for details, list, trends and the filter echo, or for instance scope beyond the overview | low (test gap) | Resolved in `26d9d0d` (`tests/test_isolation.py`). The tests pass on the code. Every test except the refusal matrix failed with the organization clause removed from the read files. |
| A7: after a refusal from trends, details, list or status the page kept its figures | low | Resolved in `90eceae`: a 401 or 403 from any endpoint puts the page into the matching refusal state. The seam 3 cases failed first. |

## Code review findings

A static code review of `e7da2e4` found ten findings (C1-C10). Outcomes on `ta/review-fixes`:

| Finding | Resolution |
| --- | --- |
| C1 request bodies on keep-alive (= A1) | Fixed, `5cb3705` |
| C2 refresh lease left live after a failure, never renewed | Fixed, `ec8512e`: released on every failure path, failed release retried, lease renewed while a step runs. `tests/test_lease.py` failed first (all three cases). |
| C3 legacy decided by "any shape-tagged row in scope" | Fixed with a recorded cutover (see the fork specification), `08b3803`. `tests/test_cutover.py` and `verify/team-analytics-page/cutover.test.cjs` failed first. |
| C4 unbounded project-name and details-search URLs | Fixed, `02b845e`: names in requests of 100 ids, the project search sends one table page of ids. Seam 3 and seam 1 tests failed first. |
| C5 model creation recorded before creation succeeded | Fixed, `936bf9a`: recorded only when the create thunk returns created ids. Seam 2 test failed first. |
| C6 page filters survived an organization switch | Fixed, `25a201c`: the address names the filters' organization. Seam 3 tests failed first. |
| C7 input counts lost when the tab closes | **Recorded as a limitation** in the fork specification. cvat-core's only page-exit path sends a fixed bandwidth record; the regular log and save are asynchronous and not `keepalive`, so delivery on `pagehide` needs a cvat-core change. Not reproduced live. |
| C8 class change consumed a pending drawing's input method | Fixed, `ee901c2`. Seam 2 test failed first. |
| C9 `str.isdigit()` accepted Unicode digits (500) | Fixed, `2868e00`: every identifier, page, id list and month takes ASCII digits only. `tests/test_query_values.py` failed first. |
| C10 a ClickHouse client per query, files re-read, discovery per request | Fixed, `e7da85e`. Behaviour is unchanged and seam 1 passes. Measured on the seam 1 ClickHouse, the median overview latency went from 2130 ms to 2027 ms: the client setup cost was small there. `tests/test_concurrency.py` (parallel requests during a refresh) passes with old and new code. |
| Housekeeping: Python bytecode not ignored | Fixed, `101b03f` |

## Rerun after the review fixes, 2026-11-14

Everything above this section was observed in the first run (04:36-04:51 UTC, images built at
`5b38488`/`bfffb23`). This section is the rerun with the fixes of `ta/review-fixes`.

| Item | Value |
| --- | --- |
| Code tree | `08b3803` (all fix commits; later commits are documentation only) |
| UI image | `cvat/ui:v2.82.0-team-analytics-review-fixes-08b3803`, `./build-ui.sh` at `08b3803` |
| Service image | `cvat/team-analytics:v2.82.0-review-fixes-08b3803`, `./build-team-analytics-service.sh` at `08b3803` |
| Run | `run.sh up` with both images set, 07:33:12-07:38:52 UTC, exit 0, "final run passed" ([`run-up-review-fixes.log`](2026-11-14-team-analytics-final-run/run-up-review-fixes.log)) |

This was an **in-place upgrade**, not a fresh stack. The orchestrator had just brought the
stack up from the main checkout with the first run's images, and `up` from the fix branch
rolled the UI and service Deployments to the new images on that namespace. The volume and
tracer data were already loaded, so they were not loaded again; a new project was annotated
through the real UI. **The stack was left running at the user's request** (namespace
`cvat-ta-it-nkt`, `http://localhost:8490`), so no `down` followed.

Checks made by hand on the upgraded stack, as `ta-admin`:

- `status` reported `cutover: {at: 2026-09-11T08:00:00+00:00}`, the first shape-tagged hour of
  the loaded volume.
- The current week of `ta-org-a` reported `legacy: false`, `partly_legacy: false` and
  `shapes: bounding_boxes`. Its work is only the tracer's untagged events. Under the old rule
  this scope read as legacy (finding C3).
- A `POST` to the overview with a body was answered 405 once through the proxy.

Tests at `08b3803` (supplied boundaries):

| Check | Result |
| --- | --- |
| Seam 1, `verify/team_analytics_service.sh` | 259 tests, OK (1343 s) |
| Seam 2, `node --test verify/team_analytics_logging.cjs` | 55 tests, all pass |
| Seam 3, `node --test verify/team_analytics_page.cjs` | 205 tests, all pass |
| `node --test verify/task_progress.cjs` with `BROWSER_BIN` set to Chrome | 21 tests, all pass |
| Type check, `tsc -p cvat-ui/tsconfig.json` | exit 0 |

Not verified after the fixes: input counts lost on tab close (C7) are a recorded limitation
and were not reproduced live; request desync behind a keep-alive production ingress was
not tested live (seam 1 shows one answer per request on the service itself); the C10
latency gain was measured on the seam 1 ClickHouse only.

## Second review round, 2026-11-14

An independent reviewer read the review-fix commits and reported three findings, all from
reading the code. Branch `ta/review-fixes-2`, from `feat/team-analytics-page` at `dca82a3`.
Each finding was reproduced by a test that failed before its fix.

| Finding | Outcome |
| --- | --- |
| F1 (medium): two replicas could hold the refresh lease at once. A renewal that failed for longer than the lease let the claim expire. Another replica then claimed it, and the first replica's next renewal brought its old claim back. | Fixed, `a130954`. A replica can lose the lease when its renewals fail or come back too late. It then stops its step before its next write, so it marks no hours. A claim renewed after it expired is never live again (`lock_holder.sql`). The wait for a hanging renewal at release is bounded at 2 s. New `LostLeaseTest` in `tests/test_lease.py` (3 tests) failed first. |
| F2 (low): an empty period that holds the cutover showed the partly-legacy notice | Fixed, `f241f98`. The overview, details and full view answer `partly_legacy` only when the scope has job work. The page shows neither notice when there is no job work. The seam 1 test failed first for all three endpoints, and so did the seam 3 test in `cutover.test.cjs`. |
| F3 (low): the cutover was provisional while history was processed | Fixed, `2c900d3`. The cutover is stored in table `cutover` of the totals database. The step that first stores a shape-tagged hour finds the cutover before it marks its hours. It runs one aggregate over the raw tagged operation events, bounded above by that hour plus one hour. Requests read the stored value, which never moves. `WhileHistoryIsProcessedTest` in `tests/test_cutover.py` (2 tests) failed first: it reported 2026-11-12 instead of 2026-11-02, and then 2026-10-25 after an earlier event was added. |

Tests at `2c900d3` (supplied boundaries):

| Check | Result |
| --- | --- |
| Seam 1, `verify/team_analytics_service.sh` | 265 tests, OK (1392 s) |
| Seam 1, `tests.test_lease` and `tests.test_cutover` on `clickhouse/clickhouse-server:23.11-alpine` | 17 tests, OK (after the lease test change below) |
| Seam 2, `node --test verify/team_analytics_logging.cjs` | 55 tests, all pass |
| Seam 3, `node --test verify/team_analytics_page.cjs` | 206 tests, all pass |
| `node --test verify/task_progress.cjs` with `BROWSER_BIN` set to Chrome | 21 tests, all pass |
| Type check, `tsc -p cvat-ui/tsconfig.json` | exit 0 |

After the run, the hanging-renewal test got an 8 s lease, so a stalled renewal leaves room for a
whole refresh on a slow host. This changed the test only. `tests.test_lease` passed again on both
ClickHouse images.

The stack was upgraded in place, without `down`. `run.sh up` ran from the fix branch with UI image
`cvat/ui:v2.82.0-team-analytics-review-fixes-2-2c900d3` and service image
`cvat/team-analytics:v2.82.0-review-fixes-2-2c900d3`, both built at `2c900d3`. It ran
08:39:42-08:44:46 UTC and ended with exit 0 and "final run passed"
([`run-up-review-fixes-2.log`](2026-11-14-team-analytics-final-run/run-up-review-fixes-2.log)).
The stack was left running.

Checks by hand on the upgraded stack:

- Before the upgrade, the totals' earliest shape-tagged hour and the raw events' earliest tagged
  operation hour were both 2026-09-11 08:00. After it, table `cutover` held one row,
  2026-09-11 08:00, stored at 08:40:24 UTC during the upgrade. As
  `ta-admin`, `status` reported `cutover: {at: 2026-09-11T08:00:00+00:00}` and history complete.
- As `ta-admin`, ta-org-a over the year (which holds the cutover) reported
  `partly_legacy: true`. The same year with a project filter matching no work reported
  `legacy: false`, `partly_legacy: false` and zero working time.

Not verified live: lease loss and a hanging renewal (seam 1 only, with injected renewal failures);
the cutover being found while history is still incomplete (the stack's history was already
complete, so the live value only shows that the stored value matches the earlier one).

## Review of the second round, 2026-11-14

An independent reviewer read `dca82a3..4ee92c0` (merged as `6acd883`). It ran the lease's
deadline logic against a fake clock and read the rest; no ClickHouse was available to it, so
the SQL was not executed in this review. No medium or high defect was found. Three low
findings about the stored cutover are recorded, not fixed:

| Finding | Outcome |
| --- | --- |
| The cutover is found only once a shape-tagged hour reaches the stored totals, so a processed period can read as legacy until then (recent work all in 3D jobs, which are never tagged) | Recorded as a known limit in `docs/fork-specification.md`. The trigger was the brief's choice; the earlier read had the same gap. |
| After an upgrade that adds the `cutover` table, every period reads as legacy until the first refresh by a new replica | Recorded as a known limit. On the stack the row was stored during the upgrade itself. |
| A tagged event that arrives after the cutover was stored, or one with a wrong date, can leave a wrong value for good | Recorded with the correction: delete the row from the `cutover` table and the next refresh finds it again. This correction was not exercised. |

Found sound by reading: two replicas cannot write at once, the placement of the lease
checks, the lease holder rule, the renewal thread and SIGTERM, the empty-period rule across
overview, details and list, and the finder's definition of a shape-tagged event.

## What remains unverified

- Detector use from the real UI with a deployed model function: only its record was sent,
  through the real API.
- A removed member and CVAT being unreachable, live. Seam 1 covers both with supplied CVAT
  answers.
- Late events two days old, live. Seam 1 covers the daily recount; the live volume loaded
  before any history day was processed.
- Firefox, Safari and real high-DPI screens; only headless Chrome ran.
- Events through Vector under load; the run sent a few thousand rows.
- The production Ingress route (`team-analytics/k8s/ingress.yaml`); the stack routes through
  its own proxy.
- Mouse zone `header` covers the annotation top bar only, so a click on CVAT's global header
  counts as `other`. This is as built (ticket 13), noted for the review of wording.
- The 400 px check looks at the page only. CVAT's header keeps its upstream width.
- Several call sites were not driven live: resize, selection delete, multi paste, class
  change by mouse (sidebar, context menu, attribute mode), tracks and shapes other than
  rectangles. Seam 2 covers them with the real cvat-core logger and a recording transport.
- "Event logging as before" was judged from the stock client scopes, `client_id`, CVAT's
  `send:working_time` rows and the 201 answers. No side-by-side run of the stock UI image was
  made.
- The synthetic volume went straight into ClickHouse, bypassing CVAT's events API and Vector.
- On the kept exploration stack, the login form timed out once right after a manual swap of
  the frontend image. A retry passed. The evidence run did not repeat it.
