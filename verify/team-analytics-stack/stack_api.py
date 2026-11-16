"""Talks to the test stack through its forwarded address, the way the CVAT UI does.

    stack_api.py seed               read every seeded account and role back through the API, then set the
                                    Technical accounts list to TA_TECHNICAL_ACCOUNTS through the settings API
    stack_api.py send-event MARKER  send one client event as ta-worker
    stack_api.py seed-work          create projects, tasks and jobs and send working time as annotators
    stack_api.py check-tracer SECS  wait up to SECS for the figures, then check refusals
    stack_api.py check-refresh SECS the status endpoint's refresh stamp advances twice within SECS

Team Analytics answers only administrators: every figure is read through `reader(org)`, ta-admin's session
bound to one organization (its slug) or to none (instance scope, ""). Owners and members do the work.

Environment: TA_BASE_URL, TA_SEED_PASSWORD, TA_TECHNICAL_ACCOUNTS (seed: user names, separated by commas or
spaces). Standard library only.
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

    def send(self, method: str, path: str, body: object = None) -> tuple[int, object]:
        """One request with the session's CSRF token and Origin, not retried and not failing on a refusal:
        (status, JSON body or text). A refused write is then a decision of the access rules or of the
        validation, not of CSRF."""
        return send(self.opener, method, path, body, self._csrf())


def send(
    opener: urllib.request.OpenerDirector, method: str, path: str, body: object = None, csrf: str | None = None
) -> tuple[int, object]:
    """One request, not retried: (status, JSON body or text). `csrf` None sends no CSRF header (signed out)."""
    status, answer, _ = send_full(opener, method, path, body, csrf)
    return status, answer


def send_full(
    opener: urllib.request.OpenerDirector,
    method: str,
    path: str,
    body: object = None,
    csrf: str | None = None,
    headers: dict | None = None,
) -> tuple[int, object, dict]:
    """send() with extra request headers, answering the response headers too (lower-case names)."""
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE_URL + path, data=data, method=method, headers=headers or {})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if method != "GET" and csrf is not None:
        req.add_header("Origin", BASE_URL)
        req.add_header("X-CSRFTOKEN", csrf)
    try:
        with opener.open(req, timeout=60) as resp:
            status, text, got = resp.status, resp.read().decode(), resp.headers
    except urllib.error.HTTPError as e:
        status, text, got = e.code, e.read().decode(), e.headers or {}
    got = {name.lower(): value for name, value in got.items()}
    try:
        return status, (json.loads(text) if text.strip() else None), got
    except ValueError:
        return status, text[:200], got


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
    the app's own bodies (`{"error": "bad_request", ...}`, `{"error": "unavailable"}`); for DRF's
    `{"detail": ...}` bodies `forbidden` (403) or `not_authenticated` (401); anything else as
    `unexpected <body>`, which matches no expectation. Every refusal of a caller who is not an administrator is
    DRF's plain 403 (`forbidden`)."""
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


# ---------------------------------------------------------------- reading figures: administrators only

ADMIN = "ta-admin"
_admin_sessions: dict[str, Session] = {}


def admin_session(username: str = ADMIN) -> Session:
    """The administrator's session, signed in once per process (CVAT throttles sign-ins)."""
    if username not in _admin_sessions:
        _admin_sessions[username] = Session(username)
    return _admin_sessions[username]


class Reader:
    """An administrator reading Team Analytics in one scope: an organization (its slug) or instance scope ("").
    It answers `call(path)` like a Session, with the path's `org` set to its scope; a path that names another
    organization is a mistake in the checker and stops it. `username` names the account and the scope, so two
    readers of one account are told apart in messages and keys."""

    def __init__(self, org: str, username: str = ADMIN) -> None:
        self.org = org
        self.session = admin_session(username)
        self.opener = self.session.opener
        self.username = f"{username} (org={org or '-'})"

    def bind(self, path: str) -> str:
        if not path.startswith(API):
            raise SystemExit(f"{self.username}: {path} is not a Team Analytics read")
        base, _, query = path.partition("?")
        params = urllib.parse.parse_qsl(query, keep_blank_values=True)
        named = {value for key, value in params if key == "org"}
        if named - {self.org}:
            raise SystemExit(f"{self.username} was asked to read org={sorted(named)}: {path}")
        params = [(k, v) for k, v in params if k != "org"] + [("org", self.org)]
        return base + "?" + urllib.parse.urlencode(params)

    def call(self, path: str) -> tuple[int, object]:
        return get_json(self.opener, self.bind(path))


def reader(org: str = "", username: str = ADMIN) -> Reader:
    """An administrator's reads bound to `org` (a slug) or to instance scope (""). `username` is another
    administrator (ta-group-admin, an administrator by group)."""
    return Reader(org, username)


# ---------------------------------------------------------------- the Technical accounts list

SETTINGS = API + "settings"
USER_SEARCH = API + "settings/users"


def find_user(session: Session, username: str) -> int | None:
    """The id of the user named exactly `username`, by the settings' user search (instance-wide); None if absent."""
    status, body = session.send("GET", USER_SEARCH + "?" + urllib.parse.urlencode({"search": username}))
    check(status == 200 and isinstance(body, dict) and isinstance(body.get("users"), list),
          f"{session.username}: GET {USER_SEARCH}?search={username} -> {status} {str(body)[:300]}")
    found = [u["id"] for u in body["users"] if u.get("username") == username]
    return found[0] if found else None


