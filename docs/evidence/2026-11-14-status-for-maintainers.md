# Status for maintainers, 2026-11-14

Ticket 15 of the defect fixes
(`.scratch/defect-fixes/issues/15-status-shows-a-maintainer-only-their-organizations-state.md`).

The history block of `status` gave every reader the instance's first day with
events and its day counts: an organization maintainer learned when the whole
instance first recorded events and how many days of history it holds.

## Changed

- `team-analytics/service/team_analytics/access.py`: `Scope` carries `admin`,
  set for a member of CVAT's admin group whether or not an organization is
  named. Before, an administrator who selected an organization had a scope
  indistinguishable from a maintainer's.
- `team-analytics/service/team_analytics/status/history.py`: the block gains
  `percent` (whole percent of the instance's days with events that are
  processed, rounded down, 100 only when complete) for everyone. A reader who
  is not an administrator gets a block built field by field: `complete`,
  `percent`, `periods`, `earliest_month`, `complete_weeks`, `trends_ready`.
  `first_day`, `days_ready`, `days_total`, `ready_from` and `ready_from_day`
  are for administrators only. `ready_from` and `ready_from_day` are withheld
  too, because the exact moment processing has reached, next to the
  percentage, gives the day count and so the first day.
- The page (`history.tsx`, `service.ts`): the progress bar and its percent
  come from `percent`; the "Ready from ... · N of M days" line appears only
  when the day counts are present. The trends refetch key
  (`team-analytics-page.tsx`) no longer relies on `ready_from` alone, which a
  maintainer's status lacks: it also takes `percent`, `complete_weeks` and
  `earliest_month`.
- Tests that read the full block (`test_history.py`, `test_shutdown.py`) read
  it as an administrator who selected the organization.

## Observed

Seam 1, `verify/team_analytics_service.sh`, in Docker, on the default image
`cvat/clickhouse:23.12.2-debian-11-r0`.

- `tests.test_isolation.HistoryStatusTest` (four cases) was run before the
  fix and failed in all four on the block's key set (setup reached the
  intended state: processed from 2026-11-10, organization B's events from
  2026-10-01). After the fix it passes.
- After the fix, `tests.test_isolation tests.test_history tests.test_status
  tests.test_cutover tests.test_shutdown tests.test_access` (every module that
  reads status, plus access): all pass except
  `test_shutdown`, which read `days_ready` as a maintainer (KeyError). It now
  reads as an administrator and passes, rerun on its own after the merge of
  `feat/team-analytics-page` (the merge changed no service file).

Seam 3, `node --test verify/team_analytics_page.cjs`, with supplied answers:
the two new progress-line cases (without the day counts; with them, the
percent taken from the service) failed before the change to `history.tsx`
and pass after; a third, the period buttons without the day counts, passed
before and after; the whole
suite passes with 0 skipped. ESLint on the three UI files and the type check
pass (type check in the worktree, reading the workspace packages from the
main checkout).

## What a maintainer's status still reveals

Each field the maintainer gets, and what it can say about the instance:

| Field | What it reveals |
| --- | --- |
| `history.complete` | One bit: whether every day since the instance's first event is processed. Instance-wide; when it flips is when processing finished. |
| `history.percent` | The share of the instance's days with events that are processed. Instance-wide by design (it agrees with the administrator's day counts). |
| `history.periods` | For each preset (week, two weeks, month, year), whether it is processed in the viewer's time zone: how far back processing has reached, to the day near the week and two-week edges, and by probing time zones. |
| `history.earliest_month` | The earliest wholly processed month: how far back processing has reached, to the month. |
| `history.complete_weeks`, `history.trends_ready` | How far back processing has reached, to the week, up to twelve weeks. The trends endpoint's per-bucket processed flags already say the same. |
| `refresh.*` | When the last refresh succeeded, the service's clock, the refresh interval and the staleness limit. Nothing about the extent of history. |
| `cutover.at` | The hour of the first shape-tagged event on the instance; allowed by the spec. |

Nothing in it names the first day with events or a day count. Every field
describes the whole instance, not the caller's organization.

While history is still being processed a residual remains, and it cannot be
removed while the percentage agrees with the day counts: the percentage is
"days processed / days in the instance", and the periods tell how far back
processing has reached. Read together at the moment a period, month or week
count changes, they bound the length of the instance's history.

