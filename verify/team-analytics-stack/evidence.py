"""Evidence checks of Team Analytics on a verification stack (ticket 09 of .scratch/team-analytics-admin-settings),
driven by run.sh. Each command prints what it expected and what it saw, prints `[evidence] PASS` or `FAIL`, exits
non-zero on a mismatch, and puts back what it changed in the stack's pods (a chart value it needs is set and
restored by run.sh around it).

    evidence.py redis-down          the in-memory Redis at zero: analytics reads answer 503 (not 500) within the
                                    wait; back up, the refresh schedule is there (restored with django-admin
                                    syncperiodicjobs when it was lost) and the figures come back
    evidence.py killed-worker       a read job whose worker processes are killed while it reads (ClickHouse held
                                    with SIGSTOP so that the job is mid-read; at least one rq process killed and
                                    gone from the pod) is queued again once the abandoned limit has passed: 429
                                    from the first request until at least the limit, then an answer within the
                                    limit, the read wait and a minute; the worker's log shows two executions
    evidence.py idle-generation     (refresh interval raised by run.sh) the interval in force on the server is the
                                    one asked for; the generation stands still over at least five minutes of runs
                                    with nothing due, read against the worker's log
    evidence.py liveness            a Team Analytics worker that loses one of its rq processes fails its liveness
                                    probe and is restarted; restart counts before and after; the probe's own
                                    command passes again (exit 0) within 90 s of the rollout
    evidence.py two-replicas        (two worker replicas set by run.sh) both pods ready; a burst of reads is
                                    served, by both pods; over twelve minutes at least five refresh runs that
                                    wrote, one from each pod at least, every run read from the logs with its
                                    timestamps, and none overlapping
    evidence.py snapshot FILE       the Technical accounts list and its table, before analytics is switched off
    evidence.py back-on FILE        after analytics is on again: the list and the table as in FILE, the refresh
                                    schedule back, the figures back
    evidence.py rq-start-race       (read-only) the queue's failed-job registry since the worker pod started: each
                                    id's own record and the log lines that explain it

Environment: TA_BASE_URL, TA_SEED_PASSWORD, TA_KUBE_CONTEXT, TA_NAMESPACE, TA_RELEASE. Standard library only.
"""

from __future__ import annotations

import json
import re
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run with python3 -I, which leaves it out

from acceptance import READ_LINE, analytics, client_budget_s, read_wait_s, refresh_runs, utc_now  # noqa: E402
from stack_api import admin_session, expected_rows, figures, not_ready, raw_get, reader, technical_accounts  # noqa: E402
from stack_ops import (  # noqa: E402
    CLICKHOUSE_SELECTOR,
    REDIS,
    REDIS_SELECTOR,
    RELEASE,
    WORKER,
    WORKER_SELECTOR,
    backend_pod,
    first_pod,
    generation,
    kubectl,
    psql,
    redis,
    scale,
    worker_log,
)

QUEUE = "team_analytics"
REFRESH_JOB = "team_analytics_refresh"
SCHEDULED = "rq:scheduler:scheduled_jobs"
TABLE = "team_analytics_technicalaccount"
REPLY_MARGIN_S = 2.0
YEAR_S = 31_536_000  # rq's default failure TTL, the refresh job's
READ_FAILURE_TTL_S = 60  # views.enqueue_read's failure_ttl of a read job
# two-replicas: twelve minutes of scheduled runs, one a minute. A run writes when the last refresh's data_as_of (its
# start) is at least the stack's 60 s old (core/worker.py), so a run that starts a moment less than a minute after
# the one before has nothing due: between every run and every other run writes, six to twelve in the window. At
# least five, and at least one from each pod (both pods take jobs from the one queue: six on one pod is about one
# chance in thirty-two, twelve one in two thousand; a failure prints the counts by pod to judge it by)
TWO_REPLICAS_WINDOW_S = 720
TWO_REPLICAS_MIN_WROTE = 5


class Failed(Exception):
    pass


def log(message: str) -> None:
    print(f"  {message}", flush=True)


def need(condition: bool, message: str) -> None:
    if not condition:
        raise Failed(message)


