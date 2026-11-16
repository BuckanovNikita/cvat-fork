# Open lines closed, and administrators-only Team Analytics on the final images, 2026-11-16

Tickets 01 to 09 of `.scratch/team-analytics-admin-settings/` (ticket 09 for this record). The
final run used the launcher and code of commit `0bf2f41cd`; the load check's repeat rule was
corrected afterwards in `9a8620e96` and the load check run again. Two images were used: the
server image `7ead6d1cec4b` (work tag `cvat/server:v2.82.0-fork-wip2`), built from the tree at
`2883bb8c1`, and the UI image `1d1a6e3d425c` (work tag `cvat/ui:v2.82.0-fork-wip4`), built at
`6da9f526f`, the last commit that touches the UI packages. `git diff` over the paths the server
image copies (and over `Dockerfile.server` and `build-server.sh`) is empty between `2883bb8c1`
and `9a8620e96`, and over the UI packages, `Dockerfile.ui` and the lock between `6da9f526f` and
`9a8620e96`, so both images are those of the branch's tip. The stack logs print the UI image's
digest; for the server they print only the tag, and its id comes from the build log.

Everything on a stack ran in a namespace of its own (`cvat-ta-it-<run id>`, here
`cvat-ta-it-verify`) on host port 8491, beside the owner's stack on port 8490, which was not
touched. Times below are UTC, as in the logs. After the incident of 2026-11-16 (below) every
command that ran code went through a cgroup memory cap and a time limit. The run's logs are kept
outside the repository; the image comparison's four diff summaries and six screenshots are in
[`2026-11-16-open-lines-closed-and-admin-settings/`](2026-11-16-open-lines-closed-and-admin-settings/).

## The open lines of the earlier records

Every line of the "Not verified" sections of
[`2026-11-15-backend-acceptance.md`](2026-11-15-backend-acceptance.md) and
[`2026-11-15-full-fork-conversion.md`](2026-11-15-full-fork-conversion.md), the "Not established"
lines of [`2026-11-15-independent-review.md`](2026-11-15-independent-review.md), and two more
lines of the backend acceptance record that the plan named, one from its section "On the final
build, after the independent review" and one from "After the second review pass":

