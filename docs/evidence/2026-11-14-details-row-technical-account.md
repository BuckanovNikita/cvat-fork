# Details row for a project with only technical-account boxes, 2026-11-14

Ticket 16 of the defect fixes
(`.scratch/defect-fixes/issues/16-a-project-with-only-technical-account-boxes-appears-in-the-details-table.md`).

The details table by project took its rows from working time and operations.
A project into which only a technical account saved boxes had neither, so it
had no row and its Model boxes were invisible in the table.

## Changed

- `team-analytics/service/sql/read/details.sql`: by project, the row set also
  holds every project with saved boxes. Under an annotator filter a technical
  account's saved boxes neither list a project nor count for one.
- `team-analytics/service/sql/read/details_scope.sql`: `project_ids`, which
  the page searches by name, follows the same rule.
- No Python and no page code changed.

## Observed at the service's read interface, against a real ClickHouse

`verify/team_analytics_service.sh`, in Docker, on the default image
`cvat/clickhouse:23.12.2-debian-11-r0`. The cases are the two classes
`TechnicalAccountOnlyProject*` in `team-analytics/service/tests/test_details_table.py`.

Each of the first three cases was written and seen to fail before its part of
the fix:

| Case | Failure seen | After the fix |
| --- | --- | --- |
| The project has a row with no working time, its saved boxes and its Model boxes | two rows listed, not three | passes |
| The project is among `project_ids`, in the table's order | `[2, 1]`, not `[2, 1, 3]`, with the row already listed: the scope query read no boxes | passes |
| An annotator filter on the technical account's id lists no project | two projects listed, once the row set took saved boxes as the table counted them | passes |

The second case also failed once more on a first version of the scope query,
where an alias hid the box count. The case caught it.

The remaining cases were written after the fix. To see which of them the old
row set fails, all seven were run once with the two query files as they were
at `e2f0499`, and the files were then restored. The first two cases failed as
in the table above; the others:

| Case | With the old queries | With the fix |
| --- | --- | --- |
| Paging: ten worked projects, the eleventh alone on page 2, a page past the end | fails: 10 rows, not 11 | passes |
| Search by ids and the project filter | fails: `ids=3` finds nothing | passes |
| Such a project of another organization does not appear | fails, but only on the own organization's project 3 being absent | passes |
| The technical account is no row of the table by annotator | passes | passes |
| An annotator filter on the technical account's id lists no project | passes: the old row set never listed it | passes |

So two things were never seen failing: the table by annotator leaving the
technical account out, which the fix does not touch, and the other
organization's project staying out. For the second the case holds a positive
control instead: the same save is listed for an administrator in instance
scope, so it is stored and it is the organization filter that leaves it out.

The whole suite ran once, on `ae0dcf3` (this branch with tickets 02 and 03
merged in): 272 cases passed, none failed and none was skipped. That is the
265 of the baseline and the seven new ones.

Tickets 01 and 19 were merged after that run (`a5c6bcd`). Of the files the
suite loads, that merge changed the calculation of operations and three test
modules. The whole suite was not run a second time; the details cases and
those three modules (`test_details_table`, `test_creation_methods`,
`test_operations`, `test_bounding_boxes`) were run again on `a5c6bcd`:
85 cases passed, none failed and none was skipped.

Tickets 04 and 06 were merged last (`b945f3c`). That merge changed no file the
suite loads (the service, the events database's init script, the runner), so
nothing of the suite was run again for it.

## Checked with supplied answers: the page

`node --test verify/team_analytics_page.cjs`, the case "a project with only
technical-account boxes ..." in `verify/team-analytics-page/details-table.test.cjs`.
The card is given the row as the service sends it (no annotators, no sessions,
zero working time, both ratios null), once in a recorded and once in a legacy
period.

- It passed without a change to the page: the row reads `0`, `0.0 h`, its
  boxes, and a dash for the average time to create and for the hotkey share.
  No cell is empty and nothing reads `NaN` or `Infinity`, hover text included.
- The case never failed against the page as it is. To see that it can fail,
  the card was changed for one run to divide working time by sessions; the
  case then failed on `NaN s`. That change was not kept.
- With the integration branch merged in (`b945f3c`, which holds ticket 02's
  change to how these tests load their browser environment), the page suite
  and the logging suite both pass with none skipped (207 and 55 cases).

## Not verified

- No stack was started: the row was not seen in a browser against a running
  service.
- The second ClickHouse image (`clickhouse/clickhouse-server:23.11-alpine`)
  was not run.
- "A technical account appears in no list of people" has a new case only
  for the details table. For the overview's annotators and sessions, the saved
  boxes by annotator, the full view by annotator and the trends' candidates it
  rests on their existing cases, which passed in the whole-suite run
  (`TechnicalAccountsLeftOutTest`, `TechnicalAccountsTest`, `SavedBoxesTest`,
  `ModelPerRowTest`, `ScopeAndComparisonTest`), and on no other read file
  being changed.

## Noticed, not changed

Read in the query files, not run:

- A scope that holds nothing but technical-account boxes now answers rows, yet
  still says `legacy: false` and `partly_legacy: false`, in a legacy period
  too: job work stays working time or an operation. The page then heads the
  column Model, and in a legacy period that Model counts every shape, as the
  overview's creation methods already do for such a scope.
- A project into which a technical account saved only objects that are not
  boxes has no row, although under All shapes it has Model objects. The spec
  names saved boxes as the source of rows, which keeps the row set independent
  of the shape switch.
- By the same rule a project in which a person only saved boxes, with no
  working time and no operation, now has a row too.
- The full-view list by project (`sql/read/list_rows.sql`) takes its rows from
  working time, operations and Model objects, so it already listed a project
  with only technical-account boxes (its existing case `ModelPerRowTest` shows
  that), and its rows follow the shape switch. The two row sets therefore
  still differ for the two projects above. It was not touched.
