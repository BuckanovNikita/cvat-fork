"""Operations on the stack's own pods that the checkers need besides HTTP: kubectl, the in-memory Redis (the
refresh lock in the RQ database), Django's cache in the backend (the generation of the totals, the ready
mark), scaling a workload and reading a container's memory.

Environment: TA_KUBE_CONTEXT, TA_NAMESPACE, TA_RELEASE. Standard library only. Passwords stay in the pods:
redis-cli reads its password from the pod's own environment (REDISCLI_AUTH), never from a command line.
"""

from __future__ import annotations

import json
import os
import subprocess
import time

RELEASE = os.environ.get("TA_RELEASE", "cvat")
WORKER = f"deploy/{RELEASE}-backend-worker-team-analytics"
WORKER_SELECTOR = "app.kubernetes.io/instance={},tier=backend,component=worker-team-analytics".format(RELEASE)
CLICKHOUSE = f"statefulset/{RELEASE}-clickhouse-shard0"
CLICKHOUSE_SELECTOR = f"app.kubernetes.io/instance={RELEASE},app.kubernetes.io/name=clickhouse"
REDIS_POD = f"{RELEASE}-redis-master-0"

# The keys the app keeps (cvat/apps/team_analytics): the refresh lock in the RQ database of the in-memory
# Redis (db 0), and in Django's cache the generation of the totals and the ready mark.
LOCK_KEY = "team_analytics:refresh"
GENERATION_KEY = "team_analytics:generation"
READY_KEY = "team_analytics:ready"


def kubectl(*args: str, input: str | None = None, check: bool = True) -> str:
    command = ["kubectl", "--context", os.environ["TA_KUBE_CONTEXT"], "-n", os.environ["TA_NAMESPACE"], *args]
    out = subprocess.run(command, input=input, capture_output=True, text=True, check=False)
    if out.returncode and check:
        raise SystemExit(f"kubectl {' '.join(args)[:200]}: {out.stderr.strip()[:300]}")
    return out.stdout


def redis(*args: str, db: int = 0) -> str:
    """One redis-cli command in the release's in-memory Redis; its raw output."""
    script = 'if [ -n "$REDIS_PASSWORD" ]; then export REDISCLI_AUTH="$REDIS_PASSWORD"; fi; exec redis-cli --no-raw -n "$0" "$@"'
    return kubectl("exec", "-i", REDIS_POD, "-c", "redis", "--", "sh", "-c", script, str(db), *args).strip()


def lock_holder() -> str | None:
    """The token of whoever holds the refresh lock, or None."""
    out = redis("GET", LOCK_KEY)
    return None if out in ("", "(nil)") else out.strip('"')


def _redis_loop(body: str, *args: str) -> str:
    """A shell loop around redis-cli inside the Redis pod, so that it looks every few tens of milliseconds."""
    script = 'if [ -n "$REDIS_PASSWORD" ]; then export REDISCLI_AUTH="$REDIS_PASSWORD"; fi; ' + body
    return kubectl("exec", "-i", REDIS_POD, "-c", "redis", "--", "sh", "-c", script, *args, check=False).strip()


def wait_lock(timeout_s: int) -> bool:
    """Waits until someone holds the refresh lock, looking about every 30 ms; False after `timeout_s`."""
    out = _redis_loop(
        'end=$(( $(date +%s) + $1 )); while [ "$(date +%s)" -lt "$end" ]; do '
        '[ -n "$(redis-cli -n 0 GET "$0")" ] && { echo held; exit 0; }; sleep 0.03; done; echo free',
        LOCK_KEY, str(timeout_s))
    return out.endswith("held")


def lock_samples(seconds: int) -> tuple[int, int]:
    """How often the refresh lock was held over `seconds`, looking about every 50 ms: (held, looks)."""
    out = _redis_loop(
        'end=$(( $(date +%s) + $1 )); h=0; n=0; while [ "$(date +%s)" -lt "$end" ]; do n=$((n+1)); '
        '[ -n "$(redis-cli -n 0 GET "$0")" ] && h=$((h+1)); sleep 0.05; done; echo "$h $n"',
        LOCK_KEY, str(seconds))
    held, looks = (out.split()[-2:] + ["0", "0"])[:2]
    return int(held), int(looks)


def take_lock(token: str, length_s: int) -> bool:
    """Takes the refresh lock as a worker's step does (redis-py Lock: SET NX with an expiry), without waiting."""
    return redis("SET", LOCK_KEY, token, "NX", "PX", str(length_s * 1000)) == "OK"


def release_lock(token: str) -> bool:
    """Releases the lock only while it still holds `token`, so a worker's lock taken after ours expired stays."""
    script = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
    return redis("EVAL", script, "1", LOCK_KEY, token).endswith("1")


def backend_pod() -> str:
    return kubectl(
        "get", "pods", "-l", f"app.kubernetes.io/instance={RELEASE},tier=backend,component=server",
        "--field-selector=status.phase=Running", "-o", "jsonpath={.items[0].metadata.name}",
    ).strip()


