# 15: Status shows a maintainer only their organization's state

**What to build:** An organization maintainer sees whether processed history is complete, how far along it is, which periods can be offered, how fresh the figures are and the cutover day. They no longer see when the whole instance first recorded events or how many days of history it holds. Administrators keep the full block. See "Service: what a read returns" and "Page" in the spec (`../spec.md`).

**Blocked by:** 05 (First lint run on the fork's UI code).

**Status:** ready-for-agent

- [x] Test first, through the service's read interface: a non-administrator's status has the complete flag, a progress percentage, the periods that can be offered, the freshness stamp and the cutover day, and has no first event day and no day counts.
- [x] An administrator's status has the first event day and the day counts, with and without an organization selected.
- [x] The percentage agrees with the administrator's day counts.
- [x] Earlier events of another organization add no field to a maintainer's status.
- [x] Test first, on the page with supplied answers: the history progress line renders from the percentage when the day counts are absent, and from the days when they are present.
- [x] The period control still offers only processed periods.
- [ ] The access change gets an independent review.

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
