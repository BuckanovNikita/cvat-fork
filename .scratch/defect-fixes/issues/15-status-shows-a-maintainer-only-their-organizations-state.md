# 15: Status shows a maintainer only their organization's state

**What to build:** An organization maintainer sees whether processed history is complete, how far along it is, which periods can be offered, how fresh the figures are and the cutover day. They no longer see when the whole instance first recorded events or how many days of history it holds. Administrators keep the full block. See "Service: what a read returns" and "Page" in the spec (`../spec.md`).

**Blocked by:** 05 (First lint run on the fork's UI code).

**Status:** resolved

- [x] Test first, through the service's read interface: a non-administrator's status has the complete flag, a progress percentage, the periods that can be offered, the freshness stamp and the cutover day, and has no first event day and no day counts.
- [x] An administrator's status has the first event day and the day counts, with and without an organization selected.
- [x] The percentage agrees with the administrator's day counts.
- [x] Earlier events of another organization add no field to a maintainer's status.
- [x] Test first, on the page with supplied answers: the history progress line renders from the percentage when the day counts are absent, and from the days when they are present.
- [x] The period control still offers only processed periods.
- [x] The access change gets an independent review.

## Comments

2026-11-14: Implemented on `ticket/15-status`; evidence in
`docs/evidence/2026-11-14-status-for-maintainers.md`.

- The first four criteria are `tests.test_isolation.HistoryStatusTest`, seen to fail on the
  block's key set before the fix and to pass after (seam 1, default ClickHouse image). The
  page criteria are three cases in `verify/team-analytics-page/history.test.cjs`; the two on
  the progress line failed first, the period-control case is a guard that passed before and
  after.
- Besides the first day and the day counts, a maintainer also loses `ready_from` and
  `ready_from_day`: the exact moment processing has reached, next to the percentage, gives the
  day count and so the first day. A maintainer's block is `complete`, `percent`, `periods`,
  `earliest_month`, `complete_weeks`, `trends_ready`. The last three are wider than the spec's
  list ("the periods that can be offered") and are kept as part of it: the month control
  needs `earliest_month`, the trends notice needs `complete_weeks` and `trends_ready`.
- What each remaining field reveals is in the evidence file. In short: once history is
  complete, nothing about the instance beyond the cutover. While it is processed, the
  percentage (days processed / days in the instance) read together with the periods at the
  moment one changes bounds the length of the instance's history (for a two-year instance,
  to about two weeks when Year becomes offered). This cannot be removed while the percentage
  agrees with the administrator's day counts; it is left for the reviewer.
- `Scope` in `access.py` gained `admin`; an administrator who selected an organization was
  indistinguishable from a maintainer before.
- Outstanding: the independent review of this access change, after merge; it is not done
  here.

2026-11-14: Merged into `feat/team-analytics-page` as `5fae08e9`, without conflicts. On the merged tree `node --test verify/team_analytics_logging.cjs` ran 70 tests and `node --test verify/team_analytics_page.cjs` 212, 0 failed and 0 skipped each; the skip-gate grep finds nothing. The service suite was not run by the merger. The ticket stays open until the independent review of the access change after this merge. Evidence: `docs/evidence/2026-11-14-status-for-maintainers.md`.

2026-11-14: Reviewed independently after merges `5fae08e9`, `35f820d0` and `a095b0ba` (tickets 15, 14, 16). Who reviewed, the verdict, the five findings and what was done about each, what held and what was not checked: `docs/evidence/2026-11-14-status-for-maintainers.md`, "Independent review". The follow-up is on branch `fix/reads-review`.

2026-11-14: Correction to the comment above that says the residual bounds the instance's history "to about two weeks" and that "once history is complete, nothing" remains. The review showed more: while history is processed, a caller outside the admin group who polls status can work out the instance's exact first event day, and so the length of its history (each change of `earliest_month` or `complete_weeks` fixes the processed day count exactly, and the percentage then gives the total). The `processed` flags of the overview, the list and the details table for any `month`, and the trends' per-bucket flags, bound the same. After history is complete the window reopens briefly when an event dated before the first day arrives. The owner decided what such a caller gets (a percentage that agrees with the administrator's day counts, and the periods that can be offered); making it coarser, a rounded percentage or one not tied to the instance's day counts, is an open decision for the owner. Written into `docs/fork-specification.md` ("Known limit of `status` for a caller outside the admin group") and the evidence file.

2026-11-14: The title says "their organization's state", but every field a caller outside the admin group still gets (`complete`, `percent`, `periods`, `earliest_month`, `complete_weeks`, `trends_ready`, `refresh`, `cutover`) describes the whole instance, not one organization: history is processed for the instance as a whole. The title is left as it is.

2026-11-14: Resolved. The ticket was merged as `5fae08e9`; the follow-up of the independent review (branch `fix/reads-review`) was merged as `76b58c31`, without conflicts, which closes the last open criterion. On the merged tree `node --test verify/team_analytics_page.cjs` ran 217 tests and `node --test verify/team_analytics_logging.cjs` 70, 0 failed and 0 skipped each; the skip-gate grep finds nothing. The service suite was not run by the merger; the orchestrator reruns it. Evidence: `docs/evidence/2026-11-14-status-for-maintainers.md`.