def technical_accounts(session: Session) -> list[dict]:
    """The Technical accounts list as GET settings answers it."""
    status, body = session.send("GET", SETTINGS)
    check(status == 200 and isinstance(body, dict) and isinstance(body.get("technical_accounts"), list),
          f"{session.username}: GET {SETTINGS} -> {status} {str(body)[:300]}")
    return body["technical_accounts"]


def save_technical_accounts(session: Session, ids: list[int]) -> list[dict]:
    """PUT settings with `ids`; the list it answers, which must hold exactly those ids."""
    status, body = session.send("PUT", SETTINGS, {"technical_accounts": ids})
    check(status == 200 and isinstance(body, dict) and isinstance(body.get("technical_accounts"), list),
          f"{session.username}: PUT {SETTINGS} {ids} -> {status} {str(body)[:300]}")
    saved = sorted(row["user_id"] for row in body["technical_accounts"])
    check(saved == sorted(ids), f"PUT {SETTINGS} {ids} answered the list {saved}")
    return body["technical_accounts"]


def seed_technical_accounts(names: list[str]) -> None:
    """The stack's Technical accounts list is exactly `names` (TA_TECHNICAL_ACCOUNTS): each resolved to its user id
    by the settings' search as the administrator, sent with PUT settings only when the list differs (so a second
    seed changes nothing, not even the answer generation), and read back with GET settings."""
    admin = admin_session()
    ids = []
    for name in names:
        user_id = find_user(admin, name)
        check(user_id is not None, f"technical account {name}: no user of that name (settings/users?search={name})")
        ids.append(user_id)
    current = technical_accounts(admin)
    if sorted(row["user_id"] for row in current) == sorted(ids):
        print(f"  Technical accounts list already {[(r['user_id'], r['user_name']) for r in current]}")
        return
    save_technical_accounts(admin, ids)
    back = technical_accounts(admin)
    got = sorted((row["user_id"], row["user_name"], row["deleted"]) for row in back)
    want = sorted((user_id, name, False) for user_id, name in zip(ids, names))
    check(got == want, f"GET {SETTINGS} after the save: {got}, expected {want}")
    print(f"  Technical accounts list set to {want} (was {[(r['user_id'], r['user_name']) for r in current]})")


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


def create_jobs(org: str, annotators: list[str], name: str = TRACER_PROJECT) -> list[dict]:
    """A project with one task in the organization, one job per annotator, each assigned."""
    owner = Session(owner_of(org))
    project = owner.request("POST", f"/api/projects?org={org}", {"name": name, "labels": [{"name": "box"}]})
    task = owner.request(
        "POST",
        f"/api/tasks?org={org}",
        {"name": f"{name}-task", "project_id": project["id"], "segment_size": 1},
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
    admin = reader("ta-org-a")
    want = expected_rows("ta-org-a")
    started = time.monotonic()
    while True:
        status, body = admin.call(OVERVIEW + "ta-org-a")
        check(status == 200, f"{admin.username} overview -> {status} {body}")
        if figures(body) == want:
            break
        if time.monotonic() - started > timeout_s:
            raise SystemExit(f"figures for ta-org-a are {figures(body)}, expected {want} (waited {timeout_s} s)")
        time.sleep(5)
    print(f"  {admin.username}: 200 {figures(body)} after {time.monotonic() - started:.0f} s")

    # only administrators read: the organization they name is the scope, none is instance scope; owners,
    # maintainers and everyone else get DRF's plain 403, with or without their organization
    cases = [
        (ADMIN, "ta-org-a", 200, want),
        (ADMIN, "ta-org-b", 200, expected_rows("ta-org-b")),
        (ADMIN, "", 200, expected_rows("ta-org-a", "ta-org-b")),
        ("ta-owner", "ta-org-a", 403, "forbidden"),
        ("ta-maintainer", "ta-org-a", 403, "forbidden"),
        ("ta-maintainer-b", "ta-org-b", 403, "forbidden"),
        ("ta-worker", "ta-org-a", 403, "forbidden"),
        ("ta-supervisor", "ta-org-a", 403, "forbidden"),
        ("ta-outsider", "ta-org-a", 403, "forbidden"),
        ("ta-maintainer-b", "ta-org-a", 403, "forbidden"),
        ("ta-maintainer", "", 403, "forbidden"),
        ("ta-owner", "", 403, "forbidden"),
    ]
    for username, org, want_status, want_body in cases:
        session = reader(org) if username == ADMIN else Session(username)
        status, body = session.call(OVERVIEW + urllib.parse.quote(org))
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
    admin = reader("")
    started, stamps = time.monotonic(), []
    while time.monotonic() - started < timeout_s:
        status, body = admin.call(API + "status?tz=UTC&org=")
        check(status == 200, f"{admin.username} status -> {status} {body}")
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
        seed_technical_accounts(os.environ.get("TA_TECHNICAL_ACCOUNTS", "").replace(",", " ").split())
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
