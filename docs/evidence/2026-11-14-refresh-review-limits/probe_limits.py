"""Fix-refresh probe: does ClickHouse stop an INSERT ... SELECT at max_execution_time, and does it keep
running one whose HTTP client gave up? Runs inside the cvat/server image against a throwaway ClickHouse.

A slow statement: a view whose rows sleep 0.5 s each (sleepEachRow), over a table of one row per part with
merges stopped, so that each block holds one row (ClickHouse refuses a sleep over 3 s per block)."""
import time
import uuid

import clickhouse_connect


def client(timeout=300):
    return clickhouse_connect.get_client(host="clickhouse", port=8123, username="user", password="user",
                                         autogenerate_session_id=False, send_receive_timeout=timeout)


for _ in range(240):
    try:
        c = client()
        c.command("SELECT 1")
        break
    except Exception:
        time.sleep(0.5)
print("server", c.command("SELECT version()"), flush=True)
c.command("CREATE DATABASE p")


def table(name, rows):
    c.command(f"CREATE TABLE p.{name} (timestamp DateTime64(3, 'Etc/UTC'), payload Nullable(String)) "
              "ENGINE = MergeTree ORDER BY timestamp")
    c.command(f"SYSTEM STOP MERGES p.{name}")
    for n in range(rows):
        c.command(f"INSERT INTO p.{name} VALUES (toDateTime64('2026-11-01 00:00:00', 3, 'Etc/UTC') + {n}, "
                  "'{\"shape_type\":\"rectangle\"}')")


table("real", 40)
c.command("CREATE TABLE p.out (at DateTime64(3, 'Etc/UTC')) ENGINE = MergeTree ORDER BY at")
c.command("CREATE VIEW p.slow AS SELECT * EXCEPT (payload), if(sleepEachRow(0.5) = 0, payload, payload) AS payload "
          "FROM p.real")
ONE_THREAD = {"max_threads": 1}  # 40 rows, 20 s
INSERT = "INSERT INTO p.out SELECT min(timestamp) FROM p.slow WHERE JSONHas(ifNull(payload, ''), 'shape_type') " \
         "HAVING count() > 0"


def running(marker):
    return c.query("SELECT query_id FROM system.processes WHERE query LIKE {m:String} "
                   "AND query NOT LIKE '%system.processes%'", parameters={"m": f"%{marker}%"}).result_rows


def case(name, statement, settings, timeout, select=False):
    marker = uuid.uuid4().hex[:8]
    text = f"{statement} /* {marker} */"
    t0 = time.monotonic()
    try:
        if select:
            client(timeout).query(text, settings=settings)
        else:
            client(timeout).command(text, settings=settings)
        outcome = "returned"
    except Exception as error:  # noqa: BLE001
        outcome = f"{type(error).__name__}: {str(error).splitlines()[0][:220]}"
    gave_up = time.monotonic() - t0
    still = []
    for _ in range(8):
        still.append(bool(running(marker)))
        time.sleep(1)
    c.command("SYSTEM FLUSH LOGS")
    log = c.query("SELECT type, round(query_duration_ms / 1000, 2), exception_code FROM system.query_log "
                  "WHERE query LIKE {m:String} AND query NOT LIKE '%query_log%' AND query NOT LIKE '%processes%' "
                  "AND type != 'QueryStart'", parameters={"m": f"%{marker}%"}).result_rows
    print(f"{name}: client {outcome!r} after {gave_up:.2f} s; still running at 1 s steps over the next 8 s: "
          f"{still}; query_log: {log}; rows in out: {c.command('SELECT count() FROM p.out')}", flush=True)
    c.command(f"KILL QUERY WHERE query LIKE '%{marker}%' AND query NOT LIKE '%KILL%' SYNC")
    c.command("TRUNCATE TABLE p.out")


case("A insert-select, max_execution_time 1", INSERT, {**ONE_THREAD, "max_execution_time": 1}, 300)
case("A2 insert-select, max_execution_time 0.5", INSERT, {**ONE_THREAD, "max_execution_time": 0.5}, 300)
case("B insert-select, no server limit, client timeout 2 s", INSERT, ONE_THREAD, 2)
case("C select, no server limit, client timeout 2 s", INSERT.split(" ", 4)[4].replace(" HAVING count() > 0", ""),
     ONE_THREAD, 2, select=True)
case("D insert-select, server limit 2, client timeout 7 (as the service: limit + 5)", INSERT,
     {**ONE_THREAD, "max_execution_time": 2, "timeout_overflow_mode": "throw"}, 7)
case("F insert-select, no server limit, client timeout 12 s", INSERT, ONE_THREAD, 12)
case("E insert-select, max_memory_usage 1 MiB, server limit 30", INSERT,
     {**ONE_THREAD, "max_execution_time": 30, "max_memory_usage": 1024 * 1024}, 300)

# the fixture of the service test: eight rows, one per part, no setting from the statement but its limit
table("pay", 8)
c.command("CREATE VIEW p.pay_slow AS SELECT * EXCEPT (payload), if(sleepEachRow(0.5) = 0, payload, payload) "
          "AS payload FROM p.pay")
FIXTURE = INSERT.replace("p.slow", "p.pay_slow")
case("G fixture, max_execution_time 1", FIXTURE, {"max_execution_time": 1}, 300)
case("G2 fixture, no limit (how long unbounded)", FIXTURE, {}, 300)
for label, text in (("H fixture, statement without payload", "SELECT count(), min(timestamp) FROM p.pay_slow"),):
    t0 = time.monotonic()
    rows = c.query(text).result_rows
    print(f"{label}: {rows} in {time.monotonic() - t0:.2f} s", flush=True)
print("max_threads of the server:", c.command("SELECT value FROM system.settings WHERE name = 'max_threads'"))
# read in order and stop at the first match: same answer as min(), nothing stored without a match
c.command("INSERT INTO p.out SELECT toStartOfHour(timestamp) FROM p.real WHERE JSONHas(ifNull(payload, ''), "
          "'shape_type') ORDER BY timestamp LIMIT 1")
c.command("INSERT INTO p.out SELECT toStartOfHour(timestamp) FROM p.real WHERE JSONHas(ifNull(payload, ''), "
          "'other') ORDER BY timestamp LIMIT 1")
print("order-by-limit rows stored (expect 1):", c.command("SELECT count() FROM p.out"), flush=True)