| Record | Open line | Now | What was run and seen, or the reason |
| --- | --- | --- | --- |
| backend acceptance | On the first sequence's build, one read per burst and one generation step per run were inferred from timing; `Cache-Control: no-store` on a refusal not read again | verified | Already read on the final build of 2026-11-15 (that record's section "On the final build"). Again on 2026-11-16: `check-review` saw 3 generation steps of +1 for 3 refresh runs that wrote and none for 1 run with nothing due, and `no-store` on the 403, 401 and 404 refusals; the load bursts' worker log is under "Load" |
| backend acceptance | A Redis failure answered with 503 | verified | `check-isolation redis-down`: with the in-memory Redis at zero, 12 reads (uncached overview and status, six rounds) were all 503 `unavailable` within 7 s; the refresh schedule was present afterwards and figures were back 58 s after the workloads were rolled out |
| backend acceptance | A read job queued again after its worker was killed | verified | `check-evidence killed-worker`: ClickHouse held with SIGSTOP so the read was mid-read, all 4 rq processes of the worker killed; the overview answered 429 for 299 s (35 answers), then 200, 305 s after it was first queued, against the abandoned limit of 300 s; the worker's log shows 2 executions of the job, the second "Job OK" |
| backend acceptance | The generation standing still over several idle minutes | verified | `check-evidence idle-generation`, refresh interval 600 s set by an in-place upgrade: generation unchanged over 360 s (22 samples) and 6 refresh runs with nothing due |
| backend acceptance | A worker that fails its liveness probe | verified | `check-evidence liveness`: one of 3 rq processes stopped; the event "Liveness probe failed: ... expected at least 3 live worker(s) ..., found 2"; the container restarted after 284 s, restarts 0 -> 1, the probe passes again |
| backend acceptance | More than one worker replica | verified | `check-evidence two-replicas`: 2 ready replicas; 12 uncached reads all 200; read jobs 6 and 6 by pod; 9 refresh runs that wrote, none overlapping |
| backend acceptance | A cluster of more than one node | ruled out | The test cluster has one node; a multi-node cluster is out of scope, as before |
| backend acceptance | Load on more data than the volume organization, and on a ClickHouse with more than 2 CPUs | verified | `TA_LOAD_HEAVY=1 check-load`: ClickHouse's CPU limit raised to 4 by an in-place upgrade; three volume organizations loaded (`ta-org-v`, `ta-org-v2`, `ta-org-v3`, 1000 sessions each), overviews read at instance scope; 36 of 36 overviews with figures within 29 s in both conditions; CVAT's p95 within tolerance (see "Load") |
| backend acceptance | A release switched from analytics on to off by an upgrade in place (the check reinstalled) | verified | `check-evidence off-then-on`: helm history "revision 9 Upgrade complete (before: revision 8)" for off and "revision 10 Upgrade complete (before: revision 9)" for on; while off all five read endpoints 404 for the administrator and signed out, no refresh scheduled, nothing added to the queue in 75 s; back on, the Technical accounts list and its table as before (`11|ta-bot`, 1 row), the schedule back, figures back after 26 s |
| backend acceptance | Upstream's Compose files, which do not start the worker | ruled out | Out of scope, as before: the fork runs on Kubernetes only (ADR 0003) |
| backend acceptance | Production, air-gapped and out of scope | ruled out | Out of scope, as before |
| backend acceptance, "After the second review pass" | Image `25b249e2e3e1` and the adjusted `check-review` and `check-isolation clickhouse-down` not run on a stack | verified, on a later image | Both checks passed on the final image `7ead6d1cec4b` (figures under "Final run"). `25b249e2e3e1` itself was not run again; it is superseded |
| backend acceptance, "On the final build, after the independent review" | The build's refusal for a rename not provoked | ruled out | The overlay build and its guards no longer exist: `build-server.sh` now builds the full image from a copy of the tracked files (ADR 0007) |
| full-fork conversion | Nothing on a running stack | verified | The 2026-11-15 acceptance record and this record |
| full-fork conversion | The build of the fork's tree with upstream's own `Dockerfile` | ruled out (superseded) | The fork builds the server from its own `Dockerfile.server`, a port of upstream's stages to Debian 12 (ADR 0007); upstream's `Dockerfile` is kept byte-identical and is not built |
| full-fork conversion | A merge of a release that changes the fork's edited files, or files under `.github/` | ruled out | The owner decided that this work makes no release merge and no source version update (the spec's "Out of Scope") |
| full-fork conversion | A fresh clone with dependencies installed from scratch passes the pipeline | verified | Fresh clone at `0bf2f41cd` with the release tag `v2.82.0` present and no `node_modules`, `verify/node_modules` or `tools/gate/.venv`: `yarn install --immutable` exit 0, `npm ci --prefix verify` exit 0, `prek run --all-files` exit 0 with twelve hooks passed |
| independent review | Whether ClickHouse cancels an insert whose client disconnected | still open | Nothing in this work looked at it; it moves to "Not verified" below |
| independent review | Why the failed-job registry once held the periodic job's id while its record said finished | verified, for the worker's start | rq 1.16.0's `clean_intermediate_queue`; see "The failed-job registry". The earlier "likelier reading" (copies of one id at once) is not the cause seen |
| independent review | Postgres connection counts and Redis memory under a real load | partly | Sampled every 2 s during the load bursts: Postgres client connections at most 13 and the in-memory Redis at most 3.6 MiB in the heavy run (at most 8 and 3.6 MiB in the regular one). This is the check's load, not a production one |

## Final run

On the stack described above, in this order (end time, exit status, seconds):

| End | Step | Exit | Seconds |
| --- | --- | --- | --- |
| 23:19:16 | `down` | 0 | 53 |
| 23:19:27 | `preflight` | 0 | 11 |
| 23:39:05 | `up` (fresh) | 0 | 1178 |
| 23:55:27 | `up` (second) | 0 | 982 |
| 00:07:52 | `check-fixes` | 0 | 745 |
| 00:08:13 | `check-cross-org` | 0 | 21 |
| 00:16:11 | `check-review` | 0 | 478 |
| 00:16:53 | `check-isolation worker-down` | 0 | 42 |
| 00:18:55 | `check-isolation clickhouse-down` | 0 | 122 |
| 00:19:27 | `check-isolation totals-dropped` | 0 | 32 |
| 00:27:55 | `check-load` | 1 | 508 |
| 00:27:57 | `check-evidence rq-start-race` | 0 | 2 |
| 00:32:44 | `check-evidence liveness` | 0 | 287 |
| 00:37:57 | `check-evidence killed-worker` | 0 | 312 |
| 00:54:50 | `check-evidence idle-generation` | 0 | 1013 |
| 01:07:39 | `check-evidence two-replicas` | 0 | 769 |
| 01:23:45 | `TA_LOAD_HEAVY=1 check-load` | 0 | 966 |
| 01:26:23 | `check-evidence off-then-on` | 0 | 158 |
| 01:28:22 | `check-isolation redis-down` | 0 | 119 |

Then, on the same stack: `check-load` alone at 0bf2f41cd (01:36:22, exit 0, 387 s), `check-load`
at `9a8620e96` (01:48:22, exit 0, 474 s) and `down` (01:49:53, exit 0, 52 s).

### `up`: settings and access

`up` runs the settings check, the issue matrix (124 rows passed), the access cases and the
organization-creation check. Every part passed:

