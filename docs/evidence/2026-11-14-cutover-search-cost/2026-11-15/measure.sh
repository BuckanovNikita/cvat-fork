#!/usr/bin/env bash
# The second measurement (2026-11-15): the cutover search as it ships now, which reads the events in timestamp
# order and stops at the first match, against the aggregate it replaced, in the states that matter.
#
#   NAME=<container> measure.sh smoke   one run of each statement, nothing kept
#   NAME=<container> measure.sh all     every state; writes setup.txt, explain.txt, runs.txt, report.txt here
#   NAME=<container> measure.sh replicate   after `all`: the steady state again, the statements interleaved;
#                                           writes replicate-runs.txt, replicate-summary.txt
#
# The container is the first measurement's (../run.sh up: 2 CPUs, 10 GiB, the fixture loaded at full scale).
# `all` changes the data on the way (two mutations of the payload column), so it runs once per load.
#
# States, in the order they are made:
#   early   the fixture as loaded: the first event is tagged; no cutover stored; the search reads to the end
#   late    every payload before $LATE has its `shape_type` key renamed (same length), so the first tagged
#           record is on the last day; no cutover stored
#   steady  as late, with the hour of that first tagged record stored as the cutover: the search reads every
#           record before it and finds nothing, as at every start and daily check of such an instance
#   none    the remaining payloads renamed too: no tagged record at all; no cutover stored
# Statements: `in-order` is team-analytics/service/sql/control/cutover_find.sql as it ships; `aggregate` is the
# same file before c3edcd58 (min() over every row before the bound). Each runs under the shipped limits of the
# start (23 s), of the daily check (60 s), both with 512 MiB, and with no limit; three times cold, three warm.
set -euo pipefail

D="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$D/../../../.." && pwd)"
NAME="${NAME:?set NAME to the container name}"
UNTIL='2026-11-14 00:00:00.000'      # after the last event of the fixture
LATE='2026-11-13 00:00:00.000'       # before this, the late state's payloads carry no `shape_type` key
SERVICE_SETTINGS=(--query_plan_execute_functions_after_sorting=0)  # team_analytics/sql.py SETTINGS
MEMORY=$((512 * 1024 * 1024))                                      # team_analytics/config.py
declare -A LIMITS=(
    [start]="--max_execution_time=23 --timeout_overflow_mode=throw --max_memory_usage=$MEMORY"
    [daily]="--max_execution_time=60 --timeout_overflow_mode=throw --max_memory_usage=$MEMORY"
    [none]=""
)
RUN_ID="${RUN_ID:-$(date -u +%H%M%S)}"
MATCH="source = 'client' AND user_id IS NOT NULL AND job_id IS NOT NULL
    AND (scope IN ('draw:object', 'paste:object', 'propagate:object', 'drag:object', 'resize:object', 'delete:object')
        OR (scope = 'debug:info' AND obj_name = 'team_analytics:class_change'))
    AND JSONHas(ifNull(payload, ''), 'shape_type')"

ch() { docker exec -i "$NAME" clickhouse-client --user user --password user --receive_timeout=3600 "$@"; }
say() { echo "[$(date -u +%H:%M:%S)] $*"; }
note() { say "$*" | tee -a "$D/runs.txt"; }
file_cache() { docker exec "$NAME" sh -c 'grep -E "^file " /sys/fs/cgroup/memory.stat' | cut -d" " -f2; }

substitute() { sed -e 's/\$events_db/default/g' -e 's/\$totals_db/ta_totals/g'; }
statements() {
    substitute < "$REPO/team-analytics/service/sql/control/cutover_find.sql" > "$D/in_order.sql"
    git -C "$REPO" show c3edcd58^:team-analytics/service/sql/control/cutover_find.sql | substitute > "$D/aggregate.sql"
    ch -q "CREATE DATABASE IF NOT EXISTS ta_totals"
    substitute < "$REPO/team-analytics/service/sql/schema/070_cutover.sql" | ch -n
}

evict() {  # as ../run.sh: the events table's files leave this container's page cache, the server's caches go
    ch -q "SYSTEM DROP MARK CACHE"
    ch -q "SYSTEM DROP UNCOMPRESSED CACHE"
    ch -q "SELECT path FROM system.parts WHERE active AND database = 'default' AND table = 'events'" \
        | docker exec -i "$NAME" sh -c 'while read -r part; do
              sync -f "$part"
              find "$part" -type f -exec dd if={} iflag=nocache count=0 status=none \;
          done'
}

stored() { ch -q "SELECT groupArray(toString(at)) FROM ta_totals.cutover"; }

