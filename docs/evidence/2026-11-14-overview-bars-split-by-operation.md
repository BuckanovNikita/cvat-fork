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
- After a second merge of `feat/team-analytics-page` (`0b4c662`, with the
  review follow-up of tickets 14 to 16 that reads the history state before any
  figure; the only conflict was in `endpoints/list.py`, resolved by keeping both
  changes), `test_full_view`, `test_entry_point`, `test_history`,
  `test_working_time`, `test_projects_filters` and `test_refresh` were run
  again: all passed.

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
`ruff check team-analytics/service` passed. `prek run --all-files` passed on
`0b4c662`, the second merge, with every hook run and none skipped. Its page
suite hook covers seam 3 on that tree.

## Not verified

- The look beside the prototype, at 1400 px and at 400 px, is ticket 27's
  browser run (what to look at is in the ticket).
- The whole seam 1 suite was not run on this branch, and neither was the second
  ClickHouse image.
- The overview now runs the full view's row read twice (once per section) in
  place of two working-time-only reads. Its cost at the benchmark's scale was
  not measured here.

## Independent review, 2026-11-15

A fresh agent that had not written the changes reviewed tickets 23 and 24
together with the two review follow-ups merged beside them (the reads side of
tickets 14 to 16 and the refresh side of tickets 17, 18 and 20). It was given
the owner's documents and the four merges (`6a442e9a`, `7ce5a449`,
`76b58c31`, `3dc1a7bc`), not the implementers' conclusions. It read and probed
the tree at `3dc1a7bc` and changed no tracked file. Ticket 24's evidence
points here.

Verdict: nothing high-severity. Within the scenarios it checked, an overview
row's split equals its full-view row both by construction and by run, and no
figure of an unprocessed time leaves the service. Both "seen failing first"
claims it spot-checked reproduced.

Findings, most severe first, and what was done:

1. **Trend candidates tell who worked in weeks not yet processed** (low to
   medium; owner decision; run). With only the current week processed, a
   person whose only work is in a computed but unprocessed week is listed as a
   candidate with `working_time_ms` 0, while the list and the overview for the
   same span withhold every row. Listing candidates from every computed hour
   was the implementer's choice. Behaviour unchanged. The limit, its scope
   and the options are written into `docs/fork-specification.md` where the
   candidates are described, and in ticket 14's comments; the choice is an
   open decision for the owner.
2. **The cutover search may be stopped at every start and daily check on a
   large instance** (low to medium; read). The in-order statement reads every
   record before the stored cutover, and its cost at the benchmark's scale was
   not measured. Measured and corrected in a separate follow-up on branch
   `fix/cutover-search-measured`.
