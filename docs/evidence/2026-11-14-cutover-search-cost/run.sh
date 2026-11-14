#!/usr/bin/env bash
# Cost of the cutover's long-range search on data of the scale of the design measurements.
#
#   NAME=<container> run.sh up        start a throwaway ClickHouse, check the tools, load the fixture
#   NAME=<container> run.sh measure   run the search cold and warm; writes setup.txt, search.sql, report.txt
#   NAME=<container> run.sh down      remove the container
#
# The fixture is the benchmark's (../2026-11-13-team-analytics-clickhouse-benchmark): its schema and its
# generator, month by month. The statement measured is the service's own file
# (team-analytics/service/sql/control/cutover_find.sql), with the databases substituted as the service does.
# The container gets 2 CPUs and 10 GiB, publishes no port and is reached with `docker exec` only.
set -euo pipefail

D="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$D/../../.." && pwd)"
FIXTURE="$D/../2026-11-13-team-analytics-clickhouse-benchmark"
IMAGE="${IMAGE:-cvat/clickhouse:23.12.2-debian-11-r0}"
NAME="${NAME:?set NAME to the container name}"
TARGET_ROWS=36326651             # the design measurements' row count (the benchmark's NOTES.md)
UNTIL='2026-11-14 00:00:00.000'  # after the last event of the fixture: the search reads everything
SERVICE_SETTINGS=(--query_plan_execute_functions_after_sorting=0)  # team_analytics/sql.py SETTINGS
RUN_ID="${RUN_ID:-$(date -u +%H%M%S)}"  # tells this invocation's runs apart in the query log

ch() { docker exec -i "$NAME" clickhouse-client --user user --password user --receive_timeout=3600 "$@"; }
say() { echo "[$(date -u +%H:%M:%S)] $*"; }
# bytes of page cache charged to the container
file_cache() { docker exec "$NAME" sh -c 'grep -E "^file " /sys/fs/cgroup/memory.stat' | cut -d" " -f2; }

up() {
    docker run -d --name "$NAME" --cpus 2 --memory 10g \
        -e CLICKHOUSE_ADMIN_USER=user -e CLICKHOUSE_ADMIN_PASSWORD=user "$IMAGE" >/dev/null
    say "started $NAME from $IMAGE"
    # fail fast, before the long load: the client logs in, the query log is kept, dd can drop a file's
    # cache, the container's page cache can be read
    for _ in $(seq 90); do ch -q "SELECT 1" >/dev/null 2>&1 && break; sleep 1; done
    if ch -q "SELECT version()" \
        && ch --log_comment="t17|probe" -q "SELECT 1" >/dev/null \
        && ch -q "SYSTEM FLUSH LOGS" \
        && [ "$(ch -q "SELECT count() > 0 FROM system.query_log WHERE log_comment = 't17|probe'")" = 1 ] \
        && docker exec "$NAME" dd if=/etc/hostname iflag=nocache count=0 status=none \
        && file_cache >/dev/null; then
        say "checks passed"
    else
        say "a check failed; removing $NAME"
        docker rm -f "$NAME" >/dev/null
        exit 1
    fi

    ch -n < "$FIXTURE/01_schema.sql"
    # The generator's `base_n` was not recorded. The row count grows with it, so it is found by bisection
    # on the number of rows the generator would write (expected_rows.sql), without writing them.
    local lo=250 hi=400 mid rows
    while [ "$lo" -lt "$hi" ]; do
        mid=$(((lo + hi) / 2))
        ch -n --param_base_n="$mid" < "$FIXTURE/02_gen_sessions.sql"
        rows="$(ch < "$D/expected_rows.sql")"
        say "base_n=$mid would write $rows rows"
        if [ "$rows" -lt "$TARGET_ROWS" ]; then lo=$((mid + 1)); else hi=$mid; fi
    done
    ch -n --param_base_n="$lo" < "$FIXTURE/02_gen_sessions.sql"
    rows="$(ch < "$D/expected_rows.sql")"
    say "chosen base_n=$lo, $rows rows expected (the design measurements had $TARGET_ROWS)"
    echo "$lo" | docker exec -i "$NAME" sh -c 'cat > /tmp/base_n'

    local bounds=(2025-11-14 2025-12-01 2026-01-01 2026-02-01 2026-03-01 2026-04-01 2026-05-01 2026-06-01
                  2026-07-01 2026-08-01 2026-09-01 2026-10-01 2026-11-01 2026-11-14)
    local m
    for ((m = 0; m <= 12; m++)); do
        ch -n --param_d_from="${bounds[$m]}" --param_d_to="${bounds[$((m + 1))]}" < "$FIXTURE/03_gen_events.sql"
        say "loaded ${bounds[$m]} .. ${bounds[$((m + 1))]}"
    done
    ch -q "OPTIMIZE TABLE events FINAL"
    say "loaded and merged: $(ch -q "SELECT count() FROM events") rows"
}

evict() {
    # Cold run: the events table's files leave the page cache (this container's files only, by
    # POSIX_FADV_DONTNEED through dd), and the server forgets its marks.
    ch -q "SYSTEM DROP MARK CACHE"
    ch -q "SYSTEM DROP UNCOMPRESSED CACHE"
    ch -q "SELECT path FROM system.parts WHERE active AND database = 'default' AND table = 'events'" \
        | docker exec -i "$NAME" sh -c 'while read -r part; do
              sync -f "$part"
              find "$part" -type f -exec dd if={} iflag=nocache count=0 status=none \;
          done'
}