Corrected after the independent review (below): the paragraph first written
here gave a single sighting as the example (a first day "within about two
weeks" when Year becomes offered) and ended "Once history is complete nothing
of this remains". Both undersell it. A caller who polls status while history
is processed sees `earliest_month` change about once a month and
`complete_weeks` change once a week up to twelve; at each change the first
processed day is known exactly (a month's first day, a Monday), so the
processed day count is known exactly, and the percentage then gives the
instance's total to within one percent; several such sightings give the exact
first event day. The reviewer's probe did this. The `processed` flags of the
overview, the list and the details table for any `month`, and the trends'
per-bucket flags, locate the processing point the same way, so withholding
`ready_from` hides little. After history is complete, an event dated before
the instance's first day makes `complete` false again for a step or two, and
for that window the same applies to the older history. Making the percentage
coarser (rounded, or not tied to the instance's day counts) would blunt this;
that is an open decision for the owner.

## Not verified here

- The whole seam 1 suite (run on the integration branch after the package's
  tickets merge).
- The independent review of this access change (after merge).
  Done after merge; see below.

## Independent review

A fresh agent that had not written the changes reviewed tickets 14, 15 and 16
together (what the service returns, and to whom), given the owner's documents
and the three merges (`5fae08e9`, `35f820d0`, `a095b0ba`), not the
implementers' conclusions. It read and probed the tree at `35f820d0` and
changed no tracked file.

Verdict: nothing found lets a caller outside the admin group be taken for an
administrator, crosses between organizations, or puts a technical account into
a list of people. Five findings, two of them defects in what a read returns.

Findings and what was done (follow-up on branch `fix/reads-review`):

1. Status: a maintainer can recover the instance's exact first day of recorded
   work while history is processed (run). The reviewer's probe, polling once
   per history step on an instance whose other organization's work began 197
   days before "today", inferred exactly 197 days from 17 moments at which
   `earliest_month` or `complete_weeks` changed. The `processed` flags of the
   other endpoints locate the processing point to the month or week the same
   way. After history is complete, an event dated before the first day reopens
   the window for a step or two. Behaviour not changed: the owner decided what
   such a caller gets. Recorded without softening in
   `docs/fork-specification.md` ("Known limit of `status` for a caller outside
   the admin group"), in ticket 15's comments, and above, where the earlier
   "about two weeks" and "nothing of this remains" are corrected. Making the
   percentage coarser is an open decision for the owner.
2. Trends: `candidates[].working_time_ms` carried figures from unprocessed
   weeks, and the ranking followed them (run). Fixed: a candidate's working
   time sums only the fully processed buckets and is null while none is;
   candidates are ranked by it, then by id. Summing the processed buckets was
   chosen over giving no figure while any bucket is unprocessed: buckets are
   processed newest first, so the current week is processed early in a long
   history fill, and the page offers the first candidates of the list; with no
   figure until all twelve buckets are processed, the order would be by id
   for the whole fill. A sum over processed buckets is the sum of that line's
   non-null points, which keeps it consistent with "a trend bucket that is not
   fully processed has a null value". Who is a candidate still comes from
   every computed hour of the twelve buckets, so that a comparison can be
   offered while history is processed. Test first:
   `tests.test_trends.ProcessedTest.test_a_candidate_has_working_time_only_from_processed_buckets`
   failed before the fix on `[(12, 7200000), (11, 3600000)]` (Bob ranked first
   on two unprocessed hours) where `[(11, None), (12, None)]` was expected, and
   passes after it. The same test then steps history until the 3rd is
   computed while its week is still unprocessed: Alice's five hours there are
   stored and must count for nothing. The withholding tests of all four endpoints now assert that
   every key outside the stated envelope is null (per point for the trends,
   per candidate while no bucket is processed), with the envelopes written as
   literals in the tests.
3. The legacy flags of an unprocessed answer come from the partial totals and
   can flip once the period is processed (run for trends, read for the list).
   Behaviour not changed: the owner settled that the flags stay in the
   envelope; how they are computed there is the owner's decision. Recorded in
   `docs/fork-specification.md` ("Known limit of unprocessed periods"), ticket
   14's comments, and beside the page's shape switch, which is hidden from
   `operations.legacy`. The two tests that pin today's values
   (`test_trends.ProcessedTest`, `test_full_view.ProcessedTest`) stay, with a
   comment that they pin this limit.
4. A race between reading figures and reading `processed` could send partial
   figures marked processed (read). Fixed: every endpoint reads the history
   state once per request (`Request.history()`), before its first figure read;
   the overview takes it before its sections. No public boundary lets a step
   land between two reads of one request (the clock and the stand-in CVAT are
   both consulted before the endpoint runs), so this is shown with a probe that
   wraps the service's SQL reads and runs one service step right after the
   request's first figure read, in a state where that step completes history
   and adds an hour to November. Before the fix, at `a423f824`, all four
   endpoints answered `processed: true` with the figures read before the step
   (one hour where two were stored; the trends' week of the 2nd at zero).
   After it, all four answer `processed: false` with no figures. The probe is
   kept outside the repository, beside the run logs. The history step writes
   the totals, then marks the hours (`hour_versions`), then records the day
   (`history_days`), so a state read first never covers hours whose figures
   are not yet visible. Read, not run: a day the daily check marks for
   computing again keeps its `history_days` row and stays processed, and its
   hours switch from one complete version to the next when the recompute marks
   them; a request whose figure reads straddle that mark can mix the two
   versions across its queries. That was so before this change and is not a
   partial figure; whether a single query can see rows that
   `drop_superseded` removes while it runs was not checked.
5. Documents did not say what the code does (read). `docs/fork-specification.md`
   now says that status depends on who asks and what each group gets, the
   technical-account row of the details table by project, and each endpoint's
   envelope as it is (the details table returns neither period nor filter
   echo, and returns `technical_accounts`). The docstring of `withheld.py`,
   which claimed a period and filter echo for every endpoint, is corrected.
   Ticket 15's title is not edited; a dated comment says that every field a
   caller outside the admin group still gets describes the whole instance.

`technical_accounts`, the number of configured technical accounts, stays in
the details table and in the overview's creation methods: the page shows it to
every reader of the table ("N technical accounts are left out of annotator
lists", `details-table-card.tsx`) and beside Model
(`creation-methods-card.tsx`). It describes the instance's configuration, not
any organization's work.

What held, as the reviewer read or ran it: administrator recognition only
from CVAT's own `/api/users/self` answer, with and without an organization,
with the caller's own credentials and per-credential cache entries; the
maintainer's status block built field by field; withholding in the overview,
list and details table, including the remainder row, operation parts, details
rows and `project_ids`; ticket 16's rows limited to the caller's organization,
a technical account excluded from every list of people checked, row order
matching `project_ids`; the callers of `keep_refreshing_since` away from window
edges, apart from one the implementer had repaired; the page with
`processed: false` gating every card.

Not checked by the reviewer: the whole service suite (run separately on both
ClickHouse images at `35f820d0`), timing side channels, anything on a stack.

## Observed in the review follow-up

Seam 1, `verify/team_analytics_service.sh`, in Docker, on the default image
`cvat/clickhouse:23.12.2-debian-11-r0`.

- Finding 2: `tests.test_trends.ProcessedTest` before the fix, the new case
  failing as described above; after it, all of `tests.test_trends` passes.
- The new "every key outside the envelope is null" assertions of the
  overview, list and details tests were checked against a temporary change
  that added one field to each withheld answer outside `withhold`: all three
  failed on it, naming the field; the change was not kept. The trends'
  per-candidate assertion is the one that failed first in finding 2.
- Finding 4: the probe (four cases, one per endpoint) failed in all four
  against a copy of the tree at `a423f824` and passed after the fix, run
  together with `tests.test_history`, `tests.test_full_view` and
  `tests.test_details_table`, all of which pass.
- The candidates' date condition in `read/trends_candidates.sql` was checked
  against a temporary change that dropped it: the candidate test failed at
  the state where the 3rd is computed and its week is not processed, on
  `[(11, 21600000), (12, 7200000)]`; the change was not kept.
- `status` was not reordered: it reads the history state once and no figure.
- The whole suite at `2077fb36`: 304 tests, one error,
  `tests.test_entry_point`, whose poll of the running service read
  `by_annotator.rows` from an answer that was not yet processed (null
  section). It never tolerated such an answer; reading the state first makes
  one more likely right after the service starts. The poll now treats a null
  section as "not yet"; `tests.test_entry_point` and
  `tests.test_trends` then pass.

Seam 3, `node --test verify/team_analytics_page.cjs`: 217 pass, 0 skipped
(the page changed only in a type and a comment). ESLint and the type check
pass on the two UI files touched (`service.ts`, `team-analytics-view.tsx`).

Not verified in the follow-up: the whole seam 1 suite after the repair of
`tests.test_entry_point`, and the second ClickHouse image (left to the
merger's runs); the race through a public boundary (none allows it); a
second independent review of the follow-up.