def django_cache(action: str) -> str:
    """Changes the app's state in Django's cache through the backend's own cache settings and serialisation:
    `advance` sets a new generation of the totals, as a step that wrote does (answers cached so far are no longer
    found); `unready` removes the ready mark, so the next job creates the schema and looks for the cutover again.
    Returns what the backend printed."""
    lines = {
        # the app's own way of advancing it: a counter in the cache
        "advance": "from cvat.apps.team_analytics.reads import advance_generation\nadvance_generation(c)",
        "unready": f"c.delete({READY_KEY!r})",
        "get": "pass",
    }[action]
    script = (
        "from django.core.cache import caches\nc = caches['default']\n"
        f"{lines}\nprint('ta-cache', {action!r}, c.get({GENERATION_KEY!r}), c.get({READY_KEY!r}))\n"
    )
    out = kubectl("exec", "-i", backend_pod(), "-c", "cvat-backend", "--", "python", "manage.py", "shell", input=script)
    found = [line for line in out.splitlines() if line.startswith("ta-cache ")]
    if not found:
        raise SystemExit(f"the backend did not confirm the cache change {action}: {out[-300:]}")
    return found[-1]


def generation() -> int | None:
    """The generation of the totals as Django's cache holds it (None before the first)."""
    value = django_cache("get").split()[2]
    return None if value == "None" else int(value)


def worker_log(since_utc: str) -> list[str]:
    """The analytics worker's log lines since an RFC 3339 UTC time, from every worker pod."""
    out = kubectl("logs", "-l", WORKER_SELECTOR, "-c", "cvat-backend", f"--since-time={since_utc}",
                  "--tail=-1", "--max-log-requests=10", check=False)
    return out.splitlines()


def server_db_connections() -> dict:
    """Open connections of the CVAT server pods to Postgres (pg_stat_activity, by client address), with the
    server pods' addresses: {"server": n, "all": n}."""
    ips = kubectl("get", "pods", "-l", f"app.kubernetes.io/instance={RELEASE},tier=backend,component=server",
                  "-o", "jsonpath={.items[*].status.podIP}").split()
    query = "SELECT coalesce(host(client_addr), '-') FROM pg_stat_activity WHERE backend_type = 'client backend'"
    script = 'PGPASSWORD="${POSTGRES_PASSWORD:-$POSTGRESQL_PASSWORD}" psql -U "${POSTGRES_USER:-${POSTGRESQL_USERNAME:-postgres}}" -d "${POSTGRES_DB:-${POSTGRESQL_DATABASE:-postgres}}" -h 127.0.0.1 -tA -c "$0"'
    out = kubectl("exec", f"{RELEASE}-postgresql-0", "--", "sh", "-c", script, query)
    addrs = [line.strip() for line in out.splitlines() if line.strip()]
    return {"server": sum(1 for a in addrs if a in ips), "all": len(addrs)}


def django_settings(*names: str) -> dict:
    """The values of Django settings as the backend has them in force (the app's defaults overridden by the
    environment of the pods)."""
    script = (
        "import json\nfrom django.conf import settings\n"
        f"print('ta-settings', json.dumps({{n: getattr(settings, n, None) for n in {list(names)!r}}}))\n"
    )
    out = kubectl("exec", "-i", backend_pod(), "-c", "cvat-backend", "--", "python", "manage.py", "shell", input=script)
    found = [line for line in out.splitlines() if line.startswith("ta-settings ")]
    if not found:
        raise SystemExit(f"the backend did not print its settings: {out[-300:]}")
    return json.loads(found[-1].split(" ", 1)[1])


def scale(workload: str, replicas: int, selector: str, timeout: str = "10m") -> None:
    """Scales a Deployment or StatefulSet; to 0 waits until its pods (`selector`) are gone, otherwise until it is
    rolled out."""
    kubectl("scale", workload, f"--replicas={replicas}")
    if replicas:
        kubectl("rollout", "status", workload, f"--timeout={timeout}")
        return
    for _ in range(300):
        if not kubectl("get", "pods", "-l", selector, "-o", "name").strip():
            return
        time.sleep(1)
    raise SystemExit(f"{workload}: pods still there 5 minutes after scaling to 0")


def replicas(workload: str) -> int:
    return int(kubectl("get", workload, "-o", "jsonpath={.spec.replicas}").strip() or 0)


def first_pod(selector: str) -> str:
    return kubectl("get", "pods", "-l", selector, "--field-selector=status.phase=Running",
                   "-o", "jsonpath={.items[0].metadata.name}").strip()


def memory_mib(pod: str, container: str) -> tuple[float, float | None]:
    """The container's memory now and its peak since it started (cgroup v2), in MiB."""
    out = kubectl("exec", pod, "-c", container, "--", "sh", "-c",
                  "cat /sys/fs/cgroup/memory.current; cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo -", check=False)
    values = out.split()
    current = int(values[0]) / 2**20 if values and values[0].isdigit() else float("nan")
    peak = int(values[1]) / 2**20 if len(values) > 1 and values[1].isdigit() else None
    return current, peak