search() {  # search <label> <statement file> <until> [keep]: one run of the statement, logged under the label
    [ "${4:-}" = keep ] || ch -q "TRUNCATE TABLE ta_totals.cutover"
    local seconds
    if ! seconds="$(ch "${SERVICE_SETTINGS[@]}" --log_comment="t17|$RUN_ID|$1" --param_until="$3" --time < "$2" 2>&1)"; then
        note "$1: FAILED: $seconds"
        return 1
    fi
    note "$1: ${seconds}s, stored $(ch -q "SELECT groupArray(toString(at)) FROM ta_totals.cutover")"
}

note() { say "$*" | tee -a "$D/runs.txt"; }  # a progress line that is kept with the results

measure() {
    local statement="$D/search.sql" absent
    absent="$(mktemp)"
    # the service's file, with the databases substituted as team_analytics/sql.py does
    sed -e 's/\$events_db/default/g' -e 's/\$totals_db/ta_totals/g' \
        "$REPO/team-analytics/service/sql/control/cutover_find.sql" > "$statement"
    sed -e "s/'shape_type'/'shape_type_absent'/" "$statement" > "$absent"
    ch -q "CREATE DATABASE IF NOT EXISTS ta_totals"
    sed -e 's/\$totals_db/ta_totals/g' "$REPO/team-analytics/service/sql/schema/070_cutover.sql" | ch -n

    {
        echo "image: $IMAGE"
        echo "server: $(ch -q "SELECT version()")"
        echo "limits: --cpus 2 --memory 10g; max_threads = $(ch --format TSVRaw -q "SELECT value FROM system.settings WHERE name = 'max_threads'")"
        echo "base_n: $(docker exec "$NAME" cat /tmp/base_n)"
        echo "events: $(ch -q "SELECT count(), min(timestamp), max(timestamp) FROM events" | tr '\t' ' ')"
        echo "parts, on disk, uncompressed: $(ch -q "SELECT count(), formatReadableSize(sum(bytes_on_disk)), formatReadableSize(sum(data_uncompressed_bytes)) FROM system.parts WHERE active AND database = 'default' AND table = 'events'" | tr '\t' ' ')"
        echo "payload column, on disk, uncompressed: $(ch -q "SELECT formatReadableSize(sum(data_compressed_bytes)), formatReadableSize(sum(data_uncompressed_bytes)) FROM system.columns WHERE database = 'default' AND table = 'events' AND name = 'payload'" | tr '\t' ' ')"
        echo "rows the search matches: $(ch -q "SELECT count() FROM events WHERE source = 'client' AND user_id IS NOT NULL AND job_id IS NOT NULL AND scope IN ('draw:object', 'paste:object', 'propagate:object', 'drag:object', 'resize:object', 'delete:object') AND JSONHas(ifNull(payload, ''), 'shape_type')")"
        echo "host load average before the runs: $(cut -d' ' -f1-3 /proc/loadavg)"
    } | tee "$D/setup.txt"

    : > "$D/runs.txt"
    local run
    for run in 1 2 3; do
        note "page cache of the container before eviction: $(file_cache) bytes"
        evict
        note "page cache of the container after eviction: $(file_cache) bytes"
        search "full range, cold, run $run" "$statement" "$UNTIL"
    done
    for run in 1 2 3; do search "full range, warm, run $run" "$statement" "$UNTIL"; done
    # a cutover is stored now (the first hour of the fixture): the search an instance tagged from its first
    # event repeats at every start and daily check reads only what lies before it
    local stored
    stored="$(ch -q "SELECT toString(min(at)) FROM ta_totals.cutover")"
    search "bounded by the stored cutover, warm" "$statement" "$stored.000" keep
    # variant, not the shipped statement: the same search for a key no payload holds, so nothing matches,
    # as on an instance whose year is all legacy
    evict
    search "variant: key absent, cold" "$absent" "$UNTIL"
    search "variant: key absent, warm" "$absent" "$UNTIL"
    rm -f "$absent"
    echo "host load average after the runs: $(cut -d' ' -f1-3 /proc/loadavg)" | tee -a "$D/setup.txt"

    ch -q "SYSTEM FLUSH LOGS"
    ch --format PrettyCompactNoEscapesMonoBlock -q "
        SELECT splitByChar('|', log_comment)[3] AS run,
               round(query_duration_ms / 1000, 2) AS seconds,
               formatReadableSize(memory_usage) AS peak_memory,
               read_rows,
               formatReadableSize(read_bytes) AS read_uncompressed,
               formatReadableSize(ProfileEvents['OSReadBytes']) AS read_from_disk,
               round(ProfileEvents['OSCPUVirtualTimeMicroseconds'] / 1e6, 2) AS cpu_seconds,
               written_rows AS stored_rows
        FROM system.query_log
        WHERE log_comment LIKE 't17|$RUN_ID|%' AND type = 'QueryFinish'
        ORDER BY event_time_microseconds" | tee "$D/report.txt"
    ch -q "SELECT count() FROM system.query_log WHERE log_comment LIKE 't17|$RUN_ID|%'
               AND type IN ('ExceptionBeforeStart', 'ExceptionWhileProcessing')" \
        | sed 's/^/failed runs: /' | tee -a "$D/report.txt"
}

case "${1:-}" in
    up) up ;;
    measure) measure ;;
    down) docker rm -f "$NAME" >/dev/null && say "removed $NAME" ;;
    *) echo "usage: NAME=<container> $0 up|measure|down" >&2; exit 2 ;;
esac