| Part | Seen |
| --- | --- |
| refusals | 24 requests of three accounts that are not administrators refused 403, 4 signed out 401, the list unchanged |
| writes | `no-store` on 200, 400 and 403 of the settings; PUT with the cookie and `X-CSRFToken` 200, without the token 403; a read-only token reads (200) and is refused on PUT (403); `.json` paths 404, plain paths 200; HEAD on status and settings 200; no warning about the removed variable in the server's log |
| bad bodies | 7 bad bodies and 2 bodies that are not JSON refused 400 `bad_request`; the list and the generation unchanged |
| generation | every save advanced the generation by one: adding, saving the same list again (200, list unchanged) and removing |
| user search | users of another organization and of none found with an organization selected; 20 rows for the empty search, `ta-` and `ta-volume-annotator-`; a long search refused |
| retroactive | with `ta-worker-s` on the list it is no longer an annotator (600000 ms of working time and 1 session fewer, Model +4); removed, the overview and the list equal the first read |
| project names | one answer names `ta-org-a`'s 1 and `ta-org-s`'s 45 projects and leaves out id 2000000000; bad ids and 501 ids 400 |
| deleted user | a throwaway user stayed listed after its deletion (deleted, with its last name), was kept, removed, then refused when added again |
| access: `revoked-admin` | 200 while in the admin group; taken out of it, 403 on its next 8 requests (old session and a fresh one, all within 0.4 s); back in the group, 200 again |
| access: `group-admin` | an account in the admin group that is not a superuser reads instance scope and `ta-org-a`, as the superuser sees them |
| access: `personal-workspace` | 20 min of work in a personal workspace appear under instance scope and under none of 8 organizations |
| access: header credentials | 13 accounts x 2 endpoints decided as with the cookie, with Basic and with Bearer |
| organization creation | 4 accounts that are not administrators refused (403, nothing created); the administrator created one (201) |

The final run inside `up` read every figure as an administrator: `ta-admin` got 200 on the five
read endpoints with no organization, `ta-org-a`, `ta-org-v` and `ta-org-c`; owners, maintainers,
a supervisor, workers, an outsider and `ta-bot` got 403 on all five, with and without an
organization; signed out 401.

### `check-fixes`

`status-roles`, `technical-project`, `gestures`, `look`, `unprocessed`, `sessions-at-limit` and
`cutover-restart` passed as before. The `page` step, new in this work, passed whole:

| Part | Measured |
| --- | --- |
| filter bar | 5 controls 36 px at 1024, 1400 and 1920 px; one line at 1400 and 1920 px (centre 148), two lines at 1024 px (centres 148 and 192); Settings 36 px at the right end of the header; the freshness stamp 36 px |
| width sweep | 127 widths from 1024 to 1920 px (every 8 px, every pixel around a change of columns); columns change at 1371 px (2 to 3) and 1807 px (3 to 4), each with a 420 px card; narrowest operations card 420 px at 1371 px; the operations card never scrolls sideways |
| other cards that scroll | creation methods at 42 widths (1024-1920 px); details at 34 widths (1024-1288 px) |
| operations table | columns Operation, Boxes, Avg time, Total time, Share; each operation followed by its "started by" line |
| selectors, volume organization | each selector sends one list request (`by=projects`, `by=annotators`, no other filter) and none on reopening; Escape closes and returns focus; a click outside closes. Project: 41 options, a long name narrows them to 2, picking it sets `project=7` and changes the figures; Annotator: 101 options, picking one sets `annotator=19`; All and the clear button remove both filters |
| open popups | at 1024, 1192 and 1400 px each open popup and its longest option lie inside the page container; the document is no wider with a selector open than with both closed |
| terms | 13 terms on the overview (Model row and Model column shown), each tooltip shown on hover and on focus, inside the window, with the glossary's text, hidden after; the full view of annotators has none |
| settings dialog | lists `ta-bot`; `ta-bot` offered disabled, "already on the list"; a search found `ta-owner-b` of another organization; added, removed, Cancel: no PUT; Save of the same list: one PUT, the dialog closed with no error |
| instance-scope project names | 51 project options, none named "Project #N" |

### `check-cross-org`, `check-review` and isolation

- `check-cross-org`: `ta-org-a`, `ta-org-b` and instance scope each got their own figures in either
  order with the same parameters; an answer the administrator cached was not served to a
  maintainer (403).
- `check-review`: 10 requests with ignored parameters served from the cache, 0 read jobs; too-long
  `tz` and `month` 400 from the API with no job; an unknown period 400 from the worker;
  `no-store` on every refusal; the generation as above; with the worker at zero for 180 s, 3
  copies of the refresh job queued and an overview 429 after 5.07 s with `Retry-After: 3`; after
  the worker came back, 0 copies after 11 s and the overview 200.
- `worker-down`: CVAT's sign-in, task list, job, data, chunk, annotations and saves all 200 while
  12 analytics requests waited; all 12 got 429 within 7 s; the server's Postgres connections
  0 -> 0.
