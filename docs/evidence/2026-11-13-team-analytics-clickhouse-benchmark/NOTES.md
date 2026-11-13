# ClickHouse analytics benchmark notes (2026-11-13)

Throwaway container `ta-chbench-f0f6`, image `clickhouse/clickhouse-server:23.11-alpine`
(server 23.11.5.29), `--cpus=6 --memory=10g`. The server detected 6 CPUs (`max_threads = auto(6)`)
and set `max_server_memory_usage` to 9.00 GiB. All timings are warm (page cache); cold-cache
timings were not measured.

## Files

| File | Purpose |
|---|---|
| `01_schema.sql` | production `events` schema + `events_fx` fixture table |
| `02_gen_sessions.sql`, `03_gen_events.sql`, `load.sh` | synthetic data generator (month by month) |
| `04_fixture.sql` | 30 hand-made rows with known answers |
| `05_json_probe.sql/.out` | JSON function behaviour on `json.dumps`-style text |
| `06_q4_bruteforce_check.sql/.out` | Q4 window formulation vs brute-force join |
| `q/q1a..q6b*.sql` | benchmark queries (params `tbl`, `days`); `q3_template.sql` + `mk_q3.py` generate Q3 variants |
| `07_rollup_ddl.sql`, `07_rollup_fill.sql`, `q/r1..r4*.sql` | hourly rollup, fill/refresh, reads |
| `08_rollup_verify.sql/.out` | rollup vs direct diff |
| `09_boundary_error.sql/.out` | hour-boundary error measurements |
| `10_refreshable_mv.sh/.out` | refreshable materialized view test |
| `11_concurrency.sh/.out` | concurrent 365-day queries |
| `run.sh`, `ch.sh` | runner / wrapper; `bench_report.txt` = timings from `system.query_log` |

## Data

36,326,651 rows, 2025-11-14 .. 2026-11-13, 13 monthly parts after `OPTIMIZE FINAL`,
2.44 GiB on disk, 10.07 GiB uncompressed (`payload` alone: 1.26 GiB / 4.94 GiB).
Weekdays ~136k rows/day, weekends ~7k. 100 users, 40 projects, 796 tasks, 2383 jobs.
About 8 sessions per user per working day (5-minute rule). No per-user timestamp ties.
Payload text uses `": "` / `", "` separators, as Python's `json.dumps` writes it; the stock
server re-serialises client payloads that way (`cvat/apps/events/serializers.py`).

## Fixture expectations (all reproduced by the queries)

- Q1a: user 1 / 2026-11-10 = 110000 ms; user 2 / 2026-11-11 = 20000 ms.
- Q2: user 1 = 2 sessions, 295 s; user 2 = 1 session, 20.5 s.
- Q3 (rectangle filter), user 1: creation 38 s / 4, alignment 57 s / 8, class change 5 s / 1,
  deletion 10 s / 1, other 45 s / 7. Without filter alignment is 67 s / 9.
- Q4, user 1: creation 75 s / 10, alignment 45 s / 6, class change 5 / 1, deletion 10 / 1, other 20 s / 3.
- Q5, user 1: 9 drag/resize events = 5 alignments.
- Q6: user 1: A = 3, B = 5.

## Findings

1. `simpleJSONExtractString` returns '' on text with a space after the colon; `JSONExtractString`
   works. Q3 with `simpleJSON*` silently returns only the "other" rows.
2. With default settings ClickHouse 23.11 evaluates the JSON extraction *after* the window sort
   (`query_plan_execute_functions_after_sorting = 1`), so the raw `payload` column is carried
   through the sort. Every payload-touching window query then fails at 365 days with
   "Memory limit (total) exceeded ... maximum: 9.00 GiB". With
   `query_plan_execute_functions_after_sorting = 0` the same queries run in 1.5-2.3 s with
   about 1-1.6 GiB. Results are identical with either value (checked by hash).
3. A suffix frame (`1 FOLLOWING .. UNBOUNDED FOLLOWING`) is avoided in Q4 by sorting descending and
   using a prefix frame.
4. Rollup with a 300 s look-back equals the direct queries exactly (0 mismatching groups over the
   year, also when the refresh boundary is placed mid-workday). Without look-back, a refresh
   boundary at 10:00 gave +7 sessions and -953 s of session time (7 users working across the
   boundary) and -15.8 s of operation time. Computing every hour independently over 30 days:
   20,960 sessions instead of 16,173 (+30%), session time -1.6%, operation time -0.26%.
5. Concurrency under the 6-CPU cap: Q3-with-JSON at 365 days took 1.9 s alone, 4.5 s with 2 copies,
   15.7 s with 4 copies (repeat: 15.4 s); 8 copies of Q2a took 8.7 s each (0.44 s alone).
   During the repeat the container's cgroup counters showed 163 of 177 CPU periods throttled and
   about 105 CPU-seconds used for 5 queries, so the CPU quota was the limiter. Four copies with
   `max_threads=1` each took 9.4 s each. (The "max_threads=2" label in `11_concurrency.out` is a
   typo; the run used `max_threads=1`.)
6. Refreshable materialized views: not available. `CREATE MATERIALIZED VIEW ... REFRESH EVERY`
   is a syntax error at `REFRESH`; `SET allow_experimental_refreshable_materialized_view = 1`
   fails with UNKNOWN_SETTING; `SYSTEM REFRESH VIEW` is a syntax error.

Timings: see `bench_report.txt` (`[fas0]` = run with `query_plan_execute_functions_after_sorting=0`).