run() {  # run <state> <statement> <limits> <cold|warm> <n> <until> [keep]: one run, logged under its label
    local label="$1|$2|$3|$4|$5" out
    [ "${7:-}" = keep ] || ch -q "TRUNCATE TABLE ta_totals.cutover"
    if [ "$4" = cold ]; then
        local before; before="$(file_cache)"; evict
        note "$label: page cache $before -> $(file_cache) bytes"
    fi
    # shellcheck disable=SC2086  # the limits are separate flags
    if out="$(ch "${SERVICE_SETTINGS[@]}" ${LIMITS[$3]} --log_comment="tcm|$RUN_ID|$label" \
                 --param_until="$6" --time < "$D/$2.sql" 2>&1)"; then
        note "$label: ${out}s, stored $(stored)"
    else
        note "$label: STOPPED: $(echo "$out" | grep -m1 -oE 'Code: [0-9]+\. DB::Exception: [^(]{0,160}')"
    fi
}

cell() {  # cell <state> <until> [keep]: both statements, every limit, three cold and three warm runs
    local statement limits n
    for statement in aggregate in_order; do
        for limits in start daily none; do
            for n in 1 2 3; do run "$1" "$statement" "$limits" cold "$n" "$2" "${3:-}"; done
            for n in 1 2 3; do run "$1" "$statement" "$limits" warm "$n" "$2" "${3:-}"; done
        done
    done
}

describe() {  # describe <state> <until>: what the data holds for this state
    {
        echo "state $1, until $2:"
        echo "  rows before until: $(ch -q "SELECT count() FROM events WHERE timestamp < '$2'")"
        echo "  tagged rows before until: $(ch -q "SELECT count() FROM events WHERE timestamp < '$2' AND $MATCH")"
        echo "  first tagged record before until: $(ch -q "SELECT ifNull(toString(min(timestamp)), 'none') FROM events WHERE timestamp < '$2' AND $MATCH")"
        echo "  stored cutover: $(stored)"
        echo "  parts (active), on disk, uncompressed: $(ch -q "SELECT count(), formatReadableSize(sum(bytes_on_disk)), formatReadableSize(sum(data_uncompressed_bytes)) FROM system.parts WHERE active AND database = 'default' AND table = 'events'" | tr '\t' ' ')"
        echo "  host load average: $(cut -d' ' -f1-3 /proc/loadavg)"
    } | tee -a "$D/setup.txt"
}

rename_key() {  # rename_key <bound>: payloads of records before <bound> lose the `shape_type` key (same length)
    say "renaming the key before $1"
    ch -q "ALTER TABLE events UPDATE payload = replaceOne(payload, '\"shape_type\"', '\"shape_tyqe\"')
           WHERE timestamp < '$1' AND position(ifNull(payload, ''), '\"shape_type\"') > 0
           SETTINGS mutations_sync = 2"
    say "renamed; mutations not done: $(ch -q "SELECT count() FROM system.mutations WHERE table = 'events' AND NOT is_done")"
}

explain() {  # explain <statement>: the plan and pipeline of its SELECT, with the service's setting
    local select; select="$(sed '/^INSERT INTO/d' "$D/$1.sql")"
    {
        echo "== $1: EXPLAIN PLAN actions = 1"
        ch "${SERVICE_SETTINGS[@]}" --param_until="$UNTIL" -q "EXPLAIN PLAN actions = 1 $select"
        echo "== $1: EXPLAIN PIPELINE"
        ch "${SERVICE_SETTINGS[@]}" --param_until="$UNTIL" -q "EXPLAIN PIPELINE $select"
    } >> "$D/explain.txt"
}

report() {
    ch -q "SYSTEM FLUSH LOGS"
    ch --format PrettyCompactNoEscapesMonoBlock -q "
        SELECT splitByChar('|', log_comment)[3] AS state,
               splitByChar('|', log_comment)[4] AS statement,
               splitByChar('|', log_comment)[5] AS limits,
               concat(splitByChar('|', log_comment)[6], ' ', splitByChar('|', log_comment)[7]) AS run,
               if(type = 'QueryFinish', 'done', concat('stopped, code ', toString(exception_code))) AS outcome,
               round(query_duration_ms / 1000, 2) AS seconds,
               formatReadableSize(memory_usage) AS peak_memory,
               read_rows,
               formatReadableSize(read_bytes) AS read_uncompressed,
               formatReadableSize(ProfileEvents['OSReadBytes']) AS read_from_disk,
               round(ProfileEvents['OSCPUVirtualTimeMicroseconds'] / 1e6, 2) AS cpu_seconds,
               written_rows AS stored_rows
        FROM system.query_log
        WHERE log_comment LIKE 'tcm|$RUN_ID|%' AND type != 'QueryStart'
        ORDER BY event_time_microseconds" > "$D/report.txt"
    ch --format PrettyCompactNoEscapesMonoBlock -q "
        SELECT splitByChar('|', log_comment)[3] AS state,
               splitByChar('|', log_comment)[4] AS statement,
               splitByChar('|', log_comment)[5] AS limits,
               splitByChar('|', log_comment)[6] AS cache,
               count() AS runs,
               countIf(type = 'QueryFinish') AS done,
               min(round(query_duration_ms / 1000, 2)) AS fastest_s,
               max(round(query_duration_ms / 1000, 2)) AS slowest_s,
               formatReadableSize(max(memory_usage)) AS peak_memory,
               max(read_rows) AS read_rows
        FROM system.query_log
        WHERE log_comment LIKE 'tcm|$RUN_ID|%' AND type != 'QueryStart'
        GROUP BY state, statement, limits, cache
        ORDER BY min(event_time_microseconds)" > "$D/summary.txt"
    ch -q "SELECT DISTINCT exception_code, substring(exception, 1, 200) FROM system.query_log
           WHERE log_comment LIKE 'tcm|$RUN_ID|%' AND type IN ('ExceptionBeforeStart', 'ExceptionWhileProcessing')" \
        > "$D/stops.txt"
}

