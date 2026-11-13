#!/usr/bin/env bash
# Benchmark runner.
#   run.sh fx  <name>            run q/<name>.sql against the fixture table and print the result
#   run.sh bench <name> [days..] run q/<name>.sql against events for each range, twice, FORMAT Null
#   run.sh report [like]         print timings from system.query_log (second run of each)
# Env for bench: CH_EXTRA = extra clickhouse-client args (e.g. a setting), TAG = suffix added to the
# query name in the log, so runs with different settings are reported separately.
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
C=ta-chbench-f0f6
mode="$1"; shift
case "$mode" in
  fx)
    name="$1"
    docker exec -i "$C" clickhouse-client --max_threads=6 --param_tbl=events_fx --param_days=7 \
      --format PrettyCompactMonoBlock < "$D/q/$name.sql"
    ;;
  bench)
    name="$1"; shift
    days_list=("$@"); [ ${#days_list[@]} -eq 0 ] && days_list=(7 30 365)
    for d in "${days_list[@]}"; do
      for r in 1 2; do
        if out=$(docker exec -i "$C" clickhouse-client --max_threads=6 --param_tbl=events --param_days="$d" \
             --log_comment="bench|$name${TAG:+ [$TAG]}|$d|$r" ${CH_EXTRA:-} --format Null --time < "$D/q/$name.sql" 2>&1); then
          echo "$name${TAG:+ [$TAG]} days=$d run=$r: ${out}s"
        else
          echo "$name${TAG:+ [$TAG]} days=$d run=$r: FAILED: $(echo "$out" | head -c 300)"
        fi
      done
    done
    ;;
  report)
    like="${1:-%}"
    docker exec "$C" clickhouse-client -q "SYSTEM FLUSH LOGS"
    docker exec "$C" clickhouse-client --format PrettyCompactMonoBlock -q "
      SELECT splitByChar('|', log_comment)[2] AS query,
             toUInt32(splitByChar('|', log_comment)[3]) AS days,
             argMax(type, event_time_microseconds) AS outcome,
             round(argMax(query_duration_ms, event_time_microseconds) / 1000, 2) AS sec_run2,
             round(argMin(query_duration_ms, event_time_microseconds) / 1000, 2) AS sec_run1,
             formatReadableSize(argMax(memory_usage, event_time_microseconds)) AS peak_mem_run2,
             argMax(read_rows, event_time_microseconds) AS read_rows,
             formatReadableSize(argMax(read_bytes, event_time_microseconds)) AS read_bytes,
             argMax(result_rows, event_time_microseconds) AS result_rows
      FROM system.query_log
      WHERE log_comment LIKE 'bench|%' AND type IN ('QueryFinish', 'ExceptionWhileProcessing')
        AND splitByChar('|', log_comment)[2] LIKE '$like'
      GROUP BY query, days
      ORDER BY query, days"
    ;;
esac
