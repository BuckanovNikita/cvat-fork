# Team Analytics in the backend: acceptance on the stack, 2026-11-15

Ticket 11 of `.scratch/standard-fork/` (ADR 0006), with what tickets 05 to 08 and 10 left for a
running stack. Everything below ran on the local Kubernetes cluster in a namespace of its own
(`TA_RUN_ID=fork`, host port 8491), beside another stack of the same user that was not touched.
The final sequence ran on the launcher as committed in `3fa20bc3` and on the fork server image
built from `919d7ea0` (`cvat/server:v2.82.0-fork`, `f7b1c80e`), with `cvat/ui:v2.82.0-fork`
(`239758255066`, built from `74ec38ed`'s page). The run's logs are kept outside the repository.

The stack's ClickHouse is limited to 2 CPUs and 2 GiB. The worker ran the chart's default: one
replica, three processes.

## Final sequence

All on the final files and image, in this order, each judged by its exit status:

| Step | Result |
| --- | --- |
| `preflight` (server image, both policy matrices, chart render with analytics on and off, render guard) | passed |
| fresh `up` | passed |
| second `up` on the same stack | passed |
| `check-cross-org` | passed |
| `check-isolation` worker-down, clickhouse-down, totals-dropped | passed |
| `check-load`, refresh condition and history-fill condition | passed |
| `check-analytics-off` | passed |
| `down` | passed; namespace gone, no port-forward, nothing on the port |

`check-fixes` (all steps) passed on the first image of the day, and its `unprocessed` and
`cutover-restart` steps, the two that depend on the generation, passed again on the final image.
The first fresh `up` on the final files failed in a checker (it read figures of a period that
was not yet processed); the checker was corrected and the sequence above followed.

## Parity

- The calculation suite, with the 35 tests added for the engine, the Redis lock and the read
  path, at `ee596bfd`: 356 tests, none failed, on `cvat/clickhouse:23.12.2-debian-11-r0`
  (3,000 s) and on `clickhouse/clickhouse-server:23.11-alpine` (2,600 s). At the commit that only
  moved the calculation code (`5cdd1237`): the service's 321 tests, none failed.
- One of those tests compares the engine under the Redis lock, asked directly, with the service
  over HTTP: equal answers for the five endpoints, for an organization and for the instance.
- Page suite 240 tests, logging 77, task progress 20 and 1 skipped; the check pipeline's twelve
  hooks passed at `43218eeb`. Upstream's generated policy suite: 29,208 cases, none failed.

The commits after `ee596bfd` changed the read path and the jobs (`2c653fe6`, `919d7ea0`), not
the calculation code; the read-path tests (22) and the API-side tests (3) were rerun on them.

## Access on real accounts

Bodies as served:

| Case | Answer |
| --- | --- |
| owner or maintainer naming no organization | 403 `{"error":"organization_required"}` |
| anyone else refused, a non-member naming an existing organization included | 403 `{"detail":"You do not have permission to perform this action."}` |
| signed out | 401 `{"detail":"Authentication credentials were not provided."}` |
| unknown organization | 404 `{"detail":"<slug> organization does not exist."}` |
| a bare `Accept: application/json` | 406, as for the rest of CVAT's API |

The access checks of `up` passed: every seeded account by endpoint, an administrator by group
with and without an organization, a personal workspace counted under instance scope only,
cookie, Basic and Bearer credentials deciding alike, and a removed member refused on the next
request with no wait. `check-cross-org`: after one organization's maintainer had loaded an
overview, another organization's maintainer asking the same parameters got their own figures,
and an administrator's `status` was not served to a maintainer.

The page, in a browser against the stack, showed its states by role through cvat-core: the
organization is attached by cvat-core, and "select an organization" is recognised from the
`organization_required` body.

## The worker

- `run worker team_analytics` started through the fork's component file. CVAT's own probe
  command reported three live worker processes; no restart and no failed probe in any run.
- The refresh job ran every minute from CVAT's scheduler. With the stack's 60 s interval the
  status stamp advanced at gaps of 60 or 120 s: a refresh of recent hours runs at the first run
  after the interval has passed.
- In the final fresh `up` the first figures were there about 1.6 minutes after the chart
  install began, 17 s after the work had been loaded.
- The worker's log shows the core's lines (`refreshed … as version …`, `history: computed <day>
  as version …`) and one line per read. One refresh step took about 0.35 s and one day of
  history about 0.25 s on this data.
- A cold overview took 2.3 to 2.6 s and came back within the 5 s wait, with no 429. A warm one
  took 0.03 to 0.04 s. The cold time is eleven ClickHouse statements in sequence at about
  0.21 s each, spent waiting for ClickHouse.

## Isolation

| Condition | CVAT's own operations | Team Analytics |
| --- | --- | --- |
| worker scaled to zero, twelve analytics requests left waiting | sign-in, the task list, a job's data and annotations, saving annotations: all succeeded, 40 to 200 ms each, while the twelve waited | each of the twelve ended in 429 after 5.2 to 5.3 s; the page showed its error panel 30 to 36 s after it was opened |
| ClickHouse scaled to zero | all succeeded | overview and trends 503 `{"error":"unavailable"}` within 2.1 s; `status` 200 with every section null |
| totals database dropped | all succeeded | 503 and the null `status` right after the drop; schema, refresh, figures equal to before and complete history back by themselves 24 to 35 s later |

`check-analytics-off` reinstalled the release with analytics disabled: the initializer deleted
the stored `team_analytics_refresh` schedule, nothing was queued over 75 s, the five endpoints
were 404 signed in and signed out, and the server and the task list worked. The chart's render
with analytics disabled holds no analytics worker.

## Load

Twelve overviews that could not come from the cache, asked at once, three bursts per condition
(36 overviews), on the volume data. CVAT's own endpoints were sampled before and during. The
limit for them was 1.5 times the baseline's 95th percentile plus 25 ms, chosen for the jitter
of a desktop and a port-forward.

Final run:

| Condition | task list p95, before → during | job annotations p95, before → during | overviews with figures within the client's budget |
| --- | --- | --- | --- |
| during a refresh | 63 → 70 ms | 62 → 69 ms (424 samples under load) | 36 of 36 |
| while history is filled | 59 → 76 ms | 58 → 74 ms (423 samples under load) | 36 of 36 |

The overviews took 4.2 to 17.9 s, at most three attempts each. The client's budget with the
default settings is 29 s (four waits of 5 s, three pauses of 3 s); all 36 were also within 23 s.
The history condition is real: the checker marks 57 days for recomputation just before each
burst and fires when the minute's run holds the lock; 57 pending days became 49 during the
bursts.

Memory during the bursts: the worker 490 to 680 MiB, ClickHouse 0.55 to 1.54 GiB.

Two failures on the way, and what they led to:

1. On the first image, 6 of the first 12 overviews in a history fill got no answer within the
   budget. The refresh job held a worker process and ClickHouse through its whole budget. Since
   `2c653fe6` a run ends after a step as soon as a read is waiting.
2. On that image, with the history condition made to overlap, 26 of 36 came back within 29 s
   and 8 within 23 s. The worker's log showed the same read computed twice: the cache key named
   the generation of the totals, the generation moved with every day of history, and a request
   that asked again queued a second job behind its own first. Since `919d7ea0` the key names
   the request only, the answer carries the generation it was computed on, and the generation
   moves once per run.

One more run, as evidence only and with nothing committed: the worker with five processes on
the final image. Each read then took about 8 s, not 4.5 s, and fewer overviews fitted in 23 s
(34 and 29 of 36). Three processes already use the stack's two ClickHouse CPUs; the bound is
ClickHouse, not the process count.

## What CVAT recorded about the feature

- `send:exception` events caused by the feature are the refusals CVAT's handler logs for any
  endpoint: 165 permission refusals, 4 failed authentications, 1 not found, 1 not acceptable.
  No 5xx and no error line in the worker after its start.
- The failed-job registry of the queue held the id `team_analytics_refresh` once, while the
  job's own record said "finished". It was not traced; the reading is that a run was cut by a
  scale-down or a restart, since the periodic job reuses one id.

## After the service was deleted

`d00afd9c` removed the separate service and the lease in ClickHouse, and moved the calculation
tests onto the engine. On that tree: `verify/team_analytics_backend.sh`, 318 tests, none failed
(1,199 s, default ClickHouse image); the check pipeline, twelve hooks passed; `./build-server.sh`
built `cvat/server:v2.82.0-fork` (`0eb0b3582fb8`) with its three checks passing, and inside it the
app, the job and the routes exist with analytics on and are absent with it off, the queue being
defined for both.

The stack sequence above ran on the image before this commit. The commit changes what the worker
runs only by removing the branch that used the lease when no lock was given, which the backend
never took.

## On the final build, after the independent review

The two reviews (`2026-11-15-independent-review.md`) changed the read path, the refresh run, the
image build and the chart template (`b1655b51`, `6d77332a`). On that tree:
`verify/team_analytics_backend.sh`, 338 tests, none failed (1,144 s); the check pipeline, twelve
hooks passed; `./build-server.sh` built `cvat/server:v2.82.0-fork` (`4b5784d7d78f`), the same
image before and after the commits.

The whole stack sequence was then run again on that image and on the launcher of `27f47b5c`, in
its own namespace on port 8491. Everything above this section describes the earlier build; the
table below is the final one.

| Step | Result |
| --- | --- |
| `preflight`, fresh `up`, second `up` | passed |
| `check-fixes`, all steps | passed |
| `check-cross-org` | passed |
| `check-isolation`, all three parts | passed |
| `check-load`, both conditions | passed |
| `check-review` | passed |
| `check-analytics-off` | passed |
| `down` | passed; namespace gone, nothing on the port |

Load, with the twelve overviews of a burst made different by parameters the overview reads (36
projects in the refresh condition, 36 annotators in the history condition):

| Condition | task list p95, before → during | job annotations p95, before → during | overviews within 29 s | within 23 s | slowest | attempts |
| --- | --- | --- | --- | --- | --- | --- |
| during a refresh | 67 → 78 ms | 69 → 78 ms | 36 of 36 | 36 of 36 | 20.0 s | 1 to 3 |
| while history is filled | 77 → 81 ms | 69 → 78 ms | 36 of 36 | 36 of 36 | 20.5 s | 1 to 3 |

The baseline is 100 reads in sequence, the load sample 440. The machine's user started a
full-screen game during these runs, which may have added noise to the latencies. Memory during
the bursts: the worker 486 to 526 MiB, ClickHouse 648 to 1,177 MiB.

Read from the worker's log this time: in all six bursts twelve read jobs ran for twelve requests,
none twice. Each burst of the history condition recomputed 50 or 56 pending days in one run and
the generation moved by one for the burst (41 → 42 → 43 → 44).

Isolation: with the worker at zero each of twelve requests got 429 after 5.2 to 5.3 s while
CVAT's own operations took 45 to 210 ms, and the server held no Postgres connection for the
twelve (0 before, 0 during; six concurrent task-list requests showed 4 to 5, so the count sees
the server). With ClickHouse at zero, overview and trends answered 503 within 2.2 s. With the
totals database dropped, the schema and both organizations' figures were back after 14 s and
the refresh and complete history after 26 s.

What the review changed, seen on the stack (`check-review` and one trace by hand):

- An overview asked again with five values of `search` and five of an unknown parameter
  answered from the cache in 0.040 to 0.044 s each, and the worker's log shows no read for them.
- `tz` of 65 characters and `month` of 8 answered 400 "is too long" in 0.04 s with no job; a
  short but unknown `period` answered 400 from the worker, with one job.
- `Cache-Control: no-store` was on the 403 refusal, the 403 `organization_required`, the 401,
  the 404 for an unknown organization and the 429.
- The generation is a small integer. Over four runs of the refresh job it moved 48 → 49 → 50,
  stayed at 50 for a run with nothing due, then 51: one per run that wrote.
- With the worker at zero for three minutes the queue held three copies of the refresh job. An
  overview asked meanwhile got 429 after its 5.1 s wait, not at once from the depth limit. Eleven
  seconds after the worker was back no copy was left, and the overview answered.
- The chart rendered with `cvat.backend.worker.teamAnalytics.replicas=0` has `replicas: 0`.

Not reached on the stack: a Redis failure answered with 503, and a read job queued again after
its worker was killed. Both are read from the code only. The build's refusal for an untracked
file was provoked by hand (it refused and tagged nothing); the refusal for a rename was not.

## Only administrators create organizations

Decided by the owner after the review (ticket 15, IAM-2 of the fork specification). The server
image was rebuilt with the setting (`cbd8f8f05c54`); inside it `ORGANIZATIONS_MIN_ROLE_TO_CREATE`
reads `admin`, and `user` when upstream's environment variable says so. The check pipeline passed
with twelve hooks.

The default stack (port 8490) was then removed and installed fresh on that image and on
`cvat/ui:v2.82.0-fork`, and its `up` passed whole. It includes the new `check-org-creation`: four
accounts that are not administrators (the `user` role in no organization, the `worker` role, an
owner and a maintainer of an organization) were refused with 403 and no organization was left
behind; the administrator created one (201) and the check removed it; the two seeded
organizations answered their maintainers' `status` with 200.

The calculation suite and the load, isolation and analytics-off checks were not run again for
this change: it is one setting that only the organization-creation rule reads.

## After the second review pass

The fixes of the second review pass (`df8d9379`, see the independent review's record) were
checked without a stack. The calculation suite was run whole on that code: 341 tests, all
passed, on `cvat/clickhouse:23.12.2-debian-11-r0`. The check pipeline passed with twelve hooks.
The server image was rebuilt from it (`25b249e2e3e1`).

Not run on a stack before the branch was published: that image, and the two checks adjusted to
the fixes. `check-review` now holds the generation to one step for each refresh run that wrote
and none otherwise, read against the worker's log. `check-isolation clickhouse-down` now also
holds that the generation stands still over two failed runs, that an overview cached before the
outage is still answered from the cache, and that one never cached is 503. Both were checked
only for syntax, by the linter and by `preflight`. The default stack (port 8490) ran the image
before the fixes (`cbd8f8f05c54`) when the branch was published.

## Not verified

- On the build of the first sequence, that each read ran once per burst and that the generation
  moved once per run were inferred from the timing, and `Cache-Control: no-store` on a refusal
  was not read again after `2c653fe6` added it. All three were read on the final build; see the
  section above.
- A Redis failure answered with 503, a read job queued again after its worker was killed, and
  the generation standing still over several idle minutes (with the stack's 60 s interval a
  refresh is due at nearly every run; the one run seen with nothing due left it unchanged).
- A worker that fails its liveness probe; more than one worker replica; a cluster of more than
  one node.
- Load on more data than the volume organization, and on a ClickHouse with more than 2 CPUs.
- A release switched from analytics on to off by an upgrade in place; the check reinstalled.
- Upstream's Compose files, which do not start the worker.
- Production, which is air-gapped and out of scope.
