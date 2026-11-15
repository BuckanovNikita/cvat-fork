"""Talks to the test stack through its forwarded address, the way the CVAT UI does.

    stack_api.py seed               read every seeded account and role back through the API
    stack_api.py send-event MARKER  send one client event as ta-worker
    stack_api.py seed-work          create projects, tasks and jobs and send working time as annotators
    stack_api.py check-tracer SECS  wait up to SECS for the figures, then check refusals
    stack_api.py check-refresh SECS the status endpoint's refresh stamp advances twice within SECS

Environment: TA_BASE_URL, TA_SEED_PASSWORD. Standard library only.
"""

import http.cookiejar
import json
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

BASE_URL = os.environ["TA_BASE_URL"]
PASSWORD = os.environ["TA_SEED_PASSWORD"]
ACCOUNTS = json.loads((Path(__file__).parent / "accounts.json").read_text())
# the organizations the final run's volume annotators join: ta-org-v, or the one TA_VOLUME_ORG names for a
# second load (final_run.py reads the same variable)
VOLUME_ORGS = {"ta-org-v", os.environ.get("TA_VOLUME_ORG") or "ta-org-v"}

# Payload field the Team Analytics UI adds to existing events; it must survive the way to
# ClickHouse (run.sh check-event looks for it).
EXTRA_PAYLOAD = {"shape_type": "rectangle"}


THROTTLE_WAIT_S = 300

# Team Analytics in CVAT's own API (cvat/apps/team_analytics). A request whose answer is not cached is
# queued for the analytics worker and waits a few seconds; when the answer is not ready the API replies
# 429 with Retry-After, and the client asks again. ANALYTICS_RETRY_S bounds how long a checker keeps
# asking (the page's cvat-core retries three times, about 23 s with the 5 s wait).
API = "/api/team-analytics/"
ANALYTICS_RETRY_S = float(os.environ.get("TA_ANALYTICS_RETRY_S") or "30")


def _retry_after(error: urllib.error.HTTPError, detail: str) -> int | None:
    """The seconds a 429 asks for: its Retry-After header, else the number in DRF's detail text."""
    header = error.headers.get("Retry-After") if error.headers else None
    if header and header.strip().isdigit():
        return int(header.strip()) + 1
    found = re.search(r"available in (\d+) second", detail)
    return int(found.group(1)) + 1 if found else None


class Session:
    def __init__(self, username: str) -> None:
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.username = username
        self.request("POST", "/api/auth/login", {"username": username, "password": PASSWORD})

    def _csrf(self) -> str:
        return next((c.value for c in self.jar if c.name == "csrftoken"), "")

    def request(self, method: str, path: str, body: object = None) -> object:
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(BASE_URL + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if method != "GET":
            req.add_header("Origin", BASE_URL)
            req.add_header("X-CSRFTOKEN", self._csrf())
        # CVAT throttles requests (the login above all, after the volume's hundred sign-ins) with a 429 that
        # names the wait; the request is sent again after it, within THROTTLE_WAIT_S in all
        waited = 0
        while True:
            try:
                with self.opener.open(req, timeout=60) as resp:
                    text = resp.read().decode()
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode()[:300]
                wait = _retry_after(e, detail) if e.code == 429 else None
                if wait is None or waited + wait > THROTTLE_WAIT_S:
                    raise SystemExit(f"{self.username}: {method} {path} -> {e.code} {detail}") from None
                print(f"  {self.username}: {method} {path} throttled, again in {wait} s", file=sys.stderr, flush=True)
                time.sleep(wait)
                waited += wait
        return json.loads(text) if text.strip() else None

    def call(self, path: str) -> tuple[int, object]:
        """GET that returns (status, JSON body) instead of failing on a refusal."""
        return get_json(self.opener, path)


def raw_get(opener: urllib.request.OpenerDirector, path: str, headers: dict | None = None) -> tuple[int, object, dict]:
    """One GET: (status, JSON body or text, response headers with lower-case names). No Accept header: CVAT
    answers 406 to a bare `Accept: application/json`."""
    request = urllib.request.Request(BASE_URL + path, headers=headers or {})
    try:
        with opener.open(request, timeout=60) as resp:
            status, text, got = resp.status, resp.read().decode(), resp.headers
    except urllib.error.HTTPError as e:
        status, text, got = e.code, e.read().decode(), e.headers or {}
    got = {name.lower(): value for name, value in got.items()}
    try:
        return status, json.loads(text), got
    except ValueError:
        return status, text[:200], got


def not_ready(status: int, body: object, path: str) -> bool:
    """The analytics API's "not ready, ask again" (429, no body), as opposed to CVAT's throttling (429 with
    DRF's `detail`)."""
    return status == 429 and path.startswith(API) and body in ("", None)


def get_json(
    opener: urllib.request.OpenerDirector, path: str, headers: dict | None = None, retry_s: float | None = None
) -> tuple[int, object]:
    """GET that returns (status, JSON body) instead of failing on a refusal. An analytics answer that is not
    ready yet is asked for again after its Retry-After, for up to `retry_s` (ANALYTICS_RETRY_S) in all;
    the last answer is returned when it stays not ready."""
    budget = ANALYTICS_RETRY_S if retry_s is None else retry_s
    started = time.monotonic()
    while True:
        status, body, got = raw_get(opener, path, headers)
        if not not_ready(status, body, path):
            return status, body
        wait = float(got.get("retry-after") or 1)
        if time.monotonic() - started + wait > budget:
            return status, body
        time.sleep(wait)


def refusal(status: int, body: object) -> str | None:
    """What a Team Analytics answer refused with, by the exact form of its body: None for 200; the `error` of
    the app's own bodies (`{"error": "organization_required"}`, `{"error": "bad_request", ...}`,
    `{"error": "unavailable"}`); for DRF's `{"detail": ...}` bodies `forbidden` (403) or `not_authenticated`
    (401); anything else as `unexpected <body>`, which matches no expectation."""
    if status == 200:
        return None
    if isinstance(body, dict) and isinstance(body.get("error"), str) and (
        set(body) == {"error"} or (set(body) == {"error", "detail"} and body["error"] == "bad_request")
    ):
        return body["error"]
    if isinstance(body, dict) and set(body) == {"detail"} and status in (401, 403):
        return {401: "not_authenticated", 403: "forbidden"}[status]
    return f"unexpected {str(body)[:200]}"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"seed check failed: {message}")


