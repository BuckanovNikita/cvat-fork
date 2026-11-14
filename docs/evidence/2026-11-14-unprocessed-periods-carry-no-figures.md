# Unprocessed periods carry no figures, 2026-11-14

Ticket 14 of the defect fixes. The Team Analytics service answered a read of a
period that is not fully processed with its partial figures and
`processed: false`; only the page held them back, so a maintainer or a script
calling the service directly got partial totals. This file records what was
changed and what was run.

## The change

- `team_analytics/withheld.py` holds the rule: after an endpoint has built its
  answer as usual, `withhold(answer, envelope)` sets every field outside the
  named envelope to null.
- Overview (`endpoints/overview.py`): `period`, `filters` and `processed` stay;
  every other section is null as a whole (rows and all), except `operations`,
  which keeps its legacy flags (`legacy`, `partly_legacy`, `cutover`, `shapes`)
  with `working_time_ms`, `active_time_ms` and `rows` null.
- Full-view list (`endpoints/list.py`): `period`, `processed`, `by` and the
  legacy flags stay; `total`, `rows` and `hotkey_actions` are null.
- Details table (`endpoints/details.py`): `by`, `page_size`, `processed`,
  `technical_accounts` and the legacy flags stay; `page`, `total`, `rows` and
  `project_ids` are null.
- Trends (`endpoints/trends.py`): a bucket not fully processed has, in every
  line, a point with `legacy` and `hotkey_recorded` kept and every value null.
  Buckets that are processed are unchanged.
- The page (`service.ts`) takes such an answer as ready (the loaders used to
  refuse an overview without `by_annotator`, a list or table without `rows`),
  and three readers that ran before the "not processed" gate no longer read
  rows that are not there: the selected annotator's label, and the project
  name lookups of the full view and of the details table.
- `docs/fork-specification.md` states the rule. It listed no limit about
  partial figures through a direct call at the base of this branch (searched
  for "partial", "processed" and "direct call"), so there was none to remove.

## Test first, and seen to fail

Seam 1 (`verify/team_analytics_service.sh`, default ClickHouse image), each
run on a frozen copy of the tree it names.

- Red: the changed tests against the unchanged service (`fb65b41` with the
  test files of `31ae5ee`). `tests.test_history.FillTest`,
  `tests.test_full_view.ProcessedTest`, `tests.test_details_table.ProcessedTest`,
  `tests.test_trends.ProcessedTest`: the four no-figures tests failed on the
  figures the service still sent (the overview's `headline` was
  `{'annotators': 1, 'projects': 1}`, the list's `total` and `rows` were
  `{'count': 0, ...}` and `[]`, the table answered page 1 with its row, the
  unprocessed trend points held zeros). The new test that a fully processed
  list keeps its figures passed.
- First green run, on `85bcfae` with the corrected test files (before the
  repairs below): 7 errors, all in existing tests that read figures of a
  period not fully processed (listed below).
- Green: the modules that read the overview, the list, the details table or
  the trends (`test_access`, `test_bounding_boxes`, `test_class_change`,
  `test_concurrency`, `test_creation_methods`, `test_cutover`,
  `test_details_table`, `test_entry_point`, `test_full_view`, `test_history`,
  `test_http`, `test_isolation`, `test_keyboard_mouse`, `test_model_saved_boxes`,
  `test_operations`, `test_periods`, `test_projects_filters`,
  `test_query_values`, `test_refresh`, `test_sessions`, `test_trends`,
  `test_working_time`), on the tree of `adf4d38` (ticket 18 merged): all
  passed. Run again on the tree of `92e75c9` (tickets 17 and 20 merged): all
  passed.

Seam 3 (`node --test verify/team_analytics_page.cjs`), with answers shaped as
the service now sends them:

- Red at `89bcbb8` (the new tests, page unchanged): 8 of 212 failed. The full view of an unprocessed list (by annotator, by project,
  split by project, hotkeys) said the list could not be loaded or failed on
  `null.rows`; the page with an unprocessed overview showed the error panel;
  the overview with an annotator filter failed on `null.rows`; the details
  section said details could not be loaded. The details card and the trends
  card already held up with nulls; their tests passed before the fix.
- Green after the fix: every test passed, none skipped.

## Existing tests that read an unprocessed period

Several seam 1 tests read figures of a period that the stored history did not
yet cover, as a device and not as their subject. Under this change they get
no figures. They were repaired without moving what they exercise:

- `tests/support.py`: `Stack.keep_refreshing_since` now ends with
  `Stack.settle()`, which steps the service until it waits, as a service
  running since that moment would have computed its history. Past days are
  then history's computation; today's hours stay the refresh's.
- Tests whose subject is a refresh-window edge compute history first and run
  their refreshes after it, so the hours they read are still written by the
  refresh under test: `test_operations.TimePerOperationTest` (window start),
  the three `test_sessions.RefreshEdgeTest` tests.
- `test_refresh`: before the first refresh the overview is asserted to carry
  no figures; "the trailing 48 hours only" adds the event before the window
  late, after history has computed its day, so a refresh that does not reach
  it leaves it out of a processed period.
- `test_history.RefreshPriorityTest`: steps until the week is processed
  before the timed part, with older days still to do.
- After ticket 18, with a one-hour window, `test_bounding_boxes.AlignmentWindowTest`
  and `test_creation_methods.RedoAcrossWindowEdgeTest` step the service until
  it waits after their two refreshes (the ticket 18 note): the history step
  computes today's hours up to 10:00 and the refresh the hour from 10:00, so
  the edge between two computations stays.

## Not verified

- The whole seam 1 suite was not run on this branch; it runs on the
  integration branch after the package's tickets are merged. The second
  ClickHouse image was not run.
- The legacy flags of an unprocessed answer still come from the partial
  totals (whether the scope has job work in the period), as before.
- Trend candidates' working time still sums all twelve buckets, processed or
  not; the spec names only bucket values.
