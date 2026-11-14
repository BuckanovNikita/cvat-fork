# Overview bars split by operation, 2026-11-14

Ticket 23 of the defect fixes. The overview's bars for working time by
annotator and by project were single-colour; the split by operation existed
only in the full view. This file records what was changed and what was run.

## The change

- Service: `team_analytics/rows.py` holds the full view's row read
  (`read/list_rows.sql`), moved out of `endpoints/list.py`. The full view
  answers with it as before. `overview/by_annotator.py` and
  `overview/by_project.py` now take their rows from the same read, one read per
  section: the first eight rows with working time, each with the `operations`
  of its row in the full view, and a `rest` that adds `operations`, the parts
  of the rows it stands for summed row by row (Other as each row has it, so a
  row whose Other is clamped at zero adds zero). Each section carries `legacy`,
  the full view's flag for its rows. The overview's own `operations.legacy`
  applies both filters, so it can differ from these rows', which drop their own
  filter. `read/overview_by_annotator.sql` and `read/overview_by_project.sql`
  are gone.
- A period not fully processed: the overview withholds both sections whole
  (ticket 14), so the parts are null with them. No code was added for this.
- Page: `operations.ts` now holds the part and legend logic (`splitParts`,
  `operationParts`, `BarPart`), moved out of `full-view.tsx`. The full view and
  `cards/working-time-breakdown.tsx` both use it, so the overview draws a row
  with the same parts, order and colours as the full view, and drops class
  change in a legacy period as the full view does. A row without `operations`
  in a supplied answer is drawn whole in one colour. The rest line stays text,
  as in the prototype. `projects-filters.scss` draws the bar 16 px high with
  2 px gaps and no track, as the full view and the prototype do, and lets the
  legend wrap.

## Test first, and seen to fail

Seam 1 (`verify/team_analytics_service.sh`, default ClickHouse image
`cvat/clickhouse:23.12.2-debian-11-r0`):

- First red run: `tests.test_full_view.OverviewSplitTest` against the unchanged
  service (`35f820d` with the first version of the tests), on a frozen copy.
  Some subtests failed on the missing keys. The `shapes='all'` subtests and
  the rest test failed instead on `None` sections: those tests read the
  overview before its period was processed, which was a fault in the tests.
  It was fixed by processing the period before every overview read in the
  class, as `listed` does.
- Red, with the corrected tests (as committed in `37350e0`) against the
  `35f820d` service, on a frozen copy: every subtest of the rows, rest, empty
  rest and legacy tests failed on the missing keys (8 times
  `KeyError: 'operations'`, once `KeyError: 'legacy'`). The test that a period
  not fully processed carries no parts passed: it pins ticket 14's behaviour
  and is not a red-to-green test.
- First green run, on the service and page changes (`e232489`, `bb9f18a`), over the modules that
  read the overview or the full view (`test_access`, `test_concurrency`,
  `test_cutover`, `test_details_table`, `test_entry_point`, `test_full_view`,
  `test_history`, `test_keyboard_mouse`, `test_model_saved_boxes`,
  `test_periods`, `test_projects_filters`, `test_refresh`, `test_sessions`,
  `test_working_time`). Everything passed except the two test faults above and
  `test_entry_point`, which compared a whole row dict and now also met
  `operations`. That test was changed to compare the fields it asserts on, as
  `test_working_time`, `test_projects_filters` and `test_history` already were.
- Green: `test_full_view` and `test_entry_point` again on the merged tree
  (`e28b022`, with `feat/team-analytics-page` at `a423f82` merged, which
  touched neither the service nor the page): all passed. The other modules
  that read the overview, and the trends (`test_bounding_boxes`,
  `test_class_change`, `test_creation_methods`, `test_http`, `test_isolation`,
  `test_operations`, `test_query_values`, `test_trends`), on the same tree:
  all passed.

Seam 3 (`node --test verify/team_analytics_page.cjs`):

- Red: the new `split-bars.test.cjs` (3 tests) failed against the unchanged
  cards. Their legend was `['Working time']`.
- Green: every test passed, none skipped. The existing legend assertion in
  `projects-filters.test.cjs` now looks for the split's names instead of
  "Working time".

## The overview asks no extra question per row

This is a stated check, not a kept test, because it reads ClickHouse's query
log, which is a side channel. A throwaway test module, run once on a frozen
copy of the changed tree and not committed, flushed `system.query_log`. It
counted the finished queries that named the test's totals database during one
overview read, first with 4 rows across the two sections and then with 16.
Both reads gave the same counts: 12 queries, 3 of them matching the text of the
full view's row read. Each count probably includes the check's own earlier
counting query, whose text holds the same patterns, so the overview itself
likely makes 11 queries, 2 of them row reads (one per section). The equality is
what the check shows. Default ClickHouse image.

## Lint and type check

ESLint, stylelint and `tsc -p cvat/cvat-ui/tsconfig.json` (section 4 of
`docs/upstream-upgrade.md`) passed on every UI file touched, in the worktree
(the type check reads the workspace packages from the main checkout).
`ruff check team-analytics/service` passed. `prek run --all-files` passed on the
merged tree, with every hook run and none skipped.

## Not verified

- The look beside the prototype, at 1400 px and at 400 px, is ticket 27's
  browser run (what to look at is in the ticket).
- The whole seam 1 suite was not run on this branch, and neither was the second
  ClickHouse image.
- The overview now runs the full view's row read twice (once per section) in
  place of two working-time-only reads. Its cost at the benchmark's scale was
  not measured here.