def seed_check() -> None:
    for username, spec in ACCOUNTS["users"].items():
        me = Session(username).request("GET", "/api/users/self")
        groups = me["groups"]
        check(("admin" in groups) == spec["admin"], f"{username} groups {groups}")
        print(f"  {username}: groups={groups}")
    for slug, spec in ACCOUNTS["organizations"].items():
        owner = next(u for u, r in spec["members"].items() if r == "owner")
        session, found, n = Session(owner), {}, 1
        while True:  # every page: the volume's organization holds more than one
            page = session.request("GET", f"/api/memberships?org={slug}&page_size=100&page={n}")
            found.update({m["user"]["username"]: (m["role"], m["is_active"]) for m in page["results"]})
            if not page.get("next"):
                break
            n += 1
        expected = {u: (r, True) for u, r in spec["members"].items()}
        # on a rerun the final run's volume annotators are members of the volume organization too (final_run.py,
        # VOLUME_MARK and VOLUME_ORG); of no other organization, and nothing else is
        others = {u: m for u, m in found.items() if u not in expected}
        volume = {u for u, m in others.items() if slug in VOLUME_ORGS
                  and u.startswith("ta-volume-annotator-") and m == ("worker", True)}
        check({u: found.get(u) for u in expected} == expected and set(others) == volume,
              f"{slug} memberships {found}")
        print(f"  {slug}: {expected}" + (f" and {len(volume)} volume annotators" if volume else ""))
    for username in ACCOUNTS["users"]:
        if any(username in o["members"] for o in ACCOUNTS["organizations"].values()):
            continue
        if ACCOUNTS["users"][username]["admin"]:
            continue
        page = Session(username).request("GET", "/api/memberships?page_size=100")
        check(page["count"] == 0, f"{username} should be a member of nothing: {page['results']}")
        print(f"  {username}: member of nothing")


def send_event(marker: str) -> None:
    now = datetime.now(UTC).isoformat()
    payload = {"source": "team-analytics-stack-check", **EXTRA_PAYLOAD}
    body = {
        "events": [
            {
                "scope": "debug:info",
                "obj_name": marker,
                "count": 1,
                "timestamp": now,
                "payload": json.dumps(payload),
            }
        ],
        "timestamp": now,
    }
    Session("ta-worker").request("POST", "/api/events", body)
    print(f"  sent client event {marker} as ta-worker")


# ---------------------------------------------------------------- Team Analytics tracer (ticket 03)