smoke() {
    local out; out="$(mktemp -d)"; D_KEEP="$D"; D="$out"
    statements
    run smoke aggregate start warm 1 "$UNTIL"
    run smoke in_order start warm 1 "$UNTIL"
    run smoke in_order none cold 1 "$UNTIL"
    explain in_order
    head -40 "$D/explain.txt"
    cat "$D/runs.txt"
    rm -rf "$out"; D="$D_KEEP"
}

all() {
    : > "$D/setup.txt"; : > "$D/runs.txt"; : > "$D/explain.txt"
    statements
    {
        echo "image: $(docker inspect --format '{{.Config.Image}}' "$NAME")"
        echo "server: $(ch -q "SELECT version()")"
        echo "limits of the container: --cpus 2 --memory 10g; max_threads = $(ch --format TSVRaw -q "SELECT value FROM system.settings WHERE name = 'max_threads'")"
        echo "base_n: $(docker exec "$NAME" cat /tmp/base_n)"
        echo "events: $(ch -q "SELECT count(), min(timestamp), max(timestamp) FROM events" | tr '\t' ' ')"
        echo "host CPUs: $(nproc)"
    } | tee -a "$D/setup.txt"
    explain in_order
    explain aggregate

    describe early "$UNTIL"
    cell early "$UNTIL"

    rename_key "$LATE"
    describe late "$UNTIL"
    cell late "$UNTIL"

    local first
    first="$(ch -q "SELECT toString(toStartOfHour(toDateTime(min(timestamp), 'Etc/UTC'))) FROM events WHERE $MATCH")"
    ch -q "TRUNCATE TABLE ta_totals.cutover"
    ch -q "INSERT INTO ta_totals.cutover (at) VALUES ('$first')"
    describe steady "$first.000"
    cell steady "$first.000" keep

    rename_key "$UNTIL"
    ch -q "TRUNCATE TABLE ta_totals.cutover"
    describe none "$UNTIL"
    cell none "$UNTIL"

    echo "host load average after the runs: $(cut -d' ' -f1-3 /proc/loadavg)" | tee -a "$D/setup.txt"
    report
    cat "$D/summary.txt" "$D/stops.txt"
}

replicate() {  # the steady state again, after `all`: no limit, the statements interleaved in alternating order
    local runs="$D/replicate-runs.txt" n first second cache
    RUN_ID="r$RUN_ID"
    note() { say "$*" | tee -a "$runs"; }
    : > "$runs"
    ch -q "TRUNCATE TABLE ta_totals.cutover"
    ch -q "INSERT INTO ta_totals.cutover (at) VALUES ('$STEADY')"
    for cache in cold warm; do
        for n in $(seq 10); do
            if [ $((n % 2)) = 1 ]; then first=aggregate second=in_order; else first=in_order second=aggregate; fi
            run steady "$first" none "$cache" "$n" "$STEADY.000" keep
            run steady "$second" none "$cache" "$n" "$STEADY.000" keep
        done
    done
    ch -q "SYSTEM FLUSH LOGS"
    ch --format PrettyCompactNoEscapesMonoBlock -q "
        SELECT splitByChar('|', log_comment)[4] AS statement,
               splitByChar('|', log_comment)[6] AS cache,
               count() AS runs, countIf(type = 'QueryFinish') AS done,
               round(quantileExact(0.5)(query_duration_ms) / 1000, 3) AS median_s,
               round(min(query_duration_ms) / 1000, 2) AS fastest_s,
               round(max(query_duration_ms) / 1000, 2) AS slowest_s,
               formatReadableSize(max(memory_usage)) AS peak_memory,
               min(read_rows) AS read_rows_min, max(read_rows) AS read_rows_max,
               formatReadableSize(min(ProfileEvents['OSReadBytes'])) AS disk_read_min
        FROM system.query_log
        WHERE log_comment LIKE 'tcm|$RUN_ID|%' AND type != 'QueryStart'
        GROUP BY statement, cache ORDER BY cache, statement" | tee "$D/replicate-summary.txt"
    echo "host load average after the runs: $(cut -d' ' -f1-3 /proc/loadavg)" | tee -a "$D/replicate-summary.txt"
}
STEADY='2026-11-13 06:00:00'  # the steady state's stored cutover, as `all` found it

case "${1:-}" in
    smoke) smoke ;;
    all) all ;;
    replicate) replicate ;;
    *) echo "usage: NAME=<container> $0 smoke|all|replicate" >&2; exit 2 ;;
esac
