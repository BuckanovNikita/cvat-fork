"""Acceptance of Team Analytics on the backend path (ticket 11 of .scratch/standard-fork), driven by run.sh. Each
command judges itself (non-zero exit on a failure) and prints the numbers it measured.

    acceptance.py cross-org             an overview organization A's maintainer loaded is not served to organization
                                        B's maintainer asking the same parameters, nor an administrator's status to
                                        a maintainer
    acceptance.py isolation [PART]      CVAT's core operations (sign-in, the task list, opening a job's data and
                                        annotations, saving annotations) and the analytics endpoints' answer times:
                                        worker-down (the analytics worker at zero while twelve analytics requests
                                        wait), clickhouse-down (ClickHouse at zero), totals-dropped (DROP DATABASE of
                                        the totals; the figures come back by themselves); all three without PART.
                                        Restores what it changed, also on a failure
    acceptance.py load                  p95 of the task list and of a job's annotations, taken sequentially before
                                        and while twelve concurrent uncached overviews run, during a refresh and
                                        while history is being filled (the volume organization's data)
    acceptance.py review                the reviews' fixes: parameters an overview ignores answer from the cache,
                                        values over their length are refused by the API, no-store on every
                                        refusal and on a 429, the generation a counter moving once per refresh run,
                                        copies of the refresh job piled up at zero workers removed by its first run
    acceptance.py analytics-off         with the release reinstalled with analytics disabled: the server answers,
                                        /api/team-analytics/ is 404 and no refresh is scheduled
    acceptance.py worker-replicas N     scales the analytics worker; back up, waits until status is answered
    acceptance.py cache advance|unready a new generation of the totals (no cached answer found), or no ready mark

Environment: TA_BASE_URL, TA_SEED_PASSWORD, TA_KUBE_CONTEXT, TA_NAMESPACE, TA_RELEASE, TA_VOLUME_ORG (optional).
Standard library only.
"""

from __future__ import annotations

import calendar
import http.cookiejar
import json
import math
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run with python3 -I, which leaves it out

from final_run import VOLUME_ORG, clickhouse  # noqa: E402
from stack_api import (  # noqa: E402
    API,
    BASE_URL,
    PASSWORD,
    Session,
    check,
    expected_rows,
    figures,
    get_json,
    not_ready,
    raw_get,
    upload_images,
)
from stack_ops import (  # noqa: E402
    CLICKHOUSE,
    CLICKHOUSE_SELECTOR,
    WORKER,
    WORKER_SELECTOR,
    django_cache,
    django_settings,
    first_pod,
    generation,
    lock_samples,
    memory_mib,
    redis,
    scale,
    server_db_connections,
    wait_lock,
    worker_log,
)

TOTALS = "team_analytics"  # TEAM_ANALYTICS_DB, the app's default
# a read job starting in the worker's log: its endpoint, scope and parameters (the key after them is left out)
READ_LINE = re.compile(r"jobs\.read_answer\((.*), '[0-9a-f]+'\)")
# The API's wait for an answer that is not cached (TEAM_ANALYTICS_READ_WAIT_S) and the Retry-After of its 429
# (TEAM_ANALYTICS_READ_RETRY_AFTER_S), as the backend has them in force (read once from the server pod), and the
# margin a reply may take beyond the wait (the request's own handling, the proxy, the port-forward).
REPLY_MARGIN_S = 2.0
# the budget with a 1 s Retry-After, which the ticket named; how many readers fit within it is printed too
EARLIER_BUDGET_S = 23.0
_settings: dict = {}


def read_settings() -> dict:
    if not _settings:
        _settings.update(django_settings("TEAM_ANALYTICS_READ_WAIT_S", "TEAM_ANALYTICS_READ_RETRY_AFTER_S"))
    return _settings


def read_wait_s() -> float:
    return float(read_settings()["TEAM_ANALYTICS_READ_WAIT_S"])


def client_budget_s() -> float:
    """The page's retry budget: cvat-core asks three times more after a 429, each after its Retry-After, and every
    attempt waits up to the read wait: 4 x wait + 3 x Retry-After (29 s with the defaults 5 and 3)."""
    return 4 * read_wait_s() + 3 * float(read_settings()["TEAM_ANALYTICS_READ_RETRY_AFTER_S"])


CONCURRENT = 12
# ta-worker-c annotates in ta-org-c (final_run.py); the isolation checks open and save a job of their own there.
CORE_ORG = "ta-org-c"
CORE_OWNER = "ta-owner-c"
CORE_USER = "ta-worker-c"
CORE_PROJECT = "ta-isolation"
ADMIN_ONLY_HISTORY = {"first_day", "days_ready", "days_total"}  # status keys only administrators get


def log(message: str) -> None:
    print(f"  {message}", flush=True)


def result(name: str, ok: bool, detail: str) -> bool:
    print(f"[acceptance] {'PASS' if ok else 'FAIL'} {name}: {detail}", flush=True)
    return ok


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile (q in 0..100); NaN for no values."""
    if not values:
        return math.nan
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q / 100 * len(ordered)) - 1)]


def summary(values: list[float]) -> str:
    if not values:
        return "n=0"
    return (f"n={len(values)} p50={percentile(values, 50):.0f} p95={percentile(values, 95):.0f} "
            f"max={max(values):.0f} ms")


def analytics(endpoint: str, **params: str) -> str:
    return API + endpoint + "?" + urllib.parse.urlencode({"tz": "UTC", **params})


def wait_answered(timeout_s: int = 300) -> float:
    """Waits until ta-admin's status is answered with its sections (200, refresh known); the seconds it took."""
    admin = Session("ta-admin")
    started = time.monotonic()
    while True:
        status, body = admin.call(analytics("status", org=""))
        if status == 200 and body.get("refresh") is not None:
            return time.monotonic() - started
        check(time.monotonic() - started < timeout_s, f"status not answered within {timeout_s} s: {status} {body}")
        time.sleep(2)


def worker_replicas(n: int) -> None:
    scale(WORKER, n, WORKER_SELECTOR)
    if n:
        log(f"analytics worker at {n}; status answered after {wait_answered():.0f} s")
    else:
        log("analytics worker at 0, its pods gone")


# ---------------------------------------------------------------- timed HTTP


