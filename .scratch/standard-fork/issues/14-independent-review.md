# 14: Independent review of the integrated branch

**What to build:** A review by an agent that wrote none of it: behaviour, interfaces, access and security of the integrated branch against the spec.

**Blocked by:** 13.

**Status:** resolved

- [x] Access: no path to figures without the permission check; no entry served across scopes.
- [ ] Isolation: nothing in the API process reaches ClickHouse for this feature; every wait is bounded.
- [ ] The refresh: one run at a time, no write without the lock.
- [x] Findings are fixed or recorded with reasons, and the affected checks rerun.

## Comments

2026-11-15: Two reviewers that wrote none of the code read the branch at `05c86536`: one on access, isolation between organizations and the read path, one on the refresh, the lock, the jobs, failure isolation and delivery. Record: `docs/evidence/2026-11-15-independent-review.md`. Nothing was rated high. Neither found a way to figures without the permission check or to another organization's figures, an injection path, or a write without the lock check that could hide newer totals under clocks that agree.

Fixed in `b1655b51` and `6d77332a`: parameters an endpoint does not read no longer make cache keys and jobs; values have the length a valid one needs; a Redis failure answers 503 and the read job lets nothing out; the generation is a counter; a run advances it also when a step failed or lost the lock; piled-up copies of the refresh job are removed and do not count as reads; refresh statements have a time limit on ClickHouse; a waiting request holds no database connection; a mistyped setting cannot stop CVAT from starting; the image build sees renames and untracked files; the chart keeps zero replicas; ruff checks the app.

Recorded as limits in the fork specification, not fixed: who can read by creating an organization; no limit per account on waiting requests; the lock against a transaction, with the clock condition; leftover rows of a failed attempt; a Redis that loses its data or never answers; Compose.

Two criteria stay unticked, because the review did not find them wholly true. Nothing in the API process reaches ClickHouse for the feature, but one wait is not bounded: CVAT's Redis connections have no socket timeout, so a Redis that never answers holds a request as it holds any other of CVAT's. One step runs at a time under the lock, but a few writes are not preceded by the lock check (the removal of superseded rows, the record of the daily check, statements after the first of a file); the reviewer found them unable to hide newer totals.

Rerun after the fixes: the calculation suite (338 tests), the check pipeline (12 hooks), and the whole stack sequence with a new `check-review` on the final image, all passed (`docs/evidence/2026-11-15-backend-acceptance.md`, "On the final build").