def unique_overview() -> str:
    """An overview nobody has asked for (its project filter names no project): a cache miss, a read job."""
    return analytics("overview", org="ta-org-a", period="week", project=str(900_000 + uuid.uuid4().int % 99_999))


def timed(session, path: str) -> tuple[int, float, object, dict]:
    started = time.monotonic()
    status, body, headers = raw_get(session.opener, session.bind(path))
    return status, time.monotonic() - started, body, headers


def stamp_of(admin) -> str | None:
    status, body = admin.call(analytics("status"))
    return (body.get("refresh") or {}).get("last_success_at") if status == 200 and isinstance(body, dict) else None


def wait_figures_back(after_stamp: str | None, timeout_s: int) -> float:
    """Waits until a refresh newer than `after_stamp` is recorded and ta-org-a's week shows the tracer's figures."""
    admin, in_org = reader(""), reader("ta-org-a")
    started = time.monotonic()
    want = expected_rows("ta-org-a")
    while True:
        stamp = stamp_of(admin)
        status, body = in_org.call(analytics("overview", org="ta-org-a", period="week"))
        rows = figures(body) if status == 200 else None
        if stamp and stamp != after_stamp and rows == want:
            return time.monotonic() - started
        need(time.monotonic() - started < timeout_s,
             f"figures not back within {timeout_s} s: refresh stamp {stamp} (before {after_stamp}), ta-org-a week "
             f"{status} {rows}, expected {want}")
        time.sleep(5)


def schedule_present() -> bool:
    out = redis("ZSCORE", SCHEDULED, REFRESH_JOB)
    return out not in ("", "(nil)")


def restore_schedule() -> str:
    """The refresh schedule in rq-scheduler's set; django-admin syncperiodicjobs (what the initializer and the
    backend's entrypoint run) writes CVAT's periodic jobs again when it was lost."""
    if schedule_present():
        return "present"
    out = kubectl("exec", "-i", backend_pod(), "-c", "cvat-backend", "--", "django-admin", "syncperiodicjobs")
    log(f"the refresh schedule was lost; django-admin syncperiodicjobs: {out.strip()[-300:]}")
    need(schedule_present(), f"{REFRESH_JOB} still not in {SCHEDULED} after syncperiodicjobs")
    return "restored by django-admin syncperiodicjobs"


def wait_rollouts() -> None:
    for workload in (WORKER, f"deploy/{RELEASE}-backend-worker-utils", f"deploy/{RELEASE}-backend-server"):
        kubectl("rollout", "status", workload, "--timeout=10m")


# ---------------------------------------------------------------- Redis down


def redis_down() -> str:
    admin, in_org = reader(""), reader("ta-org-a")
    before = stamp_of(admin)
    need(before is not None, "no refresh recorded before Redis was stopped")
    answers = []
    try:
        scale(REDIS, 0, REDIS_SELECTOR)
        log("in-memory Redis at 0, its pod gone")
        for round_ in range(6):
            for name, session, path in (("uncached overview", in_org, unique_overview()),
                                        ("status", admin, analytics("status"))):
                status, s, body, _ = timed(session, path)
                answers.append((round_, name, status, round(s, 2), body))
            time.sleep(3)
    finally:
        scale(REDIS, 1, REDIS_SELECTOR)
        log("in-memory Redis back at 1")
    limit = read_wait_s() + REPLY_MARGIN_S
    log("answers while Redis was down (round, request, status, seconds, body): "
        + "; ".join(f"{r} {n} {st} {s} {str(b)[:60]}" for r, n, st, s, b in answers))
    wrong = [a for a in answers if not (a[2] == 503 and a[4] == {"error": "unavailable"} and a[3] <= limit)]
    wait_rollouts()
    schedule = restore_schedule()
    back_s = wait_figures_back(before, 900)
    need(not wrong, f"expected 503 {{'error': 'unavailable'}} within {limit:.0f} s for every read while Redis was "
                    f"down; outside that: {[(n, st, s, str(b)[:80]) for _, n, st, s, b in wrong]}")
    return (f"{len(answers)} reads with Redis down: 503 unavailable within {limit:.0f} s; schedule {schedule}; "
            f"figures back {back_s:.0f} s after the workloads were rolled out")


# ---------------------------------------------------------------- a worker killed during a read