class Client:
    """A signed-in account whose requests are timed one by one and never retried, so a refusal or CVAT's own
    throttling shows as what it is and not as latency."""

    def __init__(self, username: str) -> None:
        self.username = username
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        status, ms, body = self.send("POST", "/api/auth/login", {"username": username, "password": PASSWORD})
        check(status == 200, f"{username}: sign-in {status} {body}")
        self.signin_ms = ms

    def send(self, method: str, path: str, body: object = None) -> tuple[int, float, object]:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(BASE_URL + path, data=data, method=method)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        if method != "GET":
            request.add_header("Origin", BASE_URL)
            csrf = next((c.value for c in self.jar if c.name == "csrftoken"), "")
            request.add_header("X-CSRFTOKEN", csrf)
        started = time.perf_counter()
        try:
            with self.opener.open(request, timeout=120) as resp:
                status, raw = resp.status, resp.read()
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
        ms = (time.perf_counter() - started) * 1000
        try:
            parsed = json.loads(raw.decode()) if raw.strip() else None
        except (UnicodeDecodeError, ValueError):
            parsed = f"<{len(raw)} bytes>"
        return status, ms, parsed


def isolation_job() -> dict:
    """ta-worker-c's job in ta-org-c's project ta-isolation, made once per stack: two small frames, one label."""
    owner = Session(CORE_OWNER)
    found = owner.request("GET", f"/api/projects?org={CORE_ORG}&name={CORE_PROJECT}")
    if found["count"]:
        project = found["results"][0]
        jobs = owner.request("GET", f"/api/jobs?org={CORE_ORG}&project_id={project['id']}&page_size=10")["results"]
    else:
        project = owner.request("POST", f"/api/projects?org={CORE_ORG}", {"name": CORE_PROJECT, "labels": [{"name": "box"}]})
        task = owner.request("POST", f"/api/tasks?org={CORE_ORG}", {"name": f"{CORE_PROJECT}-task", "project_id": project["id"]})
        upload_images(owner, task["id"], CORE_ORG, 2, side=64)
        for _ in range(120):
            jobs = owner.request("GET", f"/api/jobs?org={CORE_ORG}&task_id={task['id']}&page_size=10")["results"]
            if jobs:
                break
            time.sleep(2)
        else:
            raise SystemExit("the isolation task's job was not created within 4 minutes")
        user_id = Session(CORE_USER).request("GET", "/api/users/self")["id"]
        owner.request("PATCH", f"/api/jobs/{jobs[0]['id']}?org={CORE_ORG}", {"assignee": user_id})
    job = jobs[0]["id"]
    label = owner.request("GET", f"/api/labels?job_id={job}&org={CORE_ORG}")["results"][0]["id"]
    return {"job": job, "label": label}


def core_operations(ids: dict) -> tuple[bool, list[tuple[str, int, float]]]:
    """CVAT's core operations as the annotator ta-worker-c, each timed: sign-in, the task list, opening the job (its
    record, data meta and first chunk, annotations), saving a new box and deleting it again. Every one must succeed
    (2xx); a chunk that is still being prepared (429 with Retry-After) is asked for again within 60 s."""
    ops: list[tuple[str, int, float]] = []
    client = Client(CORE_USER)
    ops.append(("sign-in", 200, client.signin_ms))
    job, org = ids["job"], f"org={CORE_ORG}"

    def op(name: str, method: str, path: str, body: object = None) -> object:
        status, ms, parsed = client.send(method, path, body)
        ops.append((name, status, ms))
        return parsed

    op("task list", "GET", f"/api/tasks?{org}&page_size=10")
    op("job", "GET", f"/api/jobs/{job}?{org}")
    op("job data meta", "GET", f"/api/jobs/{job}/data/meta?{org}")
    started, total = time.monotonic(), 0.0
    while True:
        status, ms, _ = client.send("GET", f"/api/jobs/{job}/data?{org}&type=chunk&index=0&quality=compressed")
        total += ms
        if status != 429 or time.monotonic() - started > 60:
            break
        time.sleep(1)
    ops.append(("job chunk", status, total))
    op("annotations", "GET", f"/api/jobs/{job}/annotations?{org}")
    shape = {"type": "rectangle", "frame": 0, "label_id": ids["label"], "points": [4, 4, 30, 30],
             "occluded": False, "outside": False, "z_order": 0, "rotation": 0, "attributes": [], "group": 0,
             "source": "manual"}
    created = op("save (create a box)", "PATCH", f"/api/jobs/{job}/annotations?{org}&action=create",
                 {"version": 0, "tags": [], "shapes": [shape], "tracks": []})
    new = (created or {}).get("shapes") if isinstance(created, dict) else None
    if new:
        op("save (delete it)", "PATCH", f"/api/jobs/{job}/annotations?{org}&action=delete",
           {"version": 0, "tags": [], "shapes": new, "tracks": []})
    else:
        ops.append(("save (delete it)", 0, 0.0))
    ok = all(200 <= status < 300 for _, status, _ in ops)
    return ok, ops


def show_operations(ops: list[tuple[str, int, float]]) -> str:
    return ", ".join(f"{name} {status} {ms:.0f} ms" for name, status, ms in ops)


def probe(session: Session, endpoint: str, **params: str) -> tuple[int, float, object]:
    """One analytics request, not retried: (status, seconds, body)."""
    started = time.monotonic()
    status, body, _ = raw_get(session.opener, analytics(endpoint, **params))
    return status, time.monotonic() - started, body


# ---------------------------------------------------------------- isolation


