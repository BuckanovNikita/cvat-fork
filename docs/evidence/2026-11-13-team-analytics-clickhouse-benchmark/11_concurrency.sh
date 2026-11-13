#!/usr/bin/env bash
# N concurrent copies of one 365-day query (default: Q3 with JSON extraction), to see what
# several simultaneous page loads do under the 6 CPU / 10 GiB caps.
# usage: 11_concurrency.sh <n> [query-name]
D="$(cd "$(dirname "$0")" && pwd)"
C=ta-chbench-f0f6
n="${1:-4}"; name="${2:-q3c_json}"
s=$(date +%s.%N)
for i in $(seq 1 "$n"); do
  (
    if out=$(docker exec -i "$C" clickhouse-client --max_threads=6 --param_tbl=events --param_days=365 \
         --query_plan_execute_functions_after_sorting=0 \
         --log_comment="conc|$name|$n|$i" --format Null --time < "$D/q/$name.sql" 2>&1); then
      echo "  copy $i: ${out}s"
    else
      echo "  copy $i: FAILED: $(echo "$out" | grep -o 'Memory limit[^.]*' | head -1)"
    fi
  ) &
done
wait
e=$(date +%s.%N)
echo "$n x $name (365 days) wall: $(echo "$e - $s" | bc) s"
