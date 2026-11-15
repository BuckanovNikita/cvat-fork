# 09: Evidence closed

**What to build:** The open lines of the two evidence records of 2026-11-15 (`backend-acceptance` and `full-fork-conversion` under `docs/evidence/`) are closed on the final image (item 8 of the spec). One new dated record under `docs/evidence/` holds the results, and a pointer to it is added to the two records and to the independent review. Each open line ends verified or ruled out with its reason.

Verified on a stack (its own namespace and port, work images): the final image with `check-review` and `check-isolation clickhouse-down`; a Redis failure answered with 503 (run last, with the refresh schedule restored afterwards); a read job queued again after its worker is killed; the generation standing still over idle minutes; a worker failing its liveness probe; two worker replicas; analytics switched off and on again by an in-place upgrade, with the Technical accounts list intact; one heavier load run (ClickHouse at 4 CPUs, three times the volume of data, the same limits, with Postgres connections and Redis memory sampled).

Verified off the stack: the build from scratch (ticket 07); a fresh clone with dependencies installed from the locks passing `prek run --all-files`; the diagnosis of the failed jobs seen at worker start, which match rq 1.16.0's `clean_intermediate_queue` (a starting worker fails a job another process has just dequeued; the job still runs), confirmed from the pinned source in the image and the failed job's `exc_info`, then recorded as an upstream limit without a pin change.

Ruled out with the reason: a cluster of more than one node, upstream's Compose files, production, the release-merge trial, and the build's rename refusal (its guard is deleted in ticket 07).

**Blocked by:** 01, 02, 03, 04, 05, 06, 07, 08.

**Status:** ready-for-agent

- [ ] A new dated record exists under `docs/evidence/`, and the two 2026-11-15 records and the independent review's record of the same date (`docs/evidence/2026-11-15-independent-review.md`, for its "Not established" lines) point to it. The one-time image comparison of ticket 07 is kept beside it.
- [ ] Every open line of the two records is listed in the new record as verified (with the command and what it showed) or ruled out (with the reason); none is left open.
- [ ] On the live stack: `check-review` and `check-isolation clickhouse-down` pass on the final image; the Redis failure gives 503 and the schedule is restored after it.
- [ ] On the live stack: a killed worker's read job is queued again and answered; the generation does not move over idle minutes; a failed liveness probe restarts the worker; two replicas serve reads.
- [ ] On the live stack: analytics off and on by an in-place upgrade keeps the Technical accounts list; the heavier load run records Postgres connections and Redis memory.
- [ ] The fresh-clone pipeline run passes, and the rq diagnosis cites the pinned source and the job's `exc_info`.

## Comments