def worker_down(ids: dict) -> bool:
    """(a) The analytics worker at zero and twelve analytics requests left waiting; meanwhile the core operations."""
    maintainer = Session("ta-maintainer")
    log(django_cache("advance"))  # no answer of the twelve is cached
    worker_replicas(0)
    attempts: list[tuple[int, int, float, object]] = []  # (request, status, seconds, body)
    stop = threading.Event()

    def ask(i: int) -> None:
        # the same parameters every time (one queued read per key), asked again at once after each 429, so
        # twelve requests wait in the API throughout the core operations
        path = analytics("overview", org="ta-org-a", period="week", annotator=str(900_001 + i))
        while not stop.is_set():
            started = time.monotonic()
            status, body, _ = raw_get(maintainer.opener, path)
            attempts.append((i, status, time.monotonic() - started, body))
            if status != 429:
                return

    db_before = server_db_connections()
    try:
        threads = [threading.Thread(target=ask, args=(i,), daemon=True) for i in range(CONCURRENT)]
        for thread in threads:
            thread.start()
        time.sleep(1.0)  # every request is in the API, waiting
        db_during = server_db_connections()  # a waiting request has let its database connection go
        ok, ops = core_operations(ids)
        stop.set()
        for thread in threads:
            thread.join(read_wait_s() + 30)
    finally:
        stop.set()
        worker_replicas(1)
    times = [s for _, _, s, _ in attempts]
    wrong = [(i, status, round(s, 1), str(body)[:80]) for i, status, s, body in attempts
             if not (status == 429 and not_ready(status, body, API) and s <= read_wait_s() + REPLY_MARGIN_S)]
    at_once = sum(1 for s in times if s < 1.0)
    log(f"core operations while {CONCURRENT} analytics requests waited: {show_operations(ops)}")
    log(f"analytics requests: {len(attempts)} attempts by {CONCURRENT} requests, all 429 within "
        f"{read_wait_s() + REPLY_MARGIN_S:.0f} s: {not wrong}; seconds min {min(times):.2f} max {max(times):.2f}; "
        f"refused at once (< 1 s, the queue limit): {at_once}")
    # twelve waiting requests that each kept a connection would add twelve; a few spare are other traffic
    db_ok = db_during["server"] <= db_before["server"] + 3
    log(f"Postgres connections of the CVAT server (pg_stat_activity): before {db_before['server']} (all clients "
        f"{db_before['all']}), while {CONCURRENT} requests waited {db_during['server']} (all {db_during['all']})")
    return result("isolation worker-down", ok and not wrong and len(attempts) >= CONCURRENT and db_ok,
                  f"core operations {'succeeded' if ok else 'FAILED'}; analytics answers outside 429-within-limit: {wrong[:5]}; "
                  f"server database connections {db_before['server']} -> {db_during['server']} while waiting")


def clickhouse_down(ids: dict) -> bool:
    """(b) ClickHouse at zero: the core operations, and the analytics endpoints answer (503 or 429) within the wait.
    Also: a refresh run that fails before any write (every run while ClickHouse is down) does not advance the
    generation, so an answer cached before the outage is still served from the cache, while one never cached is 503."""
    maintainer, admin = Session("ta-maintainer"), Session("ta-admin")
    cached = {"org": "ta-org-a", "period": "week", "project": "999001"}  # parameters the overview reads, nobody else asks
    never = {"org": "ta-org-a", "period": "week", "project": "999002"}
    status, body = get_json(maintainer.opener, analytics("overview", **cached))
    check(status == 200, f"the overview to keep cached: {status} {body}")
    warm_before = probe(maintainer, "overview", **cached)
    generation_before = generation()
    log(f"before the outage: overview {cached} cached ({warm_before[0]} in {warm_before[1]:.3f} s); generation "
        f"{generation_before}")
    since = utc_now()
    scale(CLICKHOUSE, 0, CLICKHOUSE_SELECTOR)
    log("ClickHouse at 0, its pod gone")
    answers = []
    kept: dict = {}
    try:
        # two refresh runs fail while ClickHouse is down; neither may advance the generation
        runs = wait_refresh_runs(2, since)
        generation_during = generation()
        still = probe(maintainer, "overview", **cached)
        fresh = probe(maintainer, "overview", **never)
        kept = {"runs": runs, "generation": generation_during, "cached": still, "never": fresh}
        log(f"with ClickHouse down, after {runs} refresh runs: generation {generation_before} -> {generation_during}; "
            f"the cached overview {still[0]} in {still[1]:.3f} s; one never cached {fresh[0]} in {fresh[1]:.2f} s {fresh[2]}")
        log(django_cache("advance"))  # nothing cached: every read goes to the worker
        ok, ops = core_operations(ids)
        for round_ in range(3):
            for session, endpoint, params in ((maintainer, "overview", {"org": "ta-org-a", "period": "week"}),
                                              (admin, "status", {"org": ""}),
                                              (admin, "trends", {"org": "", "step": "week"})):
                status, s, body = probe(session, endpoint, **params)
                answers.append((round_, endpoint, status, round(s, 2), body))
            time.sleep(3)
    finally:
        scale(CLICKHOUSE, 1, CLICKHOUSE_SELECTOR)
        log(django_cache("advance"))  # the 503 remembered for a few seconds is not served after the restore
        log(f"ClickHouse back at 1; status answered after {wait_answered(600):.0f} s")
    # status answers by sections and degrades each one it cannot read to null (core/endpoints/status.py), so with
    # ClickHouse down it is a 200 whose sections are all null; the other endpoints fail as a whole (503)
    def degraded_status(a) -> bool:
        return a[1] == "status" and a[2] == 200 and isinstance(a[4], dict) and all(v is None for v in a[4].values())

    wrong = [a for a in answers if not (
        (a[2] == 503 and a[4] == {"error": "unavailable"}) or (a[2] == 429 and not_ready(a[2], a[4], API))
        or degraded_status(a)
    ) or a[3] > read_wait_s() + REPLY_MARGIN_S]
    log(f"core operations with ClickHouse at zero: {show_operations(ops)}")
    log("analytics answers with ClickHouse at zero (round, endpoint, status, seconds): "
        + ", ".join(f"{r}:{e} {st} {s}s" for r, e, st, s, _ in answers))
    cache_kept = bool(kept) and kept["runs"] >= 2 and kept["generation"] == generation_before \
        and kept["cached"][0] == 200 and kept["cached"][1] < 1.0 \
        and kept["never"][0] == 503 and kept["never"][2] == {"error": "unavailable"}
    return result("isolation clickhouse-down", ok and not wrong and cache_kept,
                  f"core operations {'succeeded' if ok else 'FAILED'}; analytics answers outside 503/429 (status: 200 with "
                  f"every section null) within the limit: "
                  f"{[(e, st, s, str(b)[:60]) for _, e, st, s, b in wrong]}; generation unchanged over "
                  f"{kept.get('runs')} failed runs and the cached answer served, one never cached 503: {cache_kept}")


