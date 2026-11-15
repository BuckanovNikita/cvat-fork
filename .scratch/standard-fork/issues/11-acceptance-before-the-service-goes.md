# 11: Acceptance on the stack before the service is deleted

**What to build:** The evidence that the backend path gives the same figures, the same access, and does not slow CVAT down. Recorded as one dated evidence file. See stories 7 to 14.

**Blocked by:** 10.

**Status:** resolved

- [x] Parity: the calculation suite on both ClickHouse images; the page and logging suites; the policy tests; a fresh `up`, a second `up`, `down`.
- [x] Access on real accounts: every role by endpoint, a removed member refused on the next request, an administrator by group, a personal workspace under instance scope, token credentials, no cached answer served across organizations.
- [x] Isolation: with the worker at zero while twelve analytics requests are waiting, with ClickHouse at zero, and with the totals database dropped, sign-in, the task list and opening and saving a job work, and the analytics endpoints answer within the wait.
- [x] With analytics disabled the server starts, no worker is rendered and the endpoints are 404.
- [x] Load: twelve concurrent uncached overviews on the volume data, once during a refresh and once while history is being filled; the 95th percentile of the task list and of a job's annotations stays within noise of the baseline taken just before, and all twelve overviews return figures within the client's retry budget (four waits and three pauses: 29 s with the default settings).
- [x] What was not reached is listed as not verified.

## Comments

2026-11-15: Recorded in `docs/evidence/2026-11-15-backend-acceptance.md`. The final sequence passed on the launcher of `3fa20bc3` and the server image of `919d7ea0`. The load check failed twice on the way and changed the design both times: reads now come before history (`2c653fe6`), and the cache key names the request, not the state of the totals (`919d7ea0`). In the final run CVAT's own endpoints stayed within the limit in both conditions and all 36 overviews of each condition returned figures within 23 s, the budget being 29 s. The calculation suite passed on both ClickHouse images at `ee596bfd` (356 tests each).

Run after this ticket's sequence, on the tree without the service: see ticket 12.

2026-11-15: The sequence was run again on the final build, after the independent review's fixes, and passed whole, with `check-review` added. Its figures are in the record's section "On the final build".
