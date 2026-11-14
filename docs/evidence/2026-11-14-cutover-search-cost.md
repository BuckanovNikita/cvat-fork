# Cost of the cutover's long-range search (2026-11-14)

Ticket 17 of the defect fixes lets the service look for the cutover in the recorded events
at start and in the daily check. That is one aggregate over the raw events from the first
event on. The defect-fix spec asks for its cost to be measured on a loaded volume before
it is adopted, and names a fallback if it is too costly.

Files: [`2026-11-14-cutover-search-cost/`](2026-11-14-cutover-search-cost/) (`run.sh` is
the whole procedure; `search.sql` is the statement as it ran; `setup.txt`, `runs.txt` and
`report.txt` are its output).

## What counts as acceptable

Written before the figures were read.

- **At start.** The search runs before the service opens its port. The liveness probe of
  `team-analytics/k8s/deployment.yaml` first looks 30 seconds after the container starts
  and restarts it after three failures 20 seconds apart, so a start that lasts about 70
  seconds is killed. The search is acceptable at start when the slowest cold run over the
  full range takes at most a third of that, 23 seconds. Above that it is reported as too
  costly at start, and the fallback of the spec applies.
- **In the daily check.** The search runs under the refresh lease, so a due ten-minute
  refresh waits for it. It is acceptable when it takes at most a tenth of the refresh
  interval, 60 seconds.
- **Memory.** Peak memory of at most 512 MiB, a quarter of the 2 GiB the seam 1 ClickHouse
  runs with. The design measurements' long-range queries that failed did so at the 9 GiB
  server limit.

The deciding figure is the slowest cold run over the full range.

## How it was measured

- One throwaway container of `cvat/clickhouse:23.12.2-debian-11-r0`, the image the Helm
  chart runs, with `--cpus 2 --memory 10g`, no published port, reached with `docker exec`.
- The data is the benchmark fixture of the design measurements
  (`2026-11-13-team-analytics-clickhouse-benchmark/`): its `events` schema and its
  generator, loaded month by month and merged with `OPTIMIZE FINAL`. The generator's
  `base_n` parameter was not recorded there, so `run.sh` finds it by bisection on the
  number of rows the generator would write (`expected_rows.sql`).
- The statement is the service's own file,
  `team-analytics/service/sql/control/cutover_find.sql`, with the database names
  substituted as the service substitutes them and with the service's query setting. It
  ran with `until` set after the last event, so it read the whole table, as the search
  does while no cutover is stored. `search.sql` is the text that ran.