- `clickhouse-down`: core operations 200; generation unchanged over 2 failed refresh runs; an
  overview cached before the outage served (200 in 0.032 s), one never cached 503 in 0.09 s.
- `totals-dropped`: the totals database dropped; core operations 200; overview 503, status 200;
  the database, history, cutover and both organizations' figures back by themselves after 21 s.

### Load

The regular `check-load` read 12 concurrent uncached overviews of `ta-org-v` in three bursts per
condition (a refresh, and history being filled). Client budget 29 s; tolerance for CVAT's own
endpoints: p95 under load at most 1.5 x the baseline p95 + 25 ms.

| Run | Overviews with figures | Worst p95 under load (limit) | Worker max | ClickHouse max | Postgres connections max | Redis max |
| --- | --- | --- | --- | --- | --- | --- |
| final run, 00:27 | 36 and 36 within 23 s; the check failed (below) | 66 ms (101-104 ms) | 715 MiB | 1325 MiB | 8 | 3.6 MiB |
| alone, 01:36, checker of `0bf2f41cd` | 36 and 36 | 70 ms (103-111 ms) | 715 MiB | 1687 MiB | 3 | 3.5 MiB |
| alone, 01:48, checker of `9a8620e96` | 36 and 36 | passed, within tolerance | 715 MiB | 1611 MiB | 2 | 3.4 MiB |
| heavy, 01:23 | 36 and 36 within 23 s | 74 ms (104-115 ms) | 559 MiB | 1765 MiB | 13 | 3.6 MiB |

The heavy run is the one described in the table of open lines: ClickHouse at 4 CPUs, three
volume organizations, overviews at instance scope. Its slowest overview took 12.6 s.

#### The load check's one failure

In the final run's refresh condition, burst 2, the worker's log held 13 read jobs for 12
requests: one read (`overview`, organization 4, week, project 19) ran twice. The generation was
`...4931` at the end of burst 1 and `...4932` at the start of burst 2, with one refresh run inside
burst 2's log window. All 36 overviews of the condition had figures within 23 s and both p95
were within tolerance. The checker counted the repeat as a bad overview, which is why its result
line says "35 with figures within 29 s (36 within 23 s)". It also failed the history condition
with the same entry, although every history burst's own line says "repeated none": its list of
repeats was shared by the two conditions and not reset.

The likely reading, not proven: the read started just before a refresh run that wrote advanced
the generation, so its answer was stored as older than the totals, and the request's next
attempt computed it again. That is what `reads.fetch` and `jobs._read_answer` are written to do.
The worker's log of that moment was lost to later restarts, so the order was not read. rq's
ten-minute maintenance does not coincide with it (pod start 00:16:29, burst at about 00:23).

