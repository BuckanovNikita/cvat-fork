# 09: Evidence closed

**What to build:** The open lines of the two evidence records of 2026-11-15 (`backend-acceptance` and `full-fork-conversion` under `docs/evidence/`) are closed on the final image (item 8 of the spec). One new dated record under `docs/evidence/` holds the results, and a pointer to it is added to the two records and to the independent review. Each open line ends verified or ruled out with its reason.

Verified on a stack (its own namespace and port, work images): the final image with `check-review` and `check-isolation clickhouse-down`; a Redis failure answered with 503 (run last, with the refresh schedule restored afterwards); a read job queued again after its worker is killed; the generation standing still over idle minutes; a worker failing its liveness probe; two worker replicas; analytics switched off and on again by an in-place upgrade, with the Technical accounts list intact; one heavier load run (ClickHouse at 4 CPUs, three times the volume of data, the same limits, with Postgres connections and Redis memory sampled).

Verified off the stack: the build from scratch (ticket 07); a fresh clone with dependencies installed from the locks passing `prek run --all-files`; the diagnosis of the failed jobs seen at worker start, which match rq 1.16.0's `clean_intermediate_queue` (a starting worker fails a job another process has just dequeued; the job still runs), confirmed from the pinned source in the image and the failed job's `exc_info`, then recorded as an upstream limit without a pin change.

Ruled out with the reason: a cluster of more than one node, upstream's Compose files, production, the release-merge trial, and the build's rename refusal (its guard is deleted in ticket 07).

**Blocked by:** 01, 02, 03, 04, 05, 06, 07, 08.

**Status:** resolved

- [x] A new dated record exists under `docs/evidence/`, and the two 2026-11-15 records and the independent review's record of the same date (`docs/evidence/2026-11-15-independent-review.md`, for its "Not established" lines) point to it. The one-time image comparison of ticket 07 is kept beside it.
- [x] Every open line of the two records is listed in the new record as verified (with the command and what it showed) or ruled out (with the reason); none is left open.
- [x] On the live stack: `check-review` and `check-isolation clickhouse-down` pass on the final image; the Redis failure gives 503 and the schedule is restored after it.
- [x] On the live stack: a killed worker's read job is queued again and answered; the generation does not move over idle minutes; a failed liveness probe restarts the worker; two replicas serve reads.
- [x] On the live stack: analytics off and on by an in-place upgrade keeps the Technical accounts list; the heavier load run records Postgres connections and Redis memory.
- [ ] The fresh-clone pipeline run passes, and the rq diagnosis cites the pinned source and the job's `exc_info`.

## Comments

2026-11-16: Recorded in `docs/evidence/2026-11-16-open-lines-closed-and-admin-settings.md` (`cabe076b6`), with the comparison's four diffs and six screenshots beside it; the pointers added to the three 2026-11-15 records in `153f3bead`; the review's last limits added to `docs/fork-specification.md` in `36da765c0`. The evidence steps came from `86245f4b6` and the review's fixes to them. Final run at `0bf2f41cd` on server `7ead6d1cec4b` and UI `1d1a6e3d425c`: every step exit 0 except the first `check-load`, which failed on one read run twice in a burst and on a checker defect; it passed twice alone afterwards, the second time with the corrected rule of `9a8620e96`. `check-review` and `check-isolation clickhouse-down` passed; `redis-down` (last) gave 503 to 12 reads within 7 s with the schedule present; killed-worker 429 for 299 s then 200, 2 executions; idle generation unchanged over 360 s; liveness restart after 284 s; two replicas 6 and 6 read jobs; off and on by in-place upgrades (revisions 8, 9, 10) with the list intact; the heavy load (ClickHouse at 4 CPUs, three volume organizations) 36 of 36 in both conditions with Postgres connections at most 13 and Redis at most 3.6 MiB. Every line of the two records is verified or ruled out; of the independent review's three "Not established" lines, the ClickHouse insert cancellation stays open and is listed as not verified.

Left unticked, the last criterion, only partly met: the fresh clone passed (`prek` exit 0, twelve hooks) and the rq diagnosis cites the pinned source in the image (`rq/maintenance.py` lines 10-26, `worker.py:320`) and the log order, but the failed job's `exc_info` could not be cited: the job's record had no `exc_info` field, because the scheduler creates it again under the same id every minute, and the race did not occur on the final run's worker start. Also not done: reading rq's changelog for the release that changed this.