- A cold run: before it, the files of the `events` table were dropped from the page cache
  (`POSIX_FADV_DONTNEED` through `dd iflag=nocache`, this container's files only) and the
  server's mark cache was dropped. The page cache charged to the container was read
  before and after to see that the files had left it. What the disk under the Docker
  virtual machine caches on its own side is outside this.
- Time, peak memory, rows and bytes read come from `system.query_log`.

This is not the design measurements' setup, and the two are not to be compared as equals:
those ran with 6 CPUs on ClickHouse 23.11.5 and warm caches only; this ran with 2 CPUs on
23.12.2, on a machine its user was working on at the time, with other agents' jobs held
off by a lock only for the duration of the runs.

## What was measured

The data came out as in the design measurements: `base_n` 325 gives 36,326,651 rows from
2025-11-14 to 2026-11-13, 13 parts, 2.44 GiB on disk and 10.07 GiB uncompressed, of which
the `payload` column is 1.26 GiB and 4.94 GiB. The search matches 11,566,490 of the rows
(every shape operation of the fixture is tagged), and found the first hour of the data,
2025-11-14 06:00.

The procedure ran twice, about fifty minutes apart, on the same loaded container. The
files hold the second pass; the first pass's lines are quoted from its log.

| Run | Time, pass 1 | Time, pass 2 | Peak memory | Rows read | Read from disk |
| --- | --- | --- | --- | --- | --- |
| Full range, cold | 4.62, 4.37, 4.40 s | 6.49, 4.70, 4.67 s | 62–64 MiB | 36,326,651 | 1.77 GiB |
| Full range, warm | 3.27, 3.23, 3.19 s | 3.84, 3.62, 3.50 s | 61–63 MiB | 36,326,651 | 0 |
| Bounded by the stored cutover | 0.003 s | 0.004 s | 42 KiB | 0 | 0 |
| Variant, a key no payload holds, cold | 3.95 s | 4.12 s | 17 MiB | 36,326,651 | 1.62 GiB |
| Variant, a key no payload holds, warm | 3.14 s | 3.57 s | 17 MiB | 36,326,651 | 0 |

- A full-range run reads every row and 7.68 GiB of uncompressed columns, and used between
  5.5 and 7.2 seconds of CPU time on the two cores in every run but one. Its memory stayed
  at 61 to 64 MiB whatever the run: it is one aggregate with no sort and no window.
- The cold runs were cold for the container: each read 1.77 GiB from the disk where the
  warm runs read nothing. In the second pass the page cache charged to the container
  (`runs.txt`, bytes from the container's memory counters) fell from 1.8–2.0 GB to
  0.08 GB at each eviction. In the first pass it fell from 4.4–5.1 GB to 2.5 GB: about
  2.5 GB of other files stayed cached, most likely the parts the merge had just replaced
  and not yet deleted, since their size fits and they were gone by the second pass. The
  files the search reads were evicted in both passes, as the 1.77 GiB of disk reads show.
- The first cold run of the second pass took 6.49 s and 11 s of CPU time, against 4.4 to
  4.7 s and 6 to 7.2 s for the other five cold runs. Nothing in the procedure differed;
  the machine was in use.
- "Bounded by the stored cutover" is the search an instance repeats at every start and
  daily check once its cutover is stored: it reads only what lies before the cutover. In
  the fixture the first event is already tagged, so there is nothing before it. The
  steady state with a year of untagged records before the stored cutover, which reads
  every one of them, was measured on 2026-11-15 (section of that date below).
- The variant is not the shipped statement. It asks for a key that no payload holds, so
  nothing matches: that is the search on an instance whose whole year lies before the
  cutover, or that has no shape-tagged event at all. It costs what the full-range search
  costs.

## Decision

The slowest cold run over the full range took 6.49 seconds and 64 MiB. That is under the
23 seconds set for the start, under the 60 seconds set for the daily check, and under the
512 MiB set for memory. The search is adopted at service start and in the daily check, as
the spec describes; the fallback is not used.

## What this does not show

- Production data. The volume, the payload sizes and the share of shape operations are
  the fixture's. No production row was read.
- More history. The time grows with the rows before the cutover; by these figures a
  start would reach the liveness window of about 70 seconds at roughly ten times this
  volume on the same two cores. That is arithmetic, not a measurement. Since the limits
  became settings of the statement, what counts is the 23 s limit, not the liveness
  window: see "What this does not show" of the 2026-11-15 section below.
- A slow disk. A cold run read 1.77 GiB in about a second more than a warm run took, so
  this disk was fast, and what the host caches under the virtual machine's disk was not
  controlled. On storage that reads far slower the cold search takes longer in
  proportion.
- A table with unmerged parts, as a live installation has. The fixture was merged to one
  part per month.
- The search under other load on the same ClickHouse, such as a refresh or page requests
  running at the same moment.
- The service's own start. The statement ran through `clickhouse-client`, not through the
  service; the service start that runs it is covered by the seam 1 tests on small data
  (`2026-11-14-cutover-at-start.md`).

Later (2026-11-14, after the independent review): the shipped statement now reads the
events in timestamp order and stops at the first match, and runs with these limits as
ClickHouse settings. The figures above are those of the earlier aggregate. See
[`2026-11-14-refresh-lease-two-minutes.md`](2026-11-14-refresh-lease-two-minutes.md),
"Independent review". The new statement was measured at this scale on 2026-11-15 (below):
when it finds nothing it costs about what the aggregate costs, 2.6 % more time and more
memory, and it stops early when it finds a match early.

## 2026-11-15: the in-order statement, measured

The review of tickets 23 and 24 (finding 2) asked for the statement that now ships, which
reads the events in timestamp order and stops at the first match, to be measured at this
scale before it is relied on, because once a cutover is stored every search finds nothing
and reads every record before it.

Files: [`2026-11-14-cutover-search-cost/2026-11-15/`](2026-11-14-cutover-search-cost/2026-11-15/)
(`measure.sh` is the procedure; `in_order.sql` and `aggregate.sql` are the two statements as
they ran; the other files are its output).

### What decides, written before the figures were read

The limits are the ones above, now settings of the statement: 23 s at start, 60 s in the
daily check, 512 MiB in both.

- A statement fits a state at start (or in the daily check) when all its runs there under
  the start's (or the daily check's) limits complete and none is stopped, and its peak
  memory is at most 512 MiB. The deciding figure is the slowest cold run under the limits;
  the runs with no limit show how long it would take.
- The in-order statement is worse than the aggregate in a state when, with no limit, its
  fastest cold run is slower than the aggregate's slowest cold run, or its fastest warm run
  slower than the aggregate's slowest warm run. A smaller difference is not told apart from
  the machine: the first measurement's cold runs of one statement spread from 4.4 to 6.5 s.
- The in-order statement stays when it is not worse in the steady state and fits in every
  state where the aggregate fits. Otherwise each state gets the cheaper form. Where neither
  fits, the figures are recorded and nothing else is designed.

### The first pass, and why a second one follows

Read after the first pass (`summary.txt`): in the steady state with no limit, the in-order
statement's cold runs took 4.21 to 4.29 s and the aggregate's 4.00 to 4.16 s. Read
literally, the rule above calls the in-order statement worse there, by 0.05 s. The rule
cannot tell that apart from the machine: the same aggregate in the same state took 4.18 to
4.50 s cold under the start limits, which it never came near, so it was "worse" than
itself by the same rule, and in the early state its warm runs took 3.50 to 3.58 s in one
block and 4.06 to 4.15 s in the next. Three runs a cell, the aggregate always run first,
and a host load average of 5 to 8 from other jobs (see below) make blocks drift by up to
ten times the gap. That is a fault of the rule's design, recorded here, not a result.

So the steady state, the one that decides, is measured once more, with a rule committed
before that run:

- Steady state only (the stored cutover 2026-11-13 06:00, every record before it untagged),
  no limit, ten cold and ten warm runs of each statement, the two interleaved and their
  order alternating from one pair to the next, so drift falls on both alike
  (`measure.sh replicate`).
- The in-order statement is worse in the steady state when its median cold run, or its
  median warm run, is more than 5 % slower than the aggregate's.
- If it is worse, the shipped search uses the aggregate when a cutover is stored and the
  in-order read when none is, test first. If not, the in-order statement stays. This run
  decides; there is no third.

### How it ran

- A new container made as the first measurement's was: `cvat/clickhouse:23.12.2-debian-11-r0`
  (23.12.2.59), `--cpus 2 --memory 10g`, `max_threads` auto(2), no published port, loaded
  with `../run.sh up` (`base_n` 325, 36,326,651 rows, 13 parts, 2.44 GiB on disk). It was
  removed afterwards.
- The machine was not otherwise idle. The host has 32 threads; while the runs went on,
  other agents' jobs (a test stack and a service suite) were running and its user was
  using it. The host load average was 4.4 to 7.8 (`setup.txt`,
  `replicate-summary.txt`). The container could use at most two CPUs of it. Rows read
  count whole granules, so they can exceed the rows before the bound.
- Each statement ran through `clickhouse-client` with the service's setting
  (`query_plan_execute_functions_after_sorting = 0`) and, for "start" and "daily", with the
  limits the service sends: `max_execution_time` 23 or 60, `timeout_overflow_mode` throw,
  `max_memory_usage` 512 MiB. Cold runs as in the first measurement; every cold run read
  the table from disk (1.62 to 1.77 GiB, `report.txt`), except the in-order runs of the
  early state, which read 75 MiB because they stop.
- `EXPLAIN` (`explain.txt`) shows the in-order statement reading the table `InOrder`, with
  the whole condition as a prewhere filter and `LIMIT 1` pushed down to the sort.

How each state was made on the fixture:

| State | Made by | Stored cutover | Search bound | Rows before the bound | Tagged among them |
| --- | --- | --- | --- | --- | --- |
| early | the fixture as loaded | none | after the last event | 36,326,651 | 11,566,490, the first at 2025-11-14 06:00:22 |
| late | `shape_type` renamed to a key of the same length in every payload before 2026-11-13 (one mutation) | none | after the last event | 36,326,651 | 43,398, the first at 2026-11-13 06:00:11 |
| steady | as late, with 2026-11-13 06:00 stored | 2026-11-13 06:00 | the stored cutover | 36,191,234 | 0 |
| none | the key renamed in the remaining payloads too | none | after the last event | 36,326,651 | 0 |

In `setup.txt` the late state's "stored cutover" line is what the early state's last run
left, read before the next run emptied the table, and a first tagged record of
`1970-01-01` means there is none.

### Figures

Seconds, slowest of three runs. Within a cell the three runs were at most 0.34 s apart,
except the late aggregate's warm runs with no limit (fastest in brackets). Peak memory is
the largest of the cell. No run of either statement was stopped, under any
limit (`stops.txt` is empty).

| State | Statement | Start limits, cold | Daily limits, cold | No limit, cold | No limit, warm | Peak memory | Rows read |
| --- | --- | --- | --- | --- | --- | --- | --- |
| early | aggregate | 4.78 | 4.94 | 4.93 | 3.66 | 64 MiB | 36,326,651 |
| early | in order | 0.27 | 0.27 | 0.28 | 0.04 | 54 MiB | 114,688 |
| late | aggregate | 4.67 | 4.09 | 4.30 | 4.14 (3.34) | 40 MiB | 36,326,651 |
| late | in order | 4.26 | 4.48 | 4.25 | 3.16 | 55 MiB | 36,193,328 |
| steady | aggregate | 4.50 | 4.27 | 4.16 | 3.11 | 17 MiB | 36,193,328 |
| steady | in order | 4.26 | 4.26 | 4.29 | 3.12 | 51 MiB | 36,193,328 |
| none | aggregate | 4.12 | 4.09 | 4.04 | 3.16 | 17 MiB | 36,326,651 |
| none | in order | 4.16 | 4.12 | 4.28 | 3.07 | 51 MiB | 36,326,651 |

The steady state again, interleaved, ten runs each, no limit (`replicate-summary.txt`):

| Statement | Cold median | Cold range | Warm median | Warm range | Peak memory |
| --- | --- | --- | --- | --- | --- |
| aggregate | 4.049 s | 3.93–4.40 s | 2.950 s | 2.82–3.19 s | 17 MiB |
| in order | 4.155 s | 4.06–4.36 s | 3.027 s | 2.84–3.54 s | 51 MiB |

- With a tagged record early in the data, the in-order statement stops after 14 granules:
  0.27 s cold against 4.9 s for the aggregate.
- Wherever all or almost all records come before the first match, or there is none
  (late, steady, none), both read the same rows and take about the same time. Reading in
  order is slightly slower: in the first pass the gap is within the machine's spread, and
  in the replication the in-order medians are 2.6 % above the aggregate's, cold and warm,
  about 0.1 s.
- The in-order statement holds about 50 MiB where the aggregate holds 17 MiB with nothing
  to match. The rule does not count it; both are a tenth of the 512 MiB limit or less.

### Decision

The in-order statement stays; the code does not change. The figure that decided it: in the
steady state its median cold run was 4.155 s against the aggregate's 4.049 s, 2.6 %
slower, under the 5 % committed for the replication (warm: 3.027 s against 2.950 s, also
2.6 %). It fits in every state: its slowest cold run under the start limits was 4.26 s
(23 s allowed), under the daily check's 4.48 s (60 s allowed), and its peak memory 55 MiB
(512 MiB allowed). The aggregate fits everywhere too, so the in-order statement fits
wherever the aggregate does.

### What this does not show

- A stopped search. No run reached a limit, so ClickHouse stopping this statement at 23 s
  or 60 s at scale, or earlier on its own estimate of the time left, was not observed
  here. The stop itself is shown on small data (`2026-11-14-refresh-review-limits/`).
- The headroom, by arithmetic only: at about 4.3 s cold for this history on two cores,
  the start's 23 s limit is reached at roughly five times this history before the
  cutover, and the daily check's 60 s at roughly fourteen times. Beyond that the search
  is stopped every time, so an earlier record that turns up later never moves the
  cutover on such an instance (the fork specification says what follows).
- The other image (`clickhouse/clickhouse-server:23.11-alpine`), a table with unmerged
  parts, production data, other queries running on the same ClickHouse, a slower disk,
  and the service's own client path: as for the first measurement above.
- The refresh's own search (`find_cutover`), which runs without a limit and is bounded
  by the earliest stored tagged hour, was not measured separately.