# Working time each annotator spends in a job of the organization's project, in minutes. Totals
# are exact at one decimal of an hour, so the page shows them unrounded.
WORK = {
    "ta-org-a": {"ta-worker": 90, "ta-supervisor": 30},
    "ta-org-b": {"ta-maintainer-b": 60},
}
# Seconds between two events of an annotator; CVAT counts gaps shorter than 100 s as work.
EVENT_GAP_S = 60
TRACER_PROJECT = "ta-tracer"
OVERVIEW = API + "overview?period=week&tz=UTC&org="


def owner_of(org: str) -> str:
    return next(u for u, r in ACCOUNTS["organizations"][org]["members"].items() if r == "owner")


def tiny_png(shade: int, side: int = 8) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    width = height = side
    raw = b"".join(b"\x00" + bytes([shade, shade, shade]) * width for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def upload_images(
    session: Session, task_id: int, org: str, count: int, chunk_size: int | None = None, side: int = 8
) -> None:
    """`count` generated square images of `side` pixels as the task's data; `chunk_size` frames per chunk
    (CVAT's default when None)."""
    boundary = uuid.uuid4().hex
    fields = {"image_quality": 70, **({"chunk_size": chunk_size} if chunk_size else {})}
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        for name, value in fields.items()
    ]
    for i in range(count):
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="client_files[{i}]"; filename="frame{i}.png"\r\n'
            "Content-Type: image/png\r\n\r\n".encode()
            + tiny_png((40 + 60 * i) % 256, side)
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(f"{BASE_URL}/api/tasks/{task_id}/data?org={org}", data=b"".join(parts), method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Origin", BASE_URL)
    req.add_header("X-CSRFTOKEN", session._csrf())
    try:
        with session.opener.open(req, timeout=120):
            pass
    except urllib.error.HTTPError as e:
        raise SystemExit(f"task {task_id} data -> {e.code} {e.read().decode()[:300]}") from None


def create_jobs(org: str, annotators: list[str]) -> list[dict]:
    """A project with one task in the organization, one job per annotator, each assigned."""
    owner = Session(owner_of(org))
    project = owner.request("POST", f"/api/projects?org={org}", {"name": TRACER_PROJECT, "labels": [{"name": "box"}]})
    task = owner.request(
        "POST",
        f"/api/tasks?org={org}",
        {"name": f"{TRACER_PROJECT}-task", "project_id": project["id"], "segment_size": 1},
    )
    upload_images(owner, task["id"], org, len(annotators))
    for _ in range(120):
        jobs = owner.request("GET", f"/api/jobs?org={org}&task_id={task['id']}&page_size=100")["results"]
        if len(jobs) == len(annotators):
            break
        time.sleep(2)
    else:
        raise SystemExit(f"{org}: the task's jobs were not created within 4 minutes")
    jobs.sort(key=lambda job: job["id"])
    for job, username in zip(jobs, annotators):
        user_id = Session(username).request("GET", "/api/users/self")["id"]
        owner.request("PATCH", f"/api/jobs/{job['id']}?org={org}", {"assignee": user_id})
    return [{"job_id": j["id"], "task_id": task["id"], "project_id": project["id"]} for j in jobs]


def send_work(username: str, org: str, ids: dict, minutes: int) -> None:
    """Events in the annotator's job EVENT_GAP_S apart, ending a minute ago, sent in one batch the
    way the UI sends them; CVAT itself turns the gaps into a working-time record."""
    now = datetime.now(UTC)
    steps = minutes * 60 // EVENT_GAP_S
    start = now - timedelta(seconds=60 + steps * EVENT_GAP_S)
    events = [
        {
            "scope": "debug:info",
            "obj_name": "ta-stack-work",
            "timestamp": (start + timedelta(seconds=i * EVENT_GAP_S)).isoformat(),
            "payload": json.dumps({"source": "team-analytics-stack-work"}),
            **ids,
        }
        for i in range(steps + 1)
    ]
    Session(username).request("POST", f"/api/events?org={org}", {"events": events, "timestamp": now.isoformat()})
    print(f"  {username}: {minutes} min of work in job {ids['job_id']} of {org}")


def seed_work() -> None:
    for org, work in WORK.items():
        existing = Session(owner_of(org)).request("GET", f"/api/projects?org={org}&name={TRACER_PROJECT}")
        if existing["count"]:
            print(f"  {org}: project {TRACER_PROJECT} exists; working time already loaded")
            continue
        annotators = list(work)
        for username, ids in zip(annotators, create_jobs(org, annotators)):
            send_work(username, org, ids, work[username])


def expected_rows(*orgs: str) -> list[tuple[str, int]]:
    rows = [(user, minutes * 60_000) for org in orgs for user, minutes in WORK[org].items()]
    return sorted(rows, key=lambda row: (-row[1], row[0]))


def figures(body: object) -> list[tuple[str, int]] | None:
    """The overview's annotators and working time; None while the period is not processed (no figures yet, as
    before the first refresh of a fresh stack)."""
    rows = (body.get("by_annotator") or {}).get("rows") if isinstance(body, dict) else None
    return None if rows is None else [(row["user_name"], row["working_time_ms"]) for row in rows]


def check_tracer(timeout_s: int) -> None:
    status, _ = get_json(urllib.request.build_opener(), OVERVIEW + "ta-org-a")
    check(status == 401, f"anonymous overview -> {status}, expected 401")
    print("  anonymous: 401")

    # nothing triggers a refresh: the figures appear when the scheduled refresh job runs one
    maintainer = Session("ta-maintainer")
    want = expected_rows("ta-org-a")
    started = time.monotonic()
    while True:
        status, body = maintainer.call(OVERVIEW + "ta-org-a")
        check(status == 200, f"ta-maintainer overview -> {status} {body}")
        if figures(body) == want:
            break
        if time.monotonic() - started > timeout_s:
            raise SystemExit(f"figures for ta-org-a are {figures(body)}, expected {want} (waited {timeout_s} s)")
        time.sleep(5)
    print(f"  ta-maintainer, org=ta-org-a: 200 {figures(body)} after {time.monotonic() - started:.0f} s")

    cases = [
        ("ta-owner", "ta-org-a", 200, want),
        ("ta-maintainer-b", "ta-org-b", 200, expected_rows("ta-org-b")),
        ("ta-admin", "", 200, expected_rows("ta-org-a", "ta-org-b")),
        ("ta-worker", "ta-org-a", 403, "forbidden"),
        ("ta-supervisor", "ta-org-a", 403, "forbidden"),
        ("ta-outsider", "ta-org-a", 403, "forbidden"),
        ("ta-maintainer-b", "ta-org-a", 403, "forbidden"),
        ("ta-maintainer", "", 403, "organization_required"),
    ]
    for username, org, want_status, want_body in cases:
        status, body = Session(username).call(OVERVIEW + urllib.parse.quote(org))
        got = figures(body) if status == 200 else refusal(status, body)
        if status == 200 and not org:
            # instance scope also holds the final run's organizations (final_run.py), whose people
            # work less than these annotators, so the tracer rows lead the list
            got = got[: len(want_body)]
        check(
            (status, got) == (want_status, want_body),
            f"{username} org={org!r}: {status} {got}, expected {want_status} {want_body}",
        )
        print(f"  {username}, org={org or '-'}: {status} {got}")


def check_refresh(timeout_s: int) -> None:
    """The scheduled refresh runs: ta-admin's status carries the moment of the newest successful refresh
    (`refresh.last_success_at`), which must advance twice within `timeout_s`. Prints the stamps seen."""
    admin = Session("ta-admin")
    started, stamps = time.monotonic(), []
    while time.monotonic() - started < timeout_s:
        status, body = admin.call(API + "status?tz=UTC&org=")
        check(status == 200, f"ta-admin status -> {status} {body}")
        stamp = (body.get("refresh") or {}).get("last_success_at")
        if stamp and (not stamps or stamps[-1][1] != stamp):
            stamps.append((round(time.monotonic() - started), stamp))
            print(f"  refresh stamp {stamp} seen after {stamps[-1][0]} s", flush=True)
        if len(stamps) >= 3:
            break
        time.sleep(5)
    check(len(stamps) >= 3, f"the refresh stamp advanced {max(len(stamps) - 1, 0)} times in {timeout_s} s: {stamps}")
    moments = [datetime.fromisoformat(s) for _, s in stamps]
    gaps = [round((b - a).total_seconds()) for a, b in zip(moments, moments[1:])]
    print(f"  the scheduled refresh advanced the stamp twice; seconds between stamps {gaps}")


def main() -> None:
    if sys.argv[1:] == ["seed"]:
        seed_check()
    elif len(sys.argv) == 3 and sys.argv[1] == "send-event":
        send_event(sys.argv[2])
    elif sys.argv[1:] == ["seed-work"]:
        seed_work()
    elif len(sys.argv) == 3 and sys.argv[1] == "check-tracer":
        check_tracer(int(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] == "check-refresh":
        check_refresh(int(sys.argv[2]))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