# Signals ($0) every process whose command line matches the pattern ($1), except the shell itself (its own
# command line holds the pattern too); prints how many it signalled.
SIGNAL_MATCHING = (
    'n=0; for p in /proc/[0-9]*; do i="${p#/proc/}"; [ "$i" = "$$" ] && continue; '
    'grep -qa -e "$1" "$p/cmdline" 2>/dev/null && kill -"$0" "$i" 2>/dev/null && n=$((n+1)); done; echo "$n"'
)


def clickhouse_signal(signal: str) -> int:
    """SIGSTOP or SIGCONT to ClickHouse's server process (`clickhouse-server`, or `clickhouse server`)."""
    out = kubectl("exec", first_pod(CLICKHOUSE_SELECTOR), "-c", "clickhouse", "--", "sh", "-c", SIGNAL_MATCHING,
                  signal, "clickhouse.server")
    return int(out.strip() or 0)


# Run with python3 in the worker's container: SIGKILL to every rq process of the container and to their children
# (the work horse a worker forks for the job). They are found by their command line (supervisord starts them as
# `django-admin rqworker ...`; the horse is a fork with the same command line); when none matches, by the pids rq's
# worker registry in Redis records for this pod (argv[1], comma-separated). Prints how they were found and the pids.
KILL_RQ = """
import json, os, signal, sys
def cmdline(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().replace(b"\\0", b" ").decode(errors="replace")
    except OSError:
        return ""
def parent(pid):
    try:
        with open(f"/proc/{pid}/stat") as f:
            return int(f.read().rsplit(")", 1)[1].split()[1])
    except (OSError, IndexError, ValueError):
        return None
pids = [int(d) for d in os.listdir("/proc") if d.isdigit() and int(d) != os.getpid()]
by_command = [p for p in pids if "rqworker" in cmdline(p)]
by_registry = [int(p) for p in sys.argv[1].split(",") if p and int(p) in pids]
roots, how = (by_command, "command line") if by_command else (by_registry, "rq's worker registry")
targets = set(roots)
while True:
    more = {p for p in pids if parent(p) in targets} - targets
    if not more:
        break
    targets |= more
for p in targets:
    try:
        os.kill(p, signal.SIGKILL)
    except ProcessLookupError:
        pass
print(json.dumps({"how": how, "pids": sorted(targets)}))
"""

# Run with python3 in the worker's container: which of the pids (argv[1:]) still run (absent or a zombie is gone).
STILL_RUNNING = """
import sys
alive = []
for pid in sys.argv[1:]:
    try:
        with open(f"/proc/{pid}/stat") as f:
            state = f.read().rsplit(")", 1)[1].split()[0]
    except OSError:
        continue
    if state != "Z":
        alive.append(int(pid))
print(" ".join(map(str, alive)))
"""


def registry_pids(pod: str) -> list[str]:
    """The pids rq's worker registry records for the queue's workers on `pod` (each worker's hash in Redis names its
    host, the pod, and its pid in the container)."""
    pids = []
    for line in redis("SMEMBERS", f"rq:workers:{QUEUE}").splitlines():
        key = line.split(")", 1)[-1].strip().strip('"')
        if not key.startswith("rq:worker:"):
            continue
        host, pid = (redis("HGET", key, field).strip('"') for field in ("hostname", "pid"))
        if host == pod and pid.isdigit():
            pids.append(pid)
    return pids


def kill_rq(pod: str, registered: list[str]) -> tuple[str, list[int], float]:
    """SIGKILL to the rq processes of `pod` (KILL_RQ; `registered`: the registry's pids, read beforehand so that the
    kill follows the job's start at once); how they were found, their pids and when they were killed (monotonic).
    Fails unless at least one was killed and, a few seconds on, none of them runs any more."""
    out = kubectl("exec", pod, "-c", "cvat-backend", "--", "python3", "-c", KILL_RQ, ",".join(registered))
    killed_at = time.monotonic()
    found = json.loads(out.strip().splitlines()[-1])
    how, pids = found["how"], found["pids"]
    need(bool(pids), f"no rq process of {pod} found to kill, neither by its command line ('rqworker') nor by the "
                     f"worker registry's pids {registered}: the read job was not killed")
    time.sleep(3)
    alive = kubectl("exec", pod, "-c", "cvat-backend", "--", "python3", "-c", STILL_RUNNING, *map(str, pids)).split()
    need(not alive, f"rq processes {alive} of {pod} still run 3 s after SIGKILL")
    log(f"rq processes of {pod} found by {how} (registry pids {registered}): SIGKILL to {pids}; 3 s on none of them "
        "runs (supervisord starts new ones)")
    return how, pids, killed_at