def overview_rows(session: Session, org: str) -> list | None:
    status, body = session.call(analytics("overview", org=org, period="week"))
    if status != 200 or not body.get("processed"):
        return None
    return figures(body)


def totals_dropped(ids: dict) -> bool:
    """(c) The totals database dropped: the core operations, the analytics endpoints' answers within the wait, and
    the figures back by themselves once a refresh run has recreated the schema and history is recomputed."""
    maintainer, admin, volume_owner = Session("ta-maintainer"), Session("ta-admin"), Session("ta-owner-v")
    before = {"ta-org-a": overview_rows(maintainer, "ta-org-a"), VOLUME_ORG: overview_rows(volume_owner, VOLUME_ORG)}
    status, body = admin.call(analytics("status", org=""))
    cutover_before = (body.get("cutover") or {}).get("at") if status == 200 else None
    check(all(v is not None for v in before.values()), f"figures before the drop: {before}")
    log(f"before: ta-org-a week {before['ta-org-a']}; {VOLUME_ORG} week {len(before[VOLUME_ORG])} rows; cutover {cutover_before}")
    clickhouse(f"DROP DATABASE {TOTALS}")
    dropped_at = time.monotonic()
    log(f"DROP DATABASE {TOTALS} on the stack's ClickHouse")
    log(django_cache("advance"))  # nothing cached: the reads meet the missing database
    ok, ops = core_operations(ids)
    answers = []
    for endpoint, session, params in (("overview", maintainer, {"org": "ta-org-a", "period": "week"}),
                                      ("status", admin, {"org": ""})):
        status, s, body = probe(session, endpoint, **params)
        answers.append((endpoint, status, round(s, 2), body))
    log(f"core operations without the totals database: {show_operations(ops)}")
    log("analytics answers right after the drop: " + ", ".join(f"{e} {st} {s}s {str(b)[:60]}" for e, st, s, b in answers))
    in_limit = all(s <= read_wait_s() + REPLY_MARGIN_S and st in (200, 429, 503) for _, st, s, _ in answers)
    marks: dict[str, float] = {}
    cutover_after = None
    restored_ready = False
    deadline = dropped_at + 1800
    while time.monotonic() < deadline:
        elapsed = time.monotonic() - dropped_at
        if "schema" not in marks:
            exists = clickhouse(f"EXISTS DATABASE {TOTALS}")
            if exists and int(next(iter(exists[0].values()))) == 1:
                marks["schema"] = elapsed
                log(f"the totals database exists again after {elapsed:.0f} s (a refresh run recreated it)")
        status, body = admin.call(analytics("status", org=""))
        if status == 200:
            if "refresh" not in marks and (body.get("refresh") or {}).get("last_success_at"):
                marks["refresh"] = elapsed
                log(f"first refresh after the drop recorded after {elapsed:.0f} s")
            cutover_after = (body.get("cutover") or {}).get("at")
            if "complete" not in marks and (body.get("history") or {}).get("complete"):
                marks["complete"] = elapsed
                log(f"history complete again after {elapsed:.0f} s; cutover {cutover_after}")
        for org, session in (("ta-org-a", maintainer), (VOLUME_ORG, volume_owner)):
            if f"figures {org}" not in marks and "schema" in marks:
                rows = overview_rows(session, org)
                if rows is not None and rows == before[org]:
                    marks[f"figures {org}"] = elapsed
                    log(f"{org}: the week's figures are back and equal to before, after {elapsed:.0f} s")
        if "complete" in marks and all(f"figures {o}" in marks for o in before):
            if cutover_after == cutover_before or restored_ready:
                break
            # the cutover is looked for once, before the first answer, and the ready mark says it was: a dropped
            # database does not bring the search back. Restored here by removing the mark, as a fresh start has it
            log(f"history complete, but the cutover is {cutover_after} (before: {cutover_before}); removing the ready mark")
            log(django_cache("unready"))
            log(django_cache("advance"))
            restored_ready = True
        time.sleep(5)
    log(f"after the drop (seconds): {', '.join(f'{k} {v:.0f}' for k, v in marks.items())}; cutover after {cutover_after}"
        f"{' (after the ready mark was removed)' if restored_ready else ''}")
    back = all(f"figures {o}" in marks for o in before) and "complete" in marks
    return result("isolation totals-dropped", ok and in_limit and back and cutover_after == cutover_before,
                  f"core operations {'succeeded' if ok else 'FAILED'}; analytics answered within the limit: {in_limit}; "
                  f"figures back by themselves: {back}; cutover kept by itself: {not restored_ready and cutover_after == cutover_before}"
                  f"{'; NOTE the cutover came back only after the ready mark was removed' if restored_ready else ''}")


def isolation(part: str | None) -> None:
    parts = {"worker-down": worker_down, "clickhouse-down": clickhouse_down, "totals-dropped": totals_dropped}
    check(part is None or part in parts, f"unknown part {part} ({', '.join(parts)})")
    ids = isolation_job()
    log(f"core operations on job {ids['job']} of {CORE_PROJECT} in {CORE_ORG}, as {CORE_USER}")
    ok, ops = core_operations(ids)
    log(f"core operations, everything up (reference): {show_operations(ops)}")
    check(ok, "the core operations fail with everything up")
    failed = [name for name, run in parts.items() if (part is None or part == name) and not run(ids)]
    if failed:
        raise SystemExit(f"[acceptance] FAIL isolation: {', '.join(failed)}")


# ---------------------------------------------------------------- cross-organization cache


