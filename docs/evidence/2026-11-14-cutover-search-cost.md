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
  the fixture the first event is already tagged, so there is nothing before it.
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
  volume on the same two cores. That is arithmetic, not a measurement.
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