def container_logs(pod: str, since: str) -> list[str]:
    """The worker container's log lines since `since`: the container before the current one first (killing every rq
    process can fail the liveness probe and restart the container inside the window; its lines would be lost
    otherwise), then the current one. A container ends before the next starts, so the two read one after the
    other are in time order. No container before the current one is no lines."""
    lines = []
    for previous in (True, False):
        out = kubectl("logs", pod, "-c", "cvat-backend", f"--since-time={since}", "--tail=-1",
                      *(["--previous"] if previous else []), check=False)
        part = out.splitlines()
        if previous and part:
            log(f"{pod}'s container was restarted in the window: {len(part)} lines of the container before it read too")
        lines += part
    return lines


def started_reads() -> list[str]:
    out = redis("ZRANGE", f"rq:wip:{QUEUE}", "0", "-1")
    return [line.split(")", 1)[-1].strip().strip('"') for line in out.splitlines() if "team-analytics-read-" in line]


def killed_worker() -> str:
    from stack_ops import django_settings

    timeout_s = int(django_settings("TEAM_ANALYTICS_READ_JOB_TIMEOUT_S")["TEAM_ANALYTICS_READ_JOB_TIMEOUT_S"])
    limit_s = 2 * timeout_s + 120  # views._abandoned
    in_org = reader("ta-org-a")
    path = unique_overview()
    since = utc_now()
    pod = first_pod(WORKER_SELECTOR)
    job = None
    registered = registry_pids(pod)
    try:
        stopped = clickhouse_signal("STOP")  # the read job's statements wait on ClickHouse: the job is mid-read
        log(f"ClickHouse's server process stopped (SIGSTOP to {stopped} processes)")
        need(stopped > 0, "no ClickHouse server process found to stop")
        queued_at = time.monotonic()  # the first request queues the read: the abandoned limit counts from here
        first = timed(in_org, path)
        log(f"first request: {first[0]} after {first[1]:.1f} s")
        for _ in range(10):
            reads = started_reads()
            if reads:
                job = reads[0]
                break
            time.sleep(0.5)
        need(job is not None, f"no read job started while ClickHouse was held (rq:wip:{QUEUE} empty)")
        log(f"read job {job} started: {redis('HGET', f'rq:job:{job}', 'status')}")
        how, killed, killed_at = kill_rq(pod, registered)
    finally:
        log(f"ClickHouse's server process continued (SIGCONT to {clickhouse_signal('CONT')} processes)")
    timeline = []
    while True:
        status, s, body, headers = timed(in_org, path)
        state = redis("HGET", f"rq:job:{job}", "status")
        timeline.append((round(time.monotonic() - killed_at), status, state))
        if status != 429 or not not_ready(status, body, path):
            break
        need(time.monotonic() - killed_at < limit_s + 120,
             f"still 429 {time.monotonic() - killed_at:.0f} s after the kill; the abandoned limit is {limit_s} s")
        time.sleep(float(headers.get("retry-after") or 3))
    answered_at = time.monotonic()  # the moment the answer arrived, before anything else is read
    after_s, since_queued = answered_at - killed_at, answered_at - queued_at
    log("after the kill (seconds, status, the job's record): " + ", ".join(f"{t} {st} {j}" for t, st, j in timeline))
    lines = [line for line in container_logs(pod, since) if job in line]
    log(f"the worker's log lines naming {job}:")
    for line in lines[-30:]:
        print(f"    {line}", flush=True)
    others = [t for t in timeline[:-1] if t[1] != 429]
    # the job ran twice: the run that was killed, and the run after it was queued again
    runs = [line for line in lines if "Preparing for execution" in line]
    need(status == 200 and not others, f"expected 429 until the job was queued again, then 200; saw {timeline}")
    need(len(runs) >= 2, f"the worker's log shows {len(runs)} executions of {job}, expected two (killed, then queued again)")
    # rq's own clean-up of the started registry runs only at a worker's start (before the job's timeout has passed)
    # and then every ten minutes, so the read is queued again by the API's abandoned rule, not earlier
    need(since_queued >= limit_s - 15,
         f"the answer came {since_queued:.0f} s after the read was queued, before the abandoned limit {limit_s} s "
         f"(2 x {timeout_s} + 120): something other than the abandoned rule queued it again")
    need(after_s <= limit_s + read_wait_s() + 60,
         f"the answer came {after_s:.0f} s after the kill, beyond the abandoned limit {limit_s} s (2 x "
         f"{timeout_s} + 120) and the wait")
    return (f"read job {job} killed mid-read ({len(killed)} rq processes, found by {how}): 429 for {after_s:.0f} s ({len(timeline) - 1} answers), "
            f"then 200, {since_queued:.0f} s after it was first queued; abandoned limit {limit_s} s; {len(runs)} executions")