3. **A bar's parts can add up to more than the bar** (low; run and read). A
   row whose operation time exceeds its working time has Other clamped at
   zero, and its parts fill a bar drawn at its working time (a 1.0 h row draws
   Creation 2/3 and Alignment 1/3, hovering "Creation: 2.0 h" and "Alignment:
   1.0 h"), beside the definition "every breakdown of time adds up to it". Not
   new: the full view behaves the same and the overview now matches it.
   Behaviour, glossary and definitions unchanged. Written into
   `docs/fork-specification.md` ("Known limit of the split by operation") and
   ticket 24's comments as an open decision for the owner.
4. **The two overview legends share class names** (low; by reading the
   stylesheets). Fixed in `b5743f8a`, below.
5. **A row without operation parts is drawn in Creation's colour** (low; run).
   Fixed in `27a62f78`, below.
6. **Small documentation inaccuracies** (nit; read): the fork specification
   says the cutover search goes through "a second" client where each wait
   makes its own, and `ProductionClockTest` asserts only a lower bound (said
   in its docstring). Corrected in the separate follow-up on branch
   `fix/cutover-search-measured`.

What held, as the reviewer ran or read it:

- The split: the overview sections and the full-view list go through one row
  read with the same parameters. A probe over every project filter, every
  annotator filter, both at once, an annotator with no work and both shape
  settings found every overview row equal to the full view's. The legacy
  period, the remainder row, a clamped Other and unprocessed periods are
  pinned by tests.
- The replaced overview queries: top eight, order and ties unchanged;
  technical accounts still left out; no figure returned by one view and
  withheld by the other; one query per section.
- The page: seam 3 passed with none skipped; null sections, no rows, one row,
  a 300-character name and a very large value render; in a legacy period
  class change is dropped from the legend and the bars.
- The definitions: worded from the glossary (seven sentences verbatim, two
  composed from Session gap and Idle pause), no figures, only in the overview.
- The reads follow-up: the candidate figure leak is fixed apart from finding
  1; one early read of the history state per request on all four endpoints
  can only make an answer more cautious; the envelope literals in the tests
  match the code and the specification.
- The refresh follow-up: the limits use a thrown timeout, not a partial result
  (which would store a later cutover); a stopped search is caught at start and
  in the daily check, and a lost lease still propagates; the cheaper statement
  is equivalent to the old one for ties, same-timestamp records, the bound at
  the end of the current hour, an empty table and a missing table, and stays
  "never later"; the explicit marker wraps all three lease statements.

Not checked by the reviewer: anything in a real browser; the cost of the
doubled row read and of the in-order cutover search at the benchmark's scale;
the memory limit stopping a statement; the second ClickHouse image. The whole
service suite was run separately by the orchestrator at `3dc1a7bc` on both
images.

### Follow-up on branch `fix/page-review`

**Finding 4, one class family per legend (`b5743f8a`).** The overview bars'
legend (`working-time-breakdown.tsx`, styled in `projects-filters.scss`) now
uses `cvat-team-analytics-breakdown-legend`, `-items`, `-item` and `-swatch`;
the "where working time goes" list (`working-time-split-card.tsx`, styled in
`styles.scss`) uses `cvat-team-analytics-split-legend`, `-item`, `-name` and
`-share`. No bare `cvat-team-analytics-legend` name is left in the tree. What
either legend shows is unchanged; the two seam 3 selectors that named the old
classes follow the rename.

Stated check, not a kept test, since nothing a test can see changed: a
one-off script, not committed, compiled every stylesheet of the
page directory with the UI's Sass (load path `cvat/cvat-ui/src`), rendered
the overview with supplied answers in jsdom, and listed every compiled rule
that matches an element of each legend.

| Rule | Bars' legend before | Split list before | Bars' legend after | Split list after |
| --- | --- | --- | --- | --- |
| `projects-filters.scss` legend (flex, wrap, `space-between`, 12 px) | yes | yes | yes, renamed | no |
| `styles.scss` legend (no list style, no margin) | yes | yes | no | yes, renamed |
| `projects-filters.scss` legend item (`inline-flex`, 6 px gap) | yes | yes | yes, renamed | no |
| `styles.scss` legend item (flex, 10 px gap, 7 px padding, 1 px top line) | yes | yes | no | yes, renamed |
| `projects-filters.scss` items, swatch | yes | no | yes, renamed | no |
| `styles.scss` legend name and share | no | yes | no | yes, renamed |
| `styles.scss` swatch and value (shared page classes, not renamed) | no | yes | no | yes |

Before: four rules reached both legends. After: none. Both directions of the
collision were real: the bars' legend items carried the split list's 7 px
padding and top line, and the split list carried the bars' legend's flex row
layout, `space-between` and 12 px type, with its items `inline-flex`
(`projects-filters.scss` is imported after `styles.scss`, so its
`display` and `gap` won). So the fix changes how both cards render compared
with an image built before it. The look itself is checked in a browser in
ticket 27; what that run should look at is in ticket 23's comments.

**Finding 5, a bar without parts in no legend colour (`27a62f78`).** Chosen:
a neutral bar. Leaving the legend out only helps when no row carries parts;
when only some do, the legend is right for those rows and the rows without
parts still need a colour the legend does not name. Such a row is now drawn
whole in `#595959`, which none of the five operation colours uses (Other is
the light grey `#c9c8c2`), and its hover reads "alice: 2.0 h, not split by
operation". The legend stays in every case. Seam 3, three tests added to
`verify/team-analytics-page/split-bars.test.cjs` and seen to fail first, each
on "rgb(42, 120, 214) is a colour of the legend": no row carries parts (both
cards), only some rows do, and a legacy period. After the fix all pass. The
tests and the fix are in one commit; the red run was on the tests alone.

**Findings 1 and 3.** Documentation only (`21ce496a`), as above. No service,
glossary or definitions change.

Checks on the follow-up. The branch started from the tip of
`feat/team-analytics-page` (`e62e1db8`), which had not moved when the work
was done, so there was nothing to merge. Seam 3 passed with none skipped;
ESLint on the two changed cards, stylelint on
`styles.scss` and `projects-filters.scss`, and the UI type check (section 4 of
`docs/upstream-upgrade.md`) found nothing; the type check ran in a worktree
and read the workspace packages from the main checkout. `prek run --all-files`
passed on the branch's final commit, every hook run and none skipped.

Not verified: the rendered look of either legend and of the neutral bar, at
1400 px and at 400 px, which needs a browser (ticket 27). The live stack
serves a UI image built before this change.