def cross_org() -> None:
    a, b = Session("ta-maintainer"), Session("ta-maintainer-b")
    admin = Session("ta-admin")
    problems = []
    for order, params in ((("a", "b"), {"period": "week", "shapes": "all"}),
                          (("b", "a"), {"period": "week", "shapes": "bounding_boxes"})):
        log(django_cache("advance"))  # the first request of each pair is a miss
        got = {}
        for side in order:
            session, org = (a, "ta-org-a") if side == "a" else (b, "ta-org-b")
            status, body = session.call(analytics("overview", org=org, **params))
            got[side] = figures(body) if status == 200 else (status, body)
        want = {"a": expected_rows("ta-org-a"), "b": expected_rows("ta-org-b")}
        log(f"{' then '.join(order)} {params}: ta-org-a {got['a']}, ta-org-b {got['b']}")
        if got != want:
            problems.append(f"{order} {params}: {got}, expected {want}")
    for order in (("admin", "maintainer"), ("maintainer", "admin")):
        log(django_cache("advance"))
        keys = {}
        for who in order:
            session = admin if who == "admin" else a
            status, body = session.call(analytics("status", org="ta-org-a"))
            keys[who] = sorted(ADMIN_ONLY_HISTORY & set((body.get("history") or {}) if status == 200 else {}))
        log(f"status org=ta-org-a, {' then '.join(order)}: administrator-only history keys {keys}")
        if keys != {"admin": sorted(ADMIN_ONLY_HISTORY), "maintainer": []}:
            problems.append(f"status {order}: {keys}")
    if problems:
        raise SystemExit(f"[acceptance] FAIL cross-org: {problems}")
    result("cross-org", True, "each organization's maintainer got its own figures in either order; the administrator's "
                              "status was not served to the maintainer, nor the maintainer's to the administrator")


# ---------------------------------------------------------------- load


TOLERANCE_FACTOR = 1.5
TOLERANCE_MS = 25.0
BASELINE_SAMPLES = 100
BURSTS = 3


class Sampler:
    """The two core endpoints read one after the other by one client, as the baseline is taken."""

    def __init__(self, client: Client, tasks_path: str, annotations_path: str) -> None:
        self.client, self.paths = client, {"tasks": tasks_path, "annotations": annotations_path}
        self.samples: dict[str, list[float]] = {"tasks": [], "annotations": []}
        self.failures: list[tuple[str, int]] = []

    def once(self, name: str) -> None:
        status, ms, body = self.client.send("GET", self.paths[name])
        if status == 200:
            self.samples[name].append(ms)
        else:  # CVAT's throttling shows here as a failure, not as latency
            self.failures.append((name, status, str(body)[:80]))

    def run(self, n: int) -> None:
        for name in ("tasks", "annotations"):
            for _ in range(n):
                self.once(name)

    def run_until(self, stop: threading.Event) -> None:
        while not stop.is_set():
            self.once("tasks")
            self.once("annotations")


def overview_client(session: Session, params: dict, out: list) -> None:
    """One reader: asks for an overview until it has figures, after each 429 waiting its Retry-After, within the
    client's budget; records (params, status, total seconds, attempts, processed)."""
    path = analytics("overview", org=VOLUME_ORG, **params)
    started, attempts = time.monotonic(), 0
    while True:
        attempts += 1
        status, body, headers = raw_get(session.opener, path)
        elapsed = time.monotonic() - started
        if not not_ready(status, body, path):
            break
        wait = float(headers.get("retry-after") or 1)
        if elapsed + wait > client_budget_s():
            break
        time.sleep(wait)
    processed = isinstance(body, dict) and body.get("processed") is True and body.get("by_annotator") is not None
    out.append((params, status, elapsed, attempts, processed))


def burst(owner: Session, sampler: Sampler, param_sets: list[dict], memory: list) -> tuple[list, dict]:
    """Twelve overview clients at once while the sampler reads the core endpoints and the refresh lock and the
    memory of the worker and of ClickHouse are watched."""
    readers: list = []
    stop = threading.Event()
    held: dict = {}
    worker_pod, clickhouse_pod = first_pod(WORKER_SELECTOR), first_pod(CLICKHOUSE_SELECTOR)

    def watch() -> None:
        while not stop.is_set():
            memory.append((memory_mib(worker_pod, "cvat-backend")[0], memory_mib(clickhouse_pod, "clickhouse")[0]))
            time.sleep(0.5)

    def watch_lock() -> None:  # the lock looked at in the Redis pod itself, every 50 ms, for the client budget
        held["yes"], held["looks"] = lock_samples(int(client_budget_s()) + 1)

    sampling = threading.Thread(target=sampler.run_until, args=(stop,), daemon=True)
    watching = threading.Thread(target=watch, daemon=True)
    locking = threading.Thread(target=watch_lock, daemon=True)
    locking.start()
    clients = [threading.Thread(target=overview_client, args=(owner, p, readers), daemon=True) for p in param_sets]
    sampling.start()
    watching.start()
    for c in clients:
        c.start()
    for c in clients:
        c.join(client_budget_s() + 60)
    stop.set()
    sampling.join(30)
    watching.join(30)
    locking.join(client_budget_s() + 30)
    return readers, held


def pending_days() -> int:
    return int(clickhouse(
        f"SELECT count() AS n FROM (SELECT day FROM {TOTALS}.history_days GROUP BY day HAVING argMax(pending, version) = 1)"
    )[0]["n"])


def mark_history_pending(older_than_days: int) -> int:
    """Marks every computed day older than `older_than_days` for computing again, as the daily check does for a day
    whose raw count changed (control/history_mark_pending.sql); the refresh job then recomputes them a day per step.
    The current week stays processed, so its overviews keep their figures. Returns the number of days marked."""
    clickhouse(
        f"INSERT INTO {TOTALS}.history_days (day, raw_rows, pending, version, at)"
        f" SELECT day, argMax(raw_rows, version), 1, (SELECT max(version) FROM {TOTALS}.history_days) + 1, now64(3)"
        f" FROM {TOTALS}.history_days WHERE day < today() - {older_than_days}"
        # only days history visits: from the first day with events (a day before it, such as check-fixes
        # unprocessed's probe days, would stay pending for good)
        f" AND day >= (SELECT toDate(min(timestamp)) FROM events) GROUP BY day"
    )
    return pending_days()