# ---------------------------------------------------------------- the generation when nothing is due


def idle_generation(interval_s: int) -> str:
    """A run is due once every `interval_s`; between two due runs the minute's runs have nothing to do. After a run
    that wrote, the next five and a half minutes hold only runs with nothing due (the interval is at least 600 s):
    the generation must stand still and the worker's log must show those runs."""
    from stack_ops import django_settings

    in_force = int(django_settings("TEAM_ANALYTICS_REFRESH_INTERVAL_S")["TEAM_ANALYTICS_REFRESH_INTERVAL_S"])
    need(in_force == interval_s and in_force >= 600,
         f"the refresh interval in force on the server is {in_force} s; expected {interval_s} (run.sh sets it), at least 600")
    status, body = reader("").call(analytics("status"))
    need(status == 200 and (body.get("history") or {}).get("complete"), f"history not complete: {status} {body}")
    since = utc_now()
    started = time.monotonic()
    while True:  # the window starts right after a run that wrote
        runs = refresh_runs(worker_log(since))
        if any(r["wrote"] for r in runs):
            break
        need(time.monotonic() - started < interval_s + 180, f"no run that wrote within {interval_s + 180} s")
        time.sleep(5)
    time.sleep(5)
    window_since, first = utc_now(), generation()
    seen = [(0, first)]
    window = 360
    t0 = time.monotonic()
    while time.monotonic() - t0 < window:
        time.sleep(15)
        seen.append((round(time.monotonic() - t0), generation()))
    runs = refresh_runs(worker_log(window_since))
    log(f"generation over {window} s: {seen}")
    log("refresh runs in the window (end, wrote): "
        + ", ".join(f"{time.strftime('%H:%M:%S', time.gmtime(r['end']))} {r['wrote']}" for r in runs))
    need(all(g == first for _, g in seen), f"the generation moved from {first} with nothing due: {seen}")
    need(len(runs) >= 5 and not any(r["wrote"] for r in runs),
         f"expected at least 5 runs with nothing due in {window} s, saw {[(r['end'], r['wrote']) for r in runs]}")
    return f"generation {first} unchanged over {window} s and {len(runs)} runs with nothing due"


# ---------------------------------------------------------------- liveness


def restarts(pod: str) -> int:
    return int(kubectl("get", "pod", pod, "-o", "jsonpath={.status.containerStatuses[0].restartCount}").strip() or 0)


