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

Nothing in it names the first day with events or a day count, and none of
it depends on another organization's events once history is complete
(`complete: true`, `percent: 100`, every period offered).

While history is still being processed a residual remains, and it cannot be
removed while the percentage agrees with the day counts: the percentage is
"days processed / days in the instance", and the periods tell how far back
processing has reached. Read together at the moment a period, month or week
count changes, they bound the length of the instance's history. Example: an
instance whose first event is 731 days before today. When `year` becomes
offered, about 366 days are processed and `percent` reads 50; the reader can
then infer that the instance holds between about 718 and 732 days, a first
day within about two weeks. Polling over the whole processing narrows the
bound further, and the last state before `complete` turns true says that only
the oldest day is left. Once history is complete nothing of this remains.

## Not verified here

- The whole seam 1 suite (run on the integration branch after the package's
  tickets merge).
- The independent review of this access change (after merge).