def load() -> None:
    owner = Session("ta-owner-v")
    client = Client("ta-owner-v")
    jobs = owner.request("GET", f"/api/jobs?org={VOLUME_ORG}&page_size=100")["results"]
    check(jobs, f"{VOLUME_ORG} has no jobs (run.sh load-volume first)")
    job = jobs[0]["id"]
    projects = [p["id"] for p in owner.request("GET", f"/api/projects?org={VOLUME_ORG}&page_size=100")["results"]]
    members = []
    page = 1
    while True:
        listed = owner.request("GET", f"/api/memberships?org={VOLUME_ORG}&page_size=100&page={page}")
        members += [m["user"]["id"] for m in listed["results"] if m["role"] == "worker"]
        if not listed.get("next"):
            break
        page += 1
    check(len(projects) >= BURSTS * CONCURRENT and len(members) >= BURSTS * CONCURRENT,
          f"{VOLUME_ORG}: {len(projects)} projects and {len(members)} annotators, need {BURSTS * CONCURRENT} of each")
    tasks_path = f"/api/tasks?org={VOLUME_ORG}&page_size=10"
    annotations_path = f"/api/jobs/{job}/annotations?org={VOLUME_ORG}"
    log(f"core endpoints: GET {tasks_path} and GET {annotations_path}, sequential, as ta-owner-v")
    memory: list = []
    report = {}
    all_ok = True
    duplicates: list = []
    generation_moves: list = []

    def condition(name: str, param_sets: list[list[dict]], before, each=None) -> None:
        nonlocal all_ok
        base = Sampler(client, tasks_path, annotations_path)
        base.run(BASELINE_SAMPLES)
        log(f"{name}: baseline tasks {summary(base.samples['tasks'])}; annotations {summary(base.samples['annotations'])}"
            f"; failures {base.failures}")
        before()
        sampler = Sampler(client, tasks_path, annotations_path)
        readers_all = []
        for i, sets in enumerate(param_sets):
            if name == "refresh":
                # the refresh job is scheduled every minute and holds the lock for its step only (about a second
                # on this data): the burst starts the moment the lock is seen
                waited = time.monotonic()
                seen = wait_lock(90)
                log(f"{name} burst {i + 1}: refresh lock {'seen' if seen else 'NOT seen'} after "
                    f"{time.monotonic() - waited:.1f} s of waiting")
            if each:
                each(i)
            pending_start = pending_days()
            generation_start = generation()
            since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 1))
            readers, held = burst(owner, sampler, sets, memory)
            readers_all += readers
            times = sorted(round(r[2], 1) for r in readers)
            log(f"{name} burst {i + 1}: {len(readers)} overviews, statuses {sorted({r[1] for r in readers})}, "
                f"seconds {times}, attempts {sorted(r[3] for r in readers)}; refresh lock held in "
                f"{held.get('yes')}/{held.get('looks')} looks (every 50 ms); history days pending {pending_start} -> {pending_days()}")
            # the worker's log over the burst: every read of these parameters ran once, and the generation moved once
            # per refresh run, not once per day of history
            lines = worker_log(since)
            reads = Counter(m.group(1) for m in (READ_LINE.search(line) for line in lines) if m)
            days = sum(1 for line in lines if "history: computed" in line)
            runs = sum(1 for line in lines if "Job OK (team_analytics_refresh)" in line)
            repeated = {k: n for k, n in reads.items() if n > 1}
            generation_end = generation()
            log(f"{name} burst {i + 1}, worker log: {sum(reads.values())} read jobs for {len(reads)} distinct requests, "
                f"repeated {repeated or 'none'}; {days} history days computed in {runs} refresh runs; generation "
                f"{generation_start} -> {generation_end}")
            duplicates.extend(repeated)
            generation_moves.append((generation_start, generation_end, runs, days))
        bad = [r for r in readers_all if not (r[1] == 200 and r[4] and r[2] <= client_budget_s())]
        if duplicates:
            bad.append(("reads repeated within a burst", duplicates[:3]))
        verdicts = []
        for endpoint in ("tasks", "annotations"):
            b, l_ = percentile(base.samples[endpoint], 95), percentile(sampler.samples[endpoint], 95)
            limit = TOLERANCE_FACTOR * b + TOLERANCE_MS
            verdicts.append(l_ <= limit)
            log(f"{name}: {endpoint} baseline {summary(base.samples[endpoint])} | under load "
                f"{summary(sampler.samples[endpoint])} | limit p95 {limit:.0f} ms -> {'within' if l_ <= limit else 'OVER'}")
        report[name] = {"overviews_bad": bad, "p95_within": verdicts, "failures": sampler.failures + base.failures}
        ok = not bad and all(verdicts) and not sampler.failures and not base.failures
        all_ok &= ok
        within_earlier = sum(1 for r in readers_all if r[1] == 200 and r[4] and r[2] <= EARLIER_BUDGET_S)
        result(f"load {name}", ok, f"{len(readers_all)} overviews, {len(readers_all) - len(bad)} with figures within "
                                   f"{client_budget_s():.0f} s ({within_earlier} within {EARLIER_BUDGET_S:.0f} s); p95 within tolerance (tasks, annotations): {verdicts}; "
                                   f"core failures {sampler.failures + base.failures}; bad overviews {bad[:3]}")

    project_sets = [[{"period": "week", "project": str(p)} for p in projects[i * CONCURRENT:(i + 1) * CONCURRENT]]
                    for i in range(BURSTS)]
    annotator_sets = [[{"period": "week", "annotator": str(u)} for u in members[i * CONCURRENT:(i + 1) * CONCURRENT]]
                      for i in range(BURSTS)]
    log(f"tolerance: p95 under load <= {TOLERANCE_FACTOR} x baseline p95 + {TOLERANCE_MS:.0f} ms; settings in force "
        f"{read_settings()}: the client's budget {client_budget_s():.0f} s")
    condition("refresh", project_sets, lambda: log(django_cache("advance")))

    def fill_history(i: int) -> None:
        # the history step recomputes a day in well under a second on this data, so the days are marked again right
        # before each burst, which starts at once: the refresh job has history to do while the readers ask
        # and the burst waits for the minute's run of the refresh job to take the lock (it then steps through
        # history until a read is waiting)
        marked = mark_history_pending(7)
        waited = time.monotonic()
        seen = wait_lock(90)
        log(f"history burst {i + 1}: {marked} days older than a week marked for recomputing (as the daily check "
            f"marks a changed day); refresh lock {'seen' if seen else 'NOT seen'} after {time.monotonic() - waited:.1f} s")

    condition("history", annotator_sets, lambda: log(django_cache("advance")), fill_history)
    worker_mib = [m[0] for m in memory if not math.isnan(m[0])]
    clickhouse_mib = [m[1] for m in memory if not math.isnan(m[1])]
    peaks = (memory_mib(first_pod(WORKER_SELECTOR), "cvat-backend")[1], memory_mib(first_pod(CLICKHOUSE_SELECTOR), "clickhouse")[1])
    log(f"memory during the bursts (MiB, cgroup memory.current every 0.5 s): worker max {max(worker_mib, default=0):.0f} "
        f"(min {min(worker_mib, default=0):.0f}), ClickHouse max {max(clickhouse_mib, default=0):.0f} "
        f"(min {min(clickhouse_mib, default=0):.0f}); peak since container start (memory.peak): worker {peaks[0]}, "
        f"ClickHouse {peaks[1]}")
    waited = time.monotonic()
    while pending_days() and time.monotonic() - waited < 1200:
        time.sleep(10)
    left = pending_days()
    log(f"history recomputed again after {time.monotonic() - waited:.0f} s more ({left} days pending)")
    all_ok &= result("load restore", left == 0, f"{left} history days left pending")
    if not all_ok:
        raise SystemExit("[acceptance] FAIL load")