def liveness() -> str:
    pod = first_pod(WORKER_SELECTOR)
    probe = json.loads(kubectl("get", "pod", pod, "-o", "jsonpath={.spec.containers[0].livenessProbe}") or "{}")
    period, threshold = int(probe.get("periodSeconds", 10)), int(probe.get("failureThreshold", 3))
    before = restarts(pod)
    sock = "unix:///tmp/supervisord/supervisor.sock"
    listed = kubectl("exec", pod, "-c", "cvat-backend", "--", "supervisorctl", "-s", sock, "status", check=False)
    names = [line.split()[0] for line in listed.splitlines() if line.startswith("rqworker")]
    need(names, f"no rqworker program in supervisorctl status of {pod}: {listed[:300]}")
    log(f"{pod}: probe {probe.get('exec', {}).get('command')}, every {period} s, {threshold} failures; restarts "
        f"{before}; rq processes {names}")
    # a stopped program unregisters its rq worker (a warm shutdown) and is not started again
    kubectl("exec", pod, "-c", "cvat-backend", "--", "supervisorctl", "-s", sock, "stop", names[0])
    stopped = time.monotonic()
    log(f"stopped {names[0]}; waiting up to {period * (threshold + 2) + 120} s for the restart")
    while restarts(pod) == before:
        need(time.monotonic() - stopped < period * (threshold + 2) + 120,
             f"{pod} not restarted {time.monotonic() - stopped:.0f} s after {names[0]} stopped (restarts {before})")
        time.sleep(10)
    after_s = time.monotonic() - stopped
    events = kubectl("get", "events", "--field-selector", f"involvedObject.name={pod},reason=Unhealthy",
                     "-o", "custom-columns=AT:.lastTimestamp,MSG:.message", "--no-headers", check=False)
    log(f"Unhealthy events of {pod}:\n{events.strip()}")
    kubectl("rollout", "status", WORKER, "--timeout=10m")
    procs = kubectl("get", "pod", pod, "-o", 'jsonpath={.spec.containers[0].env[?(@.name=="NUMPROCS")].value}').strip()
    passed, last = False, ""
    for _ in range(30):
        try:  # kubectl() stops on a non-zero exit, which is workerprobe's failure; passing is exit 0
            kubectl("exec", pod, "-c", "cvat-backend", "--", "django-admin", "workerprobe", QUEUE,
                    "--expected-num-workers", procs)
            passed = True
            break
        except SystemExit as error:
            last = str(error)
        time.sleep(3)
    need(passed, f"after the restart the liveness probe still fails 90 s on: {last[:300]}")
    return (f"{pod}: one of {len(names)} rq processes stopped, liveness failed, container restarted after "
            f"{after_s:.0f} s; restarts {before} -> {restarts(pod)}; the probe passes again")


# ---------------------------------------------------------------- two replicas


_PREFIXED = re.compile(r"^\[pod/([^/\]]+)/[^\]]*\] (.*)$")


def logs_by_pod(since: str) -> dict[str, list[str]]:
    out = kubectl("logs", "-l", WORKER_SELECTOR, "-c", "cvat-backend", f"--since-time={since}", "--tail=-1",
                  "--max-log-requests=10", "--prefix", check=False)
    pods: dict[str, list[str]] = {}
    for line in out.splitlines():
        m = _PREFIXED.match(line)
        if m:
            pods.setdefault(m.group(1), []).append(m.group(2))
    return pods


