#!/usr/bin/env bash
# Q8: are refreshable materialized views available in this server version?
# Every statement is run separately so each error text is captured.
C=ta-chbench-f0f6
run() { echo "--- $*"; docker exec "$C" clickhouse-client "$@" 2>&1 | head -c 900; echo; }

run -q "SELECT version()"
run -q "SELECT name, value, description FROM system.settings WHERE name ILIKE '%refresh%' FORMAT Vertical"
run -q "SELECT name FROM system.tables WHERE database = 'system' AND name ILIKE '%refresh%'"
run -q "CREATE TABLE IF NOT EXISTS rmv_target (user_id UInt64, working_ms UInt64) ENGINE = MergeTree ORDER BY user_id"
run -q "CREATE MATERIALIZED VIEW rmv_test REFRESH EVERY 1 HOUR TO rmv_target AS SELECT ifNull(user_id, 0) AS user_id, sum(duration) AS working_ms FROM events WHERE scope = 'send:working_time' GROUP BY user_id"
run --allow_experimental_refreshable_materialized_view=1 -q "CREATE MATERIALIZED VIEW rmv_test REFRESH EVERY 1 HOUR TO rmv_target AS SELECT ifNull(user_id, 0) AS user_id, sum(duration) AS working_ms FROM events WHERE scope = 'send:working_time' GROUP BY user_id"
run -q "SET allow_experimental_refreshable_materialized_view = 1"
run -q "SYSTEM REFRESH VIEW rmv_test"
run -q "EXISTS TABLE rmv_test"
run -q "DROP TABLE IF EXISTS rmv_test"
run -q "DROP TABLE IF EXISTS rmv_target"