# ---------------------------------------------------------------- analytics disabled


def analytics_off() -> None:
    status, about, _ = raw_get(urllib.request.build_opener(), "/api/server/about")
    check(status == 200, f"server about: {status} {about}")
    log(f"/api/server/about: 200, version {about.get('version')}")
    admin = Client("ta-admin")
    status, ms, _ = admin.send("GET", "/api/tasks?page_size=10")
    check(status == 200, f"ta-admin task list: {status}")
    log(f"ta-admin signed in ({admin.signin_ms:.0f} ms), task list 200 ({ms:.0f} ms)")
    codes = {}
    for endpoint in ("status", "overview", "trends", "list", "details"):
        codes[endpoint] = (admin.send("GET", analytics(endpoint, org=""))[0],
                           raw_get(urllib.request.build_opener(), analytics(endpoint, org=""))[0])
    log(f"/api/team-analytics/<endpoint> (administrator, signed out): {codes}")
    scheduled = redis("ZSCORE", "rq:scheduler:scheduled_jobs", "team_analytics_refresh")
    stored = redis("SMEMBERS", "cvat:utils:periodic-jobs:team_analytics")
    job = redis("EXISTS", "rq:job:team_analytics_refresh")
    queued = redis("LLEN", "rq:queue:team_analytics")
    log(f"rq scheduler: team_analytics_refresh scheduled at {scheduled or '(none)'}; periodic jobs of the queue "
        f"{stored or '(none)'}; job record exists {job}; jobs waiting in rq:queue:team_analytics {queued}")
    # over more than a minute (the schedule's period) nothing is added to the queue nobody consumes now
    time.sleep(75)
    queued_after = redis("LLEN", "rq:queue:team_analytics")
    log(f"jobs waiting in rq:queue:team_analytics 75 s later: {queued_after}")
    ok_codes = all(c == (404, 404) for c in codes.values())
    no_schedule = scheduled in ("", "(nil)") and job.endswith("0") and queued_after == queued
    result("analytics-off endpoints", ok_codes, f"every endpoint 404 for the administrator and signed out: {codes}")
    result("analytics-off schedule", no_schedule,
           "no refresh scheduled, nothing added to the queue" if no_schedule else
           f"the refresh is still scheduled ({scheduled}, job record {job}) or the queue grew ({queued} -> {queued_after})")
    if not (ok_codes and no_schedule):
        raise SystemExit("[acceptance] FAIL analytics-off")


# ---------------------------------------------------------------- the review's fixes


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 1))


def read_jobs_since(since: str) -> list[str]:
    return [m.group(1) for m in (READ_LINE.search(line) for line in worker_log(since)) if m]


_LOG_TIME = re.compile(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d{3})\]")


def refresh_runs(lines: list[str]) -> list[dict]:
    """The refresh runs in a worker log: when each ended (epoch seconds, UTC) and whether it wrote (a refresh of
    recent hours, or a day of history, recorded)."""
    runs, current = [], None
    for line in lines:
        if "jobs.refresh_totals()" in line:
            current = {"wrote": False}
        elif current is not None and ("core.refresh: refreshed" in line or "core.history: history:" in line):
            current["wrote"] = True
        elif current is not None and "Job OK (team_analytics_refresh)" in line:
            m = _LOG_TIME.match(line)
            if m:
                current["end"] = calendar.timegm(time.strptime(m.group(1), "%Y-%m-%d %H:%M:%S")) + int(m.group(2)) / 1000
                runs.append(current)
            current = None
    return runs


def wait_refresh_runs(n: int, since: str, timeout_s: int = 300) -> int:
    """Waits until `n` refresh runs have ended since `since`; how many did."""
    started = time.monotonic()
    while True:
        done = len(refresh_runs(worker_log(since)))
        if done >= n or time.monotonic() - started > timeout_s:
            return done
        time.sleep(5)


def timed_get(session, path: str) -> tuple[int, float, object, dict]:
    started = time.monotonic()
    status, body, headers = raw_get(session.opener, path)
    return status, time.monotonic() - started, body, headers