Two clean reruns followed on the same stack: the first with the same checker (six bursts of 12
read jobs for 12 requests), the second with the checker of `9a8620e96`. That commit fixes both
defects: a repeat is allowed only when a refresh run that wrote ended between its two starts
(read from a window of the worker's log reaching two minutes before the burst), three runs of
one read or a repeat with no such run fail, and each condition keeps its own repeats. The
second rerun had no repeat, so the allowing branch of the corrected rule has not been seen
firing on a stack.

### `check-evidence`

| Step | Figure |
| --- | --- |
| `rq-start-race` | the worker pod started at 00:16:29; its failed registry held one `team_analytics_refresh` entry added at 00:15:59, before that pod started, which the step does not judge; no failed entry since the start, so the race did not occur on this start; the intermediate list empty |
| `liveness` | as in the table of open lines: restart after 284 s, restarts 0 -> 1 |
| `killed-worker` | 429 for 299 s over 35 answers, then 200; 2 executions |
| `idle-generation` | unchanged over 360 s and 6 runs with nothing due |
| `two-replicas` | 2 ready, 12 reads 200, read jobs 6 and 6, 9 writing runs none overlapping |
| `off-then-on` | revisions 8 -> 9 -> 10, "Upgrade complete" each; 404 while off; list intact |

## The server image

The server image is built from public bases (ADR 0007): `python:3.12-slim-bookworm`, with
`rust:1.85-slim-bookworm` and `golang:1.27.2` stages, each pinned by digest as an `ARG` default
in `Dockerfile.server`. No Dockerfile of the fork starts `FROM cvat/` except upstream's own
`Dockerfile.ci` (`FROM cvat/server:local`), unchanged from `v2.82.0` and not built by the fork.

The final build (`7ead6d1cec4b`, from 710 tracked files, as many as `git ls-tree` lists under
the copied paths at `2883bb8c1`) passed every check of `build-server.sh`
before tagging: the bundle with and without analytics equal to the tree's `issues.rego`,
`comments.rego` and `team_analytics.rego`; `python`, `python3`, `django-admin` and `uvicorn`
resolve to the virtual environment and run on Python 3.12; supervisord 4.2.5; `nginx -t`
accepts `/etc/nginx/nginx.conf`; 458 shared objects of the virtual environment and FFmpeg
scanned with no missing dependency; Django sets up on the production settings with
`CVAT_ANALYTICS=1` (app installed, API routed) and `0` (neither); `makemigrations` reports "No
changes detected". The `non-free` component is enabled for `unrar` and removed again in a later
layer.

### One-time comparison with the overlay image

The comparison was made once, against the first from-scratch image, `baa5a8b72149`
(2026-11-15, the tree of `eadf981f7` with the Dockerfile of `aa9a4e659`), not against the final
one. The other side was the overlay image then tagged `cvat/server:v2.82.0-fork`,
`25b249e2e3e1`, built from `main` on stock `cvat/server:v2.82.0`. The tree's commit was found by
the hashes: `views.py`, `jobs.py`, `technical_accounts.py` and `cvat/settings/base.py` in the new
image equal those of `eadf981f7` (`views.py` differs from `3f1c7d645`'s).

| What | Result |
| --- | --- |
| installed Python distributions | identical: 134 of 134, the same versions (the diff file is empty) |
| `/opt/cvat` by sha256, `.pyc` left out | 705 files in the old image, 710 in the new; what differs or is added is exactly the 34 files the branch changed under the copied paths at `eadf981f7` (29 changed; 5 added: `models.py`, `serializers.py`, `technical_accounts.py`, `migrations/__init__.py`, `migrations/0001_initial.py`); nothing else |
| configuration | the same user (`1000:1000`, `django`), entry point and working directory; the environment adds `GPG_KEY`, `PYTHON_SHA256` and `PYTHON_VERSION=3.12.16` from the Python base and has `/usr/local/bin` once more in `PATH`, after `/opt/venv/bin`. `/home/django` in this file is the image's home directory, not a path of the build machine |
| system | Debian 12 (glibc 2.36) for Ubuntu 24.04.5 (2.39); Python 3.12.16 for 3.12.3 in the virtual environment; Debian's `python3` 3.11.2 (used by supervisord only) for 3.12.3; nginx 1.22.1 for 1.24.0; unrar 6.21 for 7.00; 7-Zip 26.02 for 23.01; git 2.39.5 for 2.43.0; the same binaries present (smokescreen, wait-for-it, pdftoppm, 7z, unrar, nginx, supervisord, uvicorn, django-admin) and the same FFmpeg and OpenH264 library names |

The four diffs are kept as `image-compare-diff.{distributions,tree,config,binaries}.txt` in the
directory beside this record.

Never built: the `CLAM_AV=yes` and `CVAT_DEBUG_ENABLED=yes` branches of `Dockerfile.server`.

## The suites

| Suite | Result |
| --- | --- |
| calculation suite, branch's app on `7ead6d1cec4b`, `cvat/clickhouse:23.12.2-debian-11-r0` | first run 370 tests, 1 failure in 1366 s: a new test, `test_the_overview_under_its_id_is_empty`, expected the rows by annotator to be empty under a filter on a technical account's id, but they keep the people (a wrong expectation, not a product fault); corrected in `5dea1cc89`; rerun at `5dea1cc89`: 370 tests, OK, 1259 s |
| frontend suites through `tools/gate/node-suite.sh` (8 GiB address space per process, one minute per test) | the wrapper's own logs: page 289 of 289 (written about 20 minutes before `3b682f584`, `ebf221ef7` and `6da9f526f` were committed), logging 77 of 77, task progress 20 and 1 skipped, 21 of 21 with a browser. A minute after those three page commits the page lane's run shows 294 of 294; its log does not record whether it went through the wrapper. The fresh clone's `prek` at `0bf2f41cd` ran all three suites through the wrapper and they passed; it prints no counts |
| policy tests | the patched policies, the stock policies and upstream's generated suite passed in the fresh clone's `prek` |
| `prek run --all-files` in the working tree | twelve hooks passed, exit 0, run after `9a8620e96` was committed (by the log's file time); the log does not name its commit |
| fresh clone | see the table of open lines |

## The failed-job registry

Diagnosed on 2026-11-15 on the owner's stack, image `25b249e2e3e1`, read-only. Established for
a worker's start:

- The Team Analytics worker pod started at 15:59:40 with three rq processes; rq is 1.16.0 (read
  in the image as `rq.__version__`).
- The log at 15:59:42, in this order: one process "Cleaning registries for queue: team_analytics"
  (,040); another dequeues `team-analytics-read-4f79...` (,043); the cleaning process "Handling
  failed execution of job team-analytics-read-4f79..." (,043); the dequeuing process "Started Job
  Registry set" and "Preparing for execution" (,054-,055). The same for `team_analytics_refresh`
  (dequeued ,048; "Cleaning registries" ,051; "Handling failed execution" ,054; "Preparing for
  execution" ,057). Both jobs then ran, and later runs say "Job OK".
- The source in the image, `rq/maintenance.py` lines 10-26, called from `worker.py:320` in
  `clean_registries`, which a worker runs when it starts and then periodically under a
  maintenance lock: `clean_intermediate_queue` fails every job id in the queue's intermediate
  list that is not in the StartedJobRegistry (`handle_job_failure(..., exc_string='Job was stuck
  in intermediate queue.')`), with no grace time. A job that another process has just moved to the
  intermediate list and not yet registered as started is failed by it.
- In Redis afterwards: `rq:failed:team_analytics` held `team_analytics_refresh` with score
  1826294382 = 1794758382 + 31536000, added at 15:59:42 with rq's default failure time to live of
  one year; the job's record said `finished` and had no `exc_info` field, because the scheduler
  creates the job again under the same id every minute; the intermediate list was empty. This is
  the acceptance record's "held the id `team_analytics_refresh` once, while the job's own record
  said finished".
- Effect: none on the figures. The refresh ran in the same second and the read job's answer was
  stored. The read job's failed entry expires with its `failure_ttl` of 60 s; the refresh job's
  stays for a year as a stale id. Any queue with more than one worker process started together
  can show the same. It is recorded as a limit of upstream's pinned rq; the pin is not changed.

The final run's `rq-start-race` step saw no such entry on its pod's start (above).

## Independent review

Three passes, each by reviewers who wrote none of the code, read-only, given the code and
questions rather than the authors' conclusions. None ran anything.

1. First review, of `main..25adcb85a`, by three reviewers: backend and access (the app and the
   calculation suite); the page; delivery (the image build, the stack checks and the documents).
2. Second look, by one fresh reviewer, of the fixes from `25adcb85a` on: no high finding; every
   first-review finding fixed in the code except two, fixed only partly (page F6 and N4). It
   checked about 25 rewritten assertions and found none weakened.
3. Third look, by one fresh reviewer, of `0c8339759..9a8620e96`, code only: nothing high or
   medium.

Found to hold by reading, among others: only administrators get figures, settings, the user
search and project names, for every method and every way of naming an organization; the
permission check runs before the cache and before every Postgres read of the app; rego, CSV and
generator agree with the Python; CSRF on PUT; the body rules; the table lock cannot deadlock;
a refused PUT changes nothing; the worker reads the generation and then the list on every path;
all 31 predicates match `user_id` as bound parameters; the header differs from upstream's only by
the link; the page's option cache, its handling of late answers, its tooltips and its dialog's
load, search and save paths hold; `Dockerfile.server`
matches upstream's stages, with no build tools in the runtime stage, exactly three pulls, and the
image tagged only after every check; no local path, name, e-mail or token in the range.

Severity is as the reviewers gave it; "not rated" marks a finding they gave no rating (nothing
was rated high; the backend reviewer rated all its findings low).

| Pass | Finding | Severity | Done |
| --- | --- | --- | --- |
| 1, backend | F1 a committed save answers 503 when the generation advance fails | low | robustness fixed `1d58d768f`; the 503 stays, a limit |
| 1, backend | F2 the read job held a Postgres connection through the ClickHouse read | low | fixed `a4e0885eb` |
| 1, backend | F3 overview saved boxes counted a technical account's boxes under `annotator=<its id>` | low | fixed `487bc46ae`, with suite tests |
| 1, backend | F4 a PUT body of another content type left as DRF's 415 | low | fixed `1d58d768f` (the app's 400) |
| 1, backend | F5 `.json`-suffixed paths routed, 500 to administrators | low | fixed `0406d9979` (not routed) |
| 1, backend | notes: stored name as fresh as the last save; an unchanged save still advances; a user deleted during a save; the variable read once to warn | note | recorded as limits; why the variable is still read, commented in `7ebe97774` |
| 1, page | F1 a non-administrator saw Settings, the filter row and the scope label until the 403 | medium | fixed `09ac22a85` (decided from the account's group, no request) |
| 1, page | F2 the dialog stayed open over the refusal panel | not rated | fixed `09ac22a85` |
| 1, page | F3 typing then Enter picked "All"; F4 focus lost after clearing; F9 stale options after a period change; F10 a popup could make the page scroll sideways | not rated | fixed `947be8a66`; F10 checked in the browser |
| 1, page | F5 a hover-opened tooltip not dismissed by Escape | not rated | fixed `0c5ccc24a` |
| 1, page | F6 Cancel during a save, a late result in a reopened dialog, no double-save guard; F7 the search's 20 filtered after the cap; F8 a failed search read "No users found" | not rated | fixed `c9170ac56`, `a741d9d4e` |
| 1, page | N4 unknown ids asked again; T1 two dropped assertions | not rated | N4 fixed `09ac22a85`; T1 restored `969e7036b` |
| 1, page | N1, N2 ticket wording; N3 a 503 after a committed save does not say figures keep the old list | note | tickets corrected; N3 recorded with the limit |
| 1, delivery | S1 killed-worker could pass without killing anything; S6 worker left at zero after a timed-out scale-down; S7 weak assertions | medium (S1); S6, S7 not rated | fixed `07d362543`, `5cce53cf3` |
| 1, delivery | S2 two-replicas passed with no refresh runs found | medium | fixed `5cce53cf3` |
| 1, delivery | S3 off-then-on did not restore on failure; S4 the HTTP port not tied to the namespace; S5 an interrupted upgrade could leave values changed | medium (S3); S4, S5 not rated | fixed `0b2942412` |
| 1, delivery | S8 no check that an administrator out of the admin group is refused at once | not rated | added `142fea153` (`revoked-admin`) |
| 1, delivery | B1 `ldd`'s exit status could make the library check vacuous; B2 the Go stage pinned only in the script; B3 `non-free` left in the final apt sources; B6 nginx unchecked | not rated | fixed `074f69d1a`; re-read by the delivery reviewer |
| 1, delivery | B4 base image environment variables | not rated | compared and stated (above) |
| 1, delivery | D1-D6 documents and tickets said more than the code | not rated | corrected `663a3f3f9`, `06fdc1880`, `94fea2172`, `4edccebeb`, `f320da121`, `4fe9cf2f0` |
| 2 | 1 a save that never answers locked the dialog | medium | fixed `3b682f584` (a save is waited for at most 30 s) |
| 2 | 2 backend F1, F4, F5 untested at the view or route level | medium | F4, F5 and HEAD added to the stack's settings check (`593154d91`, `4bd1dbea3`); the 503-after-commit path stays checked only by the author's container run |
| 2 | 3 deleted-project ids asked again after a partial failure; 4 a shifted popup lost its 360 px cap | low | fixed `ebf221ef7`, `6da9f526f` |
| 2 | 5 two-replicas can fail a correct system about 1 time in 32 by design | low | recorded; the failure message says so |
| 2 | 6 killed-worker read only the current container's log; 9 a failing restore could hide the original failure; the popup measured before its options loaded | low, note | fixed `4bd1dbea3`, `593154d91` |
| 2 | 7 an older launcher's port-forward state file refused until `run.sh forward`; 8 a test creating WebAssembly memory could fail under the 8 GiB limit | note | recorded |
| 2 | 10 `BROWSER_BIN` took the memory limit off all three suites | low-medium | fixed `0c8339759`, read by the reviewer |
| 3 | 1 after the 30 s limit a second save can be overtaken on the server by the first | low | recorded (stop rule) |
| 3 | 3 the settings check's "HEAD answers with no body" half cannot fail | low | recorded (stop rule) |
| 3 | 4 the page step's instance-scope project names can pass with an organization whose switch failed | low | recorded (stop rule) |
| 3 | 5 check-load's repeat rule has two narrow windows | low | recorded (stop rule) |

The third look's findings are numbered 1, 3, 4 and 5, as it gave them. It also found the per-save
token correct in every order of events, the popup baseline excusing only the overflow CVAT's own
layout already has at 1024 px, and `5dea1cc89` consistent with the product's rule.

Stop rule: low findings of the last pass are recorded, not fixed. The four are limits in
`docs/fork-specification.md`. Running the checks on the stack found problems in the checks
themselves: the page step's data, its organization switching and its popup baseline
(`9f5f188eb`, `a6fa266ac`, `0bf2f41cd`), and the load check's repeat rule (`9a8620e96`).

## The incident of 2026-11-16

Between 00:01 and 00:14 local time, while page finding F2 was being fixed, an agent ran a new page
test against the page code without its fix, to see it fail. The assertion
`assert.equal(<mounted dialog element>, null)` failed; Node formatted the failing value and walked
the element's React fiber graph without bound. The process grew to 49.5 GB, the virtual machine
thrashed (load 721, 6.9 GB available) and WSL was shut down.

The cause was the test's assertion on a mounted DOM element, not the page. It was reproduced
inside a 3 GB cap, where it was killed after 8 s, and a capped copy of the code showed that the
page sends one request per refusal and does not loop.

What the repository now has against it:

- the page suite's helper reports a DOM node in a comparison as a short description
  (`<div class="...">`) and fails a test after 300 requests (`e1ad3c2af`);
- 27 assertions on page elements rewritten to compare booleans (`2883bb8c1`);
- `tools/gate/node-suite.sh`, through which the pipeline runs the three frontend suites: an
  8 GiB address-space limit per process and one minute per test (`98b63dc0d`, `6ca8d692d`,
  `0c8339759`). With `BROWSER_BIN` set only the task progress suite runs without the memory
  limit, because a browser does not start inside it.

Since then every command of this work that ran code went through a cgroup memory cap and a time
limit.

## Found on the way, not changed

- At a 1024 px window, with both selectors closed, the document is 1103 px wide on the Team
  Analytics page. The page step's log names a cell of the details table as the element reaching
  furthest right (`td` in `cvat-team-analytics-details-row`, right edge 1228 px); that cell is
  inside the page's own scrolling area and is not what sets the width. Measured afterwards on the
  owner's stack as the administrator, with the stack's browser helpers: on CVAT's own pages
  (`/tasks`, `/projects`, `/jobs`) the document is 1024 px at a 1024 px window; on
  `/team-analytics` it is 1103 px, and so are the application's layout container, its header and
  its main area, while the page's own element is 1009 px wide. The layout's main area, and the
  header with it, take the minimum width of the page's content, which the page's own cap at the
  window's width does not pass up to them. The effect at a window narrower than about 1103 px:
  the document scrolls sideways and the right end of the header (the user menu) is off the
  screen. At 1400 px the document equals the window. This was measured on the branch only, not
  compared against `main`, and was not changed. At 400 px the final run and the `look` step
  print the same 1103 px for the header.
- The creation-methods card's table scrolls sideways at 42 swept widths (1024-1920 px) and the
  details card's at 34 (1024-1288 px). The owner chose to leave cards other than the operations
  card as they are.

## Not verified

- The third look's four recorded findings: a save overtaken after the 30 s limit (it needs a
  proxy that holds a request over 30 s and then delivers it); the HEAD "no body" half of the
  settings check; the page step's instance-scope names part with a failed organization switch;
  the load check's two narrow windows.
- The corrected repeat rule allowing a repeat on a stack: no repeat occurred in the run that used
  it.
- That a newer rq no longer does this. rq's changelog was read afterwards, not tried: under
  1.16.2 (2024-05-01) it lists "Fixed a bug that may cause jobs from intermediate queue to be
  moved to FailedJobRegistry", and nothing about it under 1.16.0, 1.16.1 or 2.0. The fork keeps
  upstream's pin of 1.16.0.
- The failed job's `exc_info`: the record had none (it is recreated every minute), so the cause
  rests on the log order and the source, not on the stored failure text.
- Whether ClickHouse cancels an insert whose client disconnected.
- The `CLAM_AV=yes` and `CVAT_DEBUG_ENABLED=yes` builds.
- The build's refusal when upstream's `Dockerfile` changes: provoked only by the build lane
  before the first build, as its own report states; not repeated for this record.
- The user search matching first and last names: read in the code (`icontains` on username,
  first and last name); the stack's check asserts the username match, the cap of 20 and the
  order only.
- A 503 after a committed save, at the view level: only in the author's container check.
- Screen-reader output of the page, the selectors and the dialog.
- A real double click on Save in a browser (the page suite clicks twice in one go).
- CVAT's global Escape handlers beside an open tooltip, in a browser.
- The two-replicas step's designed failure odds (about 1 in 32 on a correct system) were not
  measured.
- A real interrupt during a chart upgrade, with the restore path.
- A saved change of the list through the dialog being reflected on the next page load, in a
  browser: the browser step saved an unchanged list; the change's effect on figures was shown
  through the API (`retroactive`).
- The page at 1024 px against `main`.
- Load with production data or production concurrency; a cluster of more than one node;
  production.

## Delivery, added after the runs above

- `./build-server.sh` under the release tag gave `cvat/server:v2.82.0-fork` with the id the runs
  used (`7ead6d1cec4b`), every check passed. `./build-ui.sh` under the release tag gave an image
  with another id (`30adaed8cf00`) than the one the runs used; why two builds of the same commit
  differ was not established. The release tag `cvat/ui:v2.82.0-fork` was pointed at the image the
  runs used (`1d1a6e3d425c`). The previous images are kept as
  `cvat/server:v2.82.0-fork-before-20261116` and `cvat/ui:v2.82.0-fork-before-20261116`.
- The owner's stack (default namespace, port 8490) was removed and installed fresh on those two
  images with the launcher of this branch: `down` exit 0, `up` exit 0 with every part passed. Its
  pods report the image ids above. `run.sh check-fixes page` then passed against it (the same
  measurements as in the final run: five controls 36 px at 1024, 1400 and 1920 px, the width sweep
  with no sideways scroll in the operations card, both selectors, 13 terms, the settings dialog,
  project names at instance scope), and its screenshots were looked at. No person clicked through
  the page.
- The check pipeline passed with twelve hooks at the last commit that changes code or checks
  (`9a8620e96`) and again at the commit that closed the delivery ticket; the commits between
  change documents only.
- The verification namespace was deleted, with nothing left listening on its port; the work
  image tags were removed.

Not in this record: the push of the branch, which follows it.