def two_replicas() -> str:
    ready = kubectl("get", "pods", "-l", WORKER_SELECTOR, "-o",
                    "jsonpath={range .items[*]}{.metadata.name} {.status.containerStatuses[0].ready}{'\\n'}{end}")
    pods = [line.split() for line in ready.splitlines() if line.strip()]
    log(f"worker pods (name, ready): {pods}")
    need(len(pods) == 2 and all(p[1] == "true" for p in pods), f"expected 2 ready worker pods, saw {pods}")
    since = utc_now()
    # a burst of reads nobody asked for before, at once
    in_org = reader("ta-org-a")
    results: list = []

    def ask(path: str) -> None:
        started = time.monotonic()
        while True:
            status, body, headers = raw_get(in_org.opener, in_org.bind(path))
            if not not_ready(status, body, path) or time.monotonic() - started > client_budget_s():
                break
            time.sleep(float(headers.get("retry-after") or 1))
        results.append((status, round(time.monotonic() - started, 1)))

    threads = [threading.Thread(target=ask, args=(unique_overview(),), daemon=True) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(client_budget_s() + 30)
    log(f"burst of 12 uncached overviews (status, seconds): {sorted(results)}")
    time.sleep(TWO_REPLICAS_WINDOW_S)  # scheduled runs (one a minute) on two replicas
    by_pod = logs_by_pod(since)
    spans, reads_by_pod, wrote_by_pod, problems = [], {}, {}, []
    for pod, lines in by_pod.items():
        reads_by_pod[pod] = sum(1 for line in lines if READ_LINE.search(line))
        runs, started, unparsed = run_spans(lines)
        wrote_by_pod[pod] = sum(1 for r in runs if r[2])
        log(f"{pod}: {reads_by_pod[pod]} read jobs, {started} refresh runs started, {len(runs)} read with their start "
            f"and end, {wrote_by_pod[pod]} wrote; {unparsed} without a readable timestamp")
        # every run read whole: a run may still be going when the logs are read (one per pod), nothing else is lost
        if unparsed or len(runs) < started - 1:
            problems.append(f"{pod}: {started} runs started, {len(runs)} read with start and end, {unparsed} timestamps "
                            "not parsed")
        spans += [(begin, end, pod) for begin, end, wrote in runs if wrote]
    spans.sort()
    overlaps = [(a, b) for a, b in zip(spans, spans[1:]) if b[0] < a[1]]
    need(len(results) == 12 and all(st == 200 for st, _ in results),
         f"expected 12 answers 200 within the client's budget {client_budget_s():.0f} s, saw {sorted(results)}")
    # something to judge: logs of both pods, both serving reads, and refresh runs that wrote read with their start
    # and end, from each pod, enough of them over the window
    need(len(by_pod) == 2 and all(n > 0 for n in reads_by_pod.values()),
         f"expected logs and read jobs of both pods, saw read jobs by pod {reads_by_pod}")
    need(not problems, f"refresh runs not read whole from the logs: {problems}")
    need(not overlaps, f"refresh runs that wrote overlapped across the replicas: {overlaps}")
    need(len(spans) >= TWO_REPLICAS_MIN_WROTE,
         f"expected at least {TWO_REPLICAS_MIN_WROTE} refresh runs that wrote in {TWO_REPLICAS_WINDOW_S} s; saw "
         f"{len(spans)}, by pod {wrote_by_pod}")
    # everything else held: both pods ready and serving reads, every run read, enough runs, none overlapping
    need(all(n > 0 for n in wrote_by_pod.values()),
         f"every one of the {len(spans)} refresh runs that wrote ran on one pod ({wrote_by_pod}), while both pods were "
         f"ready, both served reads ({reads_by_pod}) and no runs overlapped. The step's own odds allow this (about one "
         "chance in thirty-two when only every second run writes): run check-evidence two-replicas again before "
         "looking for a defect; the same outcome twice is one to look into")
    return (f"2 ready replicas; 12 uncached reads 200; {len(spans)} refresh runs that wrote, none overlapping; read "
            f"jobs by pod {[(p, sum(1 for line in ls if READ_LINE.search(line))) for p, ls in by_pod.items()]}")


def run_spans(lines: list[str]) -> tuple[list[tuple[float, float, bool]], int, int]:
    """The refresh runs of one pod's log, read as acceptance.refresh_runs reads them: the runs with a start and an
    end, (start, end, wrote); how many started; how many start or end lines had no timestamp that could be read."""
    spans, current, started, unparsed = [], None, 0, 0
    for line in lines:
        if "jobs.refresh_totals()" in line:
            started += 1
            current = {"begin": _log_time(line), "wrote": False}
            unparsed += current["begin"] is None
        elif current is not None and ("core.refresh: refreshed" in line or "core.history: history:" in line):
            current["wrote"] = True
        elif current is not None and "Job OK (team_analytics_refresh)" in line:
            end = _log_time(line)
            unparsed += end is None
            if current["begin"] is not None and end is not None:
                spans.append((current["begin"], end, current["wrote"]))
            current = None
    return spans, started, unparsed


def _log_time(line: str) -> float | None:
    m = re.match(r"^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d{3})\]", line)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp() + int(m.group(2)) / 1000


# ---------------------------------------------------------------- off, then on again


def table_rows() -> list[str]:
    return sorted(line.strip() for line in psql(f"SELECT user_id, user_name FROM {TABLE} ORDER BY user_id")
                  .splitlines() if line.strip())


def snapshot(file: str) -> str:
    state = {"list": technical_accounts(admin_session()), "table": table_rows(), "stamp": stamp_of(reader(""))}
    Path(file).write_text(json.dumps(state))
    return f"list {state['list']}; table rows {state['table']}"


def back_on(file: str) -> str:
    state = json.loads(Path(file).read_text())
    rows, listed = table_rows(), technical_accounts(admin_session())
    log(f"after on again: table {rows} (before {state['table']}); list {listed}")
    need(rows == state["table"], f"the table {TABLE} is {rows}, before off it was {state['table']}")
    need(listed == state["list"], f"the list is {listed}, before off it was {state['list']}")
    for _ in range(60):
        if schedule_present():
            break
        time.sleep(5)
    need(schedule_present(), f"{REFRESH_JOB} not back in {SCHEDULED} five minutes after analytics was on again")
    back_s = wait_figures_back(state["stamp"], 900)
    return f"table and list as before off ({len(rows)} rows); the schedule back; figures back after {back_s:.0f} s"


# ---------------------------------------------------------------- rq's start race (read-only)


def rq_start_race() -> str:
    pod = first_pod(WORKER_SELECTOR)
    started = kubectl("get", "pod", pod, "-o", "jsonpath={.status.containerStatuses[0].state.running.startedAt}").strip()
    since = datetime.fromisoformat(started.replace("Z", "+00:00")).timestamp()
    failed = redis("ZRANGE", f"rq:failed:{QUEUE}", "0", "-1", "WITHSCORES").splitlines()
    values = [line.split(")", 1)[-1].strip().strip('"') for line in failed if line.strip()]
    entries = list(zip(values[::2], (float(v) for v in values[1::2])))
    lines = kubectl("logs", pod, "-c", "cvat-backend", f"--since-time={started}", "--tail=-1", check=False).splitlines()
    log(f"worker pod {pod} started {started}; failed registry of {QUEUE}: {entries}")
    found = []
    unexplained = []
    for job, score in entries:
        added = score - (YEAR_S if score - time.time() > 10 * READ_FAILURE_TTL_S else READ_FAILURE_TTL_S)
        if added < since - 1:
            log(f"{job}: added {datetime.fromtimestamp(added, UTC).isoformat()}, before this pod started: not judged")
            continue
        record = redis("HGET", f"rq:job:{job}", "status")
        exc = redis("HEXISTS", f"rq:job:{job}", "exc_info")
        failing = [line for line in lines if f"Handling failed execution of job {job}" in line]
        preparing = [line for line in lines if "Preparing for execution" in line and job in line]
        cleaning = [line for line in lines if "Cleaning registries for queue" in line]
        log(f"{job}: added {datetime.fromtimestamp(added, UTC).isoformat()}; its record {record}, exc_info {exc}")
        for line in (cleaning[:3] + failing[:3] + preparing[:3]):
            print(f"    {line}", flush=True)
        if failing and preparing:
            found.append(job)
        else:
            unexplained.append(job)
    intermediate = redis("LRANGE", f"rq:queue:{QUEUE}:intermediate", "0", "-1")
    log(f"intermediate list now: {intermediate or '(empty)'}")
    need(not unexplained, f"failed entries since the pod started without rq's start-race lines (a process cleaning "
                          f"registries failing a job another process prepares): {unexplained}")
    if not found:
        return f"no failed entry since {pod} started: the race did not occur on this start (nothing to explain)"
    return (f"{len(found)} failed entries since the start, each failed by clean_intermediate_queue while another "
            f"process prepared it (rq 1.16.0): {found}")


def main() -> None:
    args = sys.argv[1:]
    steps = {"redis-down": redis_down, "killed-worker": killed_worker, "liveness": liveness,
             "two-replicas": two_replicas, "rq-start-race": rq_start_race}
    if len(args) == 1 and args[0] in steps:
        name, run = args[0], steps[args[0]]
    elif len(args) == 2 and args[0] == "idle-generation":
        name, run = args[0], lambda: idle_generation(int(args[1]))
    elif len(args) == 2 and args[0] in ("snapshot", "back-on"):
        name, run = args[0], (lambda: (snapshot if args[0] == "snapshot" else back_on)(args[1]))
    else:
        raise SystemExit(__doc__)
    try:
        detail = run()
    except Failed as error:
        print(f"[evidence] FAIL {name}: {error}", flush=True)
        raise SystemExit(1) from None
    print(f"[evidence] PASS {name}: {detail}", flush=True)


if __name__ == "__main__":
    main()