def review() -> None:
    """The fixes of the independent reviews, on the running stack: ignored parameters answer from the cache, values
    over their length are refused by the API, every refusal and 429 carries no-store, the generation is a counter
    that moves once per refresh run, copies of the refresh job piled up while no worker ran are removed."""
    oks: list[bool] = []
    maintainer, worker = Session("ta-maintainer"), Session("ta-worker")
    anonymous = type("Anonymous", (), {"opener": urllib.request.build_opener()})()

    # 1. a parameter the overview does not read changes neither the key nor the job
    base = {"org": "ta-org-a", "period": "week", "shapes": "all"}
    get_json(maintainer.opener, analytics("overview", **base))  # cached now
    since = utc_now()
    warm = timed_get(maintainer, analytics("overview", **base))
    times = []
    for name in ("search", "cachebust"):
        for v in range(5):
            status, s, body, _ = timed_get(maintainer, analytics("overview", **base, **{name: f"x{v}-{name}"}))
            times.append((name, v, status, round(s, 3)))
    time.sleep(2)
    jobs = read_jobs_since(since)
    ok = all(st == 200 and s < 1.0 for _, _, st, s in times) and not jobs
    log(f"1. overview warm {warm[0]} {warm[1]:.3f} s; with ignored parameters (name, value, status, s): {times}; "
        f"read jobs in the worker's log meanwhile: {jobs}")
    oks.append(result("review ignored-parameters", ok, f"10 requests with search/cachebust from the cache, {len(jobs)} read jobs"))

    # 2. a value over its length is refused by the API at once; a wrong short period by the worker
    since = utc_now()
    cases = []
    for params in ({"tz": "A" * 65}, {"month": "2026-111"}):
        status, s, body, _ = timed_get(maintainer, analytics("overview", org="ta-org-a", period="week", **params))
        cases.append((list(params)[0], status, round(s, 3), body))
    time.sleep(2)
    api_jobs = read_jobs_since(since)
    status, s, body, _ = timed_get(maintainer, analytics("overview", org="ta-org-a", period="fortnight"))
    time.sleep(2)
    worker_jobs = [j for j in read_jobs_since(since) if "fortnight" in j]
    ok = (all(st == 400 and t < 1.0 and isinstance(b, dict) and b.get("error") == "bad_request"
              and str(b.get("detail", "")).endswith("is too long") for _, st, t, b in cases)
          and not api_jobs and status == 400 and isinstance(body, dict) and body.get("error") == "bad_request"
          and len(worker_jobs) == 1)
    log(f"2. too long (parameter, status, s, body): {cases}; read jobs for them: {api_jobs}; period=fortnight: {status} "
        f"{s:.2f} s {body}, read jobs for it {len(worker_jobs)}")
    oks.append(result("review length-limits", ok, "too long: 400 from the API with no job; a wrong period: 400 from the worker"))

    # 3 (without the 429, which part 6 checks): no-store on every refusal
    refusals = {
        "403 forbidden": timed_get(worker, analytics("status", org="ta-org-a")),
        "403 organization_required": timed_get(maintainer, analytics("status", org="")),
        "401": timed_get(anonymous, analytics("status", org="ta-org-a")),
        "404 unknown organization": timed_get(maintainer, analytics("status", org="ta-no-such-org")),
    }
    seen = {k: (v[0], v[3].get("cache-control"), v[2]) for k, v in refusals.items()}
    ok = all(v[1] == "no-store" for v in seen.values()) and [v[0] for v in seen.values()] == [403, 403, 401, 404]
    log(f"3. refusals (status, Cache-Control, body): {seen}")
    oks.append(result("review no-store", ok, "every refusal carries Cache-Control: no-store"))

    # 4. the generation: an integer counter (it starts at the time in seconds when none exists), one step for each
    # refresh run that wrote and none for a run with nothing due, read every 2 s against the worker's log
    since = utc_now()
    started = time.time()
    changes: list[tuple[float, int | None, int | None]] = []  # (time, before, after)
    previous = generation()
    first = previous
    while time.time() - started < 250:
        time.sleep(2)
        now = generation()
        if now != previous:
            changes.append((time.time(), previous, now))
            previous = now
    ended = time.time()
    runs = [r for r in refresh_runs(worker_log(since)) if r["end"] < ended - 1]
    writing = [r for r in runs if r["wrote"]]
    steps_ok = all(isinstance(a, int) and isinstance(b, int) and b == a + 1 for _, a, b in changes)
    # every change follows a run that wrote by a few seconds at most, and every such run made one
    matched = all(any(0 <= t - r["end"] <= 5 for r in writing) for t, _, _ in changes)
    ok = isinstance(first, int) and steps_ok and matched and len(changes) == len(writing) and len(runs) >= 2
    log(f"4. generation over {ended - started:.0f} s: {first} -> {previous}; changes "
        f"{[(time.strftime('%H:%M:%S', time.gmtime(t)), a, b) for t, a, b in changes]}; refresh runs "
        f"{[(time.strftime('%H:%M:%S', time.gmtime(r['end'])), 'wrote' if r['wrote'] else 'nothing due') for r in runs]}")
    oks.append(result("review generation", ok, f"{len(changes)} steps of +1 for {len(writing)} runs that wrote, none for "
                                              f"{len(runs) - len(writing)} run(s) with nothing due"))

    # 6. copies of the refresh job pile up while no worker runs, and the first run removes them
    log(django_cache("advance"))
    worker_replicas(0)
    try:
        time.sleep(180)
        queued = redis("LRANGE", "rq:queue:team_analytics", "0", "-1")
        copies = queued.count("team_analytics_refresh")
        status, s, body, headers = timed_get(maintainer, analytics("overview", org="ta-org-a", period="month"))
        log(f"6. after 180 s at zero: {copies} copies of team_analytics_refresh in rq:queue:team_analytics; an overview "
            f"meanwhile: {status} after {s:.2f} s, Retry-After {headers.get('retry-after')}, Cache-Control "
            f"{headers.get('cache-control')}")
        refused_429 = status == 429 and s >= read_wait_s() - 0.5 and headers.get("cache-control") == "no-store"
    finally:
        worker_replicas(1)
    since = utc_now()
    waited = time.monotonic()
    left = copies
    while time.monotonic() - waited < 150:
        left = redis("LRANGE", "rq:queue:team_analytics", "0", "-1").count("team_analytics_refresh")
        if any("Job OK (team_analytics_refresh)" in line for line in worker_log(since)) and left == 0:
            break
        time.sleep(3)
    status_after, body_after = get_json(maintainer.opener, analytics("overview", org="ta-org-a", period="month"))
    log(f"6. after the worker came back: copies left {left} after {time.monotonic() - waited:.0f} s; the overview "
        f"{status_after}")
    ok = copies >= 2 and refused_429 and left == 0 and status_after == 200
    oks.append(result("review pile-up", ok, f"{copies} copies while at zero, 0 after the first run; the overview 429 "
                                            f"after the wait with no-store, then 200"))
    if not all(oks):
        raise SystemExit("[acceptance] FAIL review")


def main() -> None:
    args = sys.argv[1:]
    if args == ["cross-org"]:
        cross_org()
    elif args == ["review"]:
        review()
    elif args[:1] == ["isolation"] and len(args) <= 2:
        isolation(args[1] if len(args) == 2 else None)
    elif args == ["load"]:
        load()
    elif args == ["analytics-off"]:
        analytics_off()
    elif len(args) == 2 and args[0] == "worker-replicas":
        worker_replicas(int(args[1]))
    elif len(args) == 2 and args[0] == "cache" and args[1] in ("advance", "unready"):
        log(django_cache(args[1]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
