# The cutover at start and its move: checks of ticket 17 (2026-11-14)

Ticket 17 of the defect fixes makes the service look for the cutover in the recorded
events when it starts and in the daily check, and lets a stored cutover move to an earlier
hour. The cost of that search was measured first and is in
[`2026-11-14-cutover-search-cost.md`](2026-11-14-cutover-search-cost.md). This file holds
the test runs.

Every run below is seam 1, `verify/team_analytics_service.sh`: the service's read interface
over HTTP against a real ClickHouse in a throwaway container, with a stand-in for CVAT's
identity answers. Nothing here ran against a real CVAT or on the Kubernetes stack.

## Before the change

The new tests of `tests/test_cutover.py` on the service as it was at `e1d92b8`, on
`cvat/clickhouse:23.12.2-debian-11-r0`: 19 tests, 5 of them failed.

| Test | Result on the old service |
| --- | --- |
| A service started on recorded tagged events knows the cutover on its first answer | failed: status said no cutover |
| Tagged work that has not reached the stored totals yields a cutover | failed: no cutover while history was days away from the tagged day |
| Two replicas that find the cutover at once leave one value | failed: neither replica had a cutover after its start |
| An earlier tagged event that arrives later moves the cutover at the next daily check | failed: after the next daily check the cutover and the labels were unchanged |
| A wrongly early event is undone by removing it and then the stored value | failed at its first step: the wrongly early event did not move the cutover |
| A later tagged event never moves the cutover | passed, as before |
| No cutover is found at start or by the daily check without a shape-tagged event | passed, as before |
| A service started before CVAT created its events table still starts | passed, as before |
| A table keeps the legacy content of the rows it lists while its own filter is set | passed: it pins existing behaviour |
| The ten tests that were there before and did not change | passed |

The test that said a stored cutover does not move was replaced by the two tests of the
move.

## After the change

The eleven modules are `tests.test_cutover`, `test_history`, `test_lease`, `test_refresh`,
`test_status`, `test_entry_point`, `test_shutdown`, `test_concurrency`, `test_trends`,
`test_details_table` and `test_full_view`: the cutover and the legacy labels, history and
the daily check, and the start of the service.

| Tree | Run | Image | Result |
| --- | --- | --- | --- |
| `a202616`, the change on `e1d92b8` | the eleven modules | `cvat/clickhouse:23.12.2-debian-11-r0` | 103 tests, OK |
| `a202616` | `tests.test_cutover` | `clickhouse/clickhouse-server:23.11-alpine` | 19 tests, OK |
| `5ff847f`, after merging `feat/team-analytics-page` at `34ed347` (tickets 16 and 19 among others) and adding one test | the eleven modules | `cvat/clickhouse:23.12.2-debian-11-r0` | 111 tests, OK |

The branch was merged once more with `feat/team-analytics-page` at `789a1e8` (tickets 21
and 24). That merge changed nothing under `team-analytics/`, in the seam's runner or in
CVAT's ClickHouse setup script, so the last row stands for the head.

What the cutover tests show, each through status and the answers of the read interface:

- A service started on recorded tagged events reports the cutover on its first answer,
  with no refresh made. The envelope of an overview answer carries it too.
- With tagged work days before the trailing hours and only untagged work since, a
  processed week is labelled by the cutover while history is still days away from the
  tagged day, so no tagged hour is in the stored totals.
- Two service instances started at the same moment on the same databases both report
  the one cutover, straight after the start and again after a refresh, all of history and
  the daily check.
- An earlier tagged event that arrives after the cutover was stored changes nothing at
  the next ten-minute refresh. After the next daily check the cutover is that event's
  hour; October, which was legacy, holds the cutover and is partly legacy; the week
  between the two hours is no longer legacy; October's bounding boxes count the late box.
- A later tagged event leaves the cutover where it was, after a daily check and after a
  restart.
- With no shape-tagged event there is no cutover after a start and after the daily check,
  and a week and a month with job work are legacy.
- With CVAT's `events` table absent the service still starts and answers status with no
  cutover; once the table and a tagged event exist, the cutover is found.
- A tagged event dated a week ahead is not taken as the cutover at start, and the refresh
  that then stores tagged work of today finds today's hour.
- The correction the fork specification now describes was exercised: deleting the rows of
  the `cutover` table alone brought the wrongly early hour back at the next start;
  deleting the event and then the rows gave the right cutover again at the next start,
  and after the next daily check the labels of October were as before the wrong event.

## Two tests that were not seen to fail first

Each ran once against a throwaway copy of the service with one line changed, to see that
it can fail. The copies were never part of the tree.

- `test_a_table_keeps_the_legacy_content_of_the_rows_it_lists_while_its_own_filter_is_set`
  pins existing behaviour and passes before and after the change. Against a copy in which
  the details table and the full-view list apply their own dimension's filter: 4
  failures, one per table and dimension, each with an empty row list where the project
  or the annotator was expected.
- `test_an_event_dated_in_the_future_is_not_the_cutover` was written after the change.
  Against a copy in which the search does not stop at the end of the current hour: it
  failed, with the event's hour a week ahead reported as the cutover.

## The seam 1 runner's volumes

`verify/team_analytics_service.sh` removed its containers without their anonymous volumes,
and `clickhouse/clickhouse-server:23.11-alpine` declares two, so every run on that image
left both behind. Since `b7cb367` the runner removes them with the containers (`docker rm
-v`). Shown once at `b7cb367`, holding the shared lock so that no other run made or removed
volumes meanwhile: 67 unused volumes before a run of `tests.test_working_time` on that
image (4 tests, OK), 67 after, none new. The 67 were there before and were left alone.

## Not verified

- The whole seam 1 suite. Only the eleven modules above ran, by the ticket's
  instructions; the suite is run on the integration branch after the tickets of this
  package are merged.
- The second image at the head. `test_cutover` ran on it at `a202616` only, before the
  merge and before the test of the event dated in the future; the other modules did not
  run on it at all.
- Anything on the Kubernetes stack or against a real CVAT: the start of a pod on a loaded
  volume, the liveness probe during the search, an in-place upgrade read at once for the
  cutover. The upgrade read is on the list of the final run.
- A search that fails at start for a reason other than a missing `events` table.
- A search that fails inside the daily check. By the code it is tried again by the next
  daily check and the check stays recorded; no test makes it fail.

## After the independent review

The independent review of tickets 17, 18 and 20, and what its follow-up changed, are
recorded in "Independent review" in
[`2026-11-14-refresh-lease-two-minutes.md`](2026-11-14-refresh-lease-two-minutes.md). For
this ticket: the search at start and in the daily check now runs within the limits
committed here, enforced by ClickHouse; a search that fails inside the daily check now
ends the step without it and is exercised by a test; the first answer is shown on the
service started as `python -m team_analytics`. The statement now reads the events in
order and stops at the first match, so the figures of
[`2026-11-14-cutover-search-cost.md`](2026-11-14-cutover-search-cost.md) were measured on
the earlier aggregate. The new statement's cost at that scale was measured on 2026-11-15,
in the section of that date in the same file.
