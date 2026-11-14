"""The service's Ingress route and four access cases against the stack's real CVAT (ticket 11).
Driven by run.sh; each command judges its own case and exits non-zero on a failure.

    access_cases.py check-ingress HOST   status through the Ingress at https://HOST (the ingress
                                         controller on 127.0.0.1:443): answered with a session,
                                         refused as signed out without one
    access_cases.py removed-member       a maintainer removed from ta-org-r is refused once the
                                         service's identity cache has expired
    access_cases.py group-admin          an administrator by group who is not a superuser reads
                                         instance scope and a named organization
    access_cases.py personal-workspace SECS
                                         job work in ta-solo's personal workspace appears under
                                         instance scope and under no organization (waits up to SECS
                                         for the scheduled refresh)
    access_cases.py header-credentials   credentials sent as an Authorization header (Basic, and a
                                         personal access token as Bearer) get the decisions a
                                         session cookie gets

Accounts: access_accounts.json (seed_access.py) and accounts.json. Environment: TA_BASE_URL,
TA_SEED_PASSWORD. Standard library only.
"""

from __future__ import annotations

import base64
import http.client
import json
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run with python3 -I, which leaves it out

from stack_api import BASE_URL, PASSWORD, Session, get_json, send_work, upload_images

HERE = Path(__file__).resolve().parent
API = "/team-analytics-api/v1/"
ACCESS_ACCOUNTS = json.loads((HERE / "access_accounts.json").read_text())
ADMIN_ONLY_HISTORY = {"first_day", "days_ready", "days_total"}  # status keys only administrators get (ticket 15)

# The service reuses CVAT's answers per caller for ANSWER_TTL (team_analytics/access.py), a constant
# with no configuration: the removed-member case waits it out. Read from the source so that a change
# there changes the wait.
ACCESS_SOURCE = HERE.parents[1] / "team-analytics/service/team_analytics/access.py"
_TTL = re.search(r"^ANSWER_TTL = timedelta\((minutes|seconds)=(\d+)\)$", ACCESS_SOURCE.read_text(), re.M)
if _TTL is None:
    raise SystemExit("ANSWER_TTL not found in team_analytics/access.py; the removed-member wait is unknown")
CACHE_TTL_S = int(_TTL.group(2)) * (60 if _TTL.group(1) == "minutes" else 1)
CACHE_MARGIN_S = 5

REMOVED_ORG = "ta-org-r"
LEAVER = "ta-leaver"
GROUP_ADMIN = "ta-group-admin"
SOLO = "ta-solo"
SOLO_MINUTES = 20  # less than any tracer annotator's, so check-tracer's leading instance rows stay theirs
SOLO_PROJECT = "ta-personal"


def log(message: str) -> None:
    print(f"  {message}", flush=True)


def passed(case: str, detail: str) -> None:
    print(f"[access] PASS {case}: {detail}", flush=True)


def fail(case: str, detail: str) -> None:
    raise SystemExit(f"[access] FAIL {case}: {detail}")


def query(path: str, **params: str) -> str:
    return API + path + "?" + urllib.parse.urlencode({"tz": "UTC", **params})


def endpoint_query(endpoint: str, org: str) -> str:
    """`status` as the existing matrix asks it (no period), `overview` for the week."""
    return query(endpoint, org=org, **({"period": "week"} if endpoint == "overview" else {}))


def overview_names(body: object) -> list[str] | None:
    """The annotators an overview lists; None when the week is not processed (no figures)."""
    if not isinstance(body, dict) or not body.get("processed", True):
        return None
    rows = (body.get("by_annotator") or {}).get("rows")
    return [row["user_name"] for row in rows] if isinstance(rows, list) else None


def error_of(status: int, body: object) -> str | None:
    return body.get("error") if status != 200 and isinstance(body, dict) else None


# ---------------------------------------------------------------- Ingress


class _ControllerConnection(http.client.HTTPSConnection):
    """HTTPS to the ingress controller on the host's 443 for a name the host does not resolve: the
    TCP connection goes to 127.0.0.1, the TLS name (SNI and verification) and Host stay the name."""

    def connect(self) -> None:
        sock = socket.create_connection(("127.0.0.1", self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def ingress_get(host: str, path: str, cookie: str | None) -> tuple[int, object]:
    # verification on, with the default trust store (the local CA is in the host bundle, k8s-infra)
    connection = _ControllerConnection(host, 443, timeout=30, context=ssl.create_default_context())
    try:
        connection.request("GET", path, headers={"Cookie": cookie} if cookie else {})
        response = connection.getresponse()
        status, text = response.status, response.read().decode(errors="replace")
    finally:
        connection.close()
    try:
        return status, json.loads(text)
    except ValueError:
        return status, text[:200]


def check_ingress(host: str) -> None:
    case = "ingress"
    session = Session("ta-maintainer")  # logged in through the proxy; the cookie's value is what CVAT reads
    cookie = "; ".join(f"{c.name}={c.value}" for c in session.jar)
    path = query("status", org="ta-org-a")
    # the controller answers 404 or 503 for the host until it has synced the new Ingress
    deadline = time.monotonic() + 120
    while True:
        status, body = ingress_get(host, path, cookie)
        if status not in (404, 502, 503) or time.monotonic() > deadline:
            break
        time.sleep(3)
    if status != 200 or not isinstance(body, dict) or not {"history", "refresh", "cutover"} <= set(body):
        fail(case, f"with a session: {status} {str(body)[:300]}, expected 200 with history, refresh and cutover")
    log(f"https://{host}{API}status as ta-maintainer, org=ta-org-a: 200 {sorted(body)}")
    status, body = ingress_get(host, path, None)
    if (status, error_of(status, body)) != (401, "not_authenticated"):
        fail(case, f"without a session: {status} {str(body)[:300]}, expected 401 not_authenticated")
    log(f"https://{host}{API}status without a session: 401 not_authenticated")
    passed(case, f"status through the Ingress at {host}: 200 with a session, 401 not_authenticated without")


# ---------------------------------------------------------------- a removed member


def removed_member() -> None:
    case = "removed-member"
    owner = Session(next(u for u, r in ACCESS_ACCOUNTS["organizations"][REMOVED_ORG]["members"].items() if r == "owner"))
    leaver = Session(LEAVER)  # one session throughout: the cache key is the credentials
    path = query("status", org=REMOVED_ORG)
    status, body = leaver.call(path)
    if status != 200:
        fail(case, f"{LEAVER} before the removal: {status} {body}, expected 200 (run.sh seed-access first)")
    asked_at = time.monotonic()  # every answer of that read was fetched before this moment
    log(f"{LEAVER}, org={REMOVED_ORG}, a maintainer: 200")

    rows = owner.request("GET", f"/api/memberships?org={REMOVED_ORG}&user={LEAVER}&page_size=100")["results"]
    if len(rows) != 1:
        fail(case, f"{REMOVED_ORG} has {len(rows)} memberships of {LEAVER}, expected 1")
    owner.request("DELETE", f"/api/memberships/{rows[0]['id']}?org={REMOVED_ORG}")
    left = owner.request("GET", f"/api/memberships?org={REMOVED_ORG}&user={LEAVER}&page_size=100")["results"]
    if left:
        fail(case, f"the membership is still listed after the owner deleted it: {left}")
    log(f"{LEAVER} removed from {REMOVED_ORG} by its owner through CVAT's API")
    # not judged: within the minute the cached answers may still let the same session in
    status, body = leaver.call(path)
    log(f"right after the removal (cache not expired, not judged): {status} {error_of(status, body) or ''}")

    wait = asked_at + CACHE_TTL_S + CACHE_MARGIN_S - time.monotonic()
    log(f"waiting {max(wait, 0):.0f} s for the identity cache ({CACHE_TTL_S} s, team_analytics/access.py ANSWER_TTL)")
    time.sleep(max(wait, 0))
    for org, want in ((REMOVED_ORG, "forbidden"), ("", "forbidden")):
        for endpoint in ("status", "overview"):
            status, body = leaver.call(endpoint_query(endpoint, org))
            if (status, error_of(status, body)) != (403, want):
                fail(case, f"{LEAVER}, org={org or '-'} {endpoint} after the cache expired: {status} {body}, expected 403 {want}")
            log(f"{LEAVER}, org={org or '-'} {endpoint}: 403 {want}")
    passed(case, f"{LEAVER} removed from {REMOVED_ORG}: 403 forbidden with and without the organization after {CACHE_TTL_S} s")


# ---------------------------------------------------------------- an administrator by group


COMPARE_ATTEMPTS = 4


def same_reads(first, second):
    """Two reads meant to be equal, taken one after the other. Other work on the shared stack can
    land between them (a refresh, another ticket's events), so a pair that differs is read again,
    up to COMPARE_ATTEMPTS times, before the difference is judged. A rule that answers differently
    differs on every attempt."""
    for attempt in range(COMPARE_ATTEMPTS):
        a, b = first(), second()
        if a == b:
            return a, b
        if attempt + 1 < COMPARE_ATTEMPTS:
            log(f"reads differ (attempt {attempt + 1}), reading again: {str(a)[:120]} / {str(b)[:120]}")
            time.sleep(3)
    return a, b


def annotators(session: Session, org: str) -> list[str]:
    status, body = session.call(endpoint_query("overview", org))
    names = overview_names(body) if status == 200 else None
    if names is None:
        raise SystemExit(f"[access] FAIL group-admin: {session.username}, org={org or '-'} overview: {status} "
                         f"{str(body)[:300]}, expected 200 with the processed week's annotators")
    return names


def group_admin() -> None:
    case = "group-admin"
    admin = Session(GROUP_ADMIN)
    me = admin.request("GET", "/api/users/self")
    if "admin" not in me["groups"] or me.get("is_superuser") is not False or me.get("is_staff") is not False:
        fail(case, f"{GROUP_ADMIN} is groups={me['groups']} is_superuser={me.get('is_superuser')} "
                   f"is_staff={me.get('is_staff')}, expected the admin group without either flag")
    log(f"{GROUP_ADMIN}: groups={me['groups']}, is_superuser=False, is_staff=False")
    for org in ("", "ta-org-a"):
        status, body = admin.call(query("status", org=org))
        history = body.get("history") if isinstance(body, dict) else None
        if status != 200 or not isinstance(history, dict) or not ADMIN_ONLY_HISTORY <= set(history):
            fail(case, f"status org={org or '-'}: {status} {str(body)[:300]}, expected 200 with the administrator's history")
        log(f"{GROUP_ADMIN}, org={org or '-'} status: 200 with {sorted(ADMIN_ONLY_HISTORY)}")
    named, owners_view = same_reads(lambda: annotators(admin, "ta-org-a"), lambda: annotators(Session("ta-owner"), "ta-org-a"))
    if not named or named != owners_view:
        fail(case, f"overview org=ta-org-a: {named}, expected the owner's view {owners_view}")
    instance, superusers_view = same_reads(lambda: annotators(admin, ""), lambda: annotators(Session("ta-admin"), ""))
    if instance != superusers_view or instance == named:
        fail(case, f"overview org=-: {instance}, expected the superuser's instance scope {superusers_view}")
    log(f"{GROUP_ADMIN}, org=ta-org-a overview: {named}, as its owner sees it")
    log(f"{GROUP_ADMIN}, org=- overview: {len(instance)} annotators, as the superuser ta-admin sees instance scope")
    passed(case, f"{GROUP_ADMIN} (admin group, not a superuser) reads instance scope and ta-org-a")


# ---------------------------------------------------------------- a personal workspace


def personal_job(solo: Session) -> dict:
    """ta-solo's project, task and job in the personal workspace (no organization), made once."""
    existing = solo.request("GET", f"/api/projects?org=&name={SOLO_PROJECT}")
    if existing["count"]:
        project = existing["results"][0]
        jobs = solo.request("GET", f"/api/jobs?org=&project_id={project['id']}&page_size=100")["results"]
        if len(jobs) != 1:
            raise SystemExit(f"[access] FAIL personal-workspace: {SOLO_PROJECT} has {len(jobs)} jobs, expected 1")
        log(f"{SOLO_PROJECT} exists in {SOLO}'s personal workspace; its work is already loaded")
        return {"job_id": jobs[0]["id"], "task_id": jobs[0]["task_id"], "project_id": project["id"], "new": False}
    project = solo.request("POST", "/api/projects?org=", {"name": SOLO_PROJECT, "labels": [{"name": "box"}]})
    if project.get("organization") is not None:
        raise SystemExit(f"[access] FAIL personal-workspace: the project went to organization {project['organization']}")
    task = solo.request("POST", "/api/tasks?org=", {"name": f"{SOLO_PROJECT}-task", "project_id": project["id"]})
    upload_images(solo, task["id"], "", 1)
    for _ in range(120):
        jobs = solo.request("GET", f"/api/jobs?org=&task_id={task['id']}&page_size=100")["results"]
        if jobs:
            break
        time.sleep(2)
    else:
        raise SystemExit("[access] FAIL personal-workspace: the task's job was not created within 4 minutes")
    solo.request("PATCH", f"/api/jobs/{jobs[0]['id']}?org=", {"assignee": solo.request("GET", "/api/users/self")["id"]})
    return {"job_id": jobs[0]["id"], "task_id": task["id"], "project_id": project["id"], "new": True}


def details(session: Session, org: str, **params: str) -> dict | None:
    """The details table, or None while the week is not fully processed."""
    status, body = session.call(query("details", org=org, period="week", **params))
    if status != 200:
        raise SystemExit(f"[access] FAIL personal-workspace: {session.username}, org={org or '-'} details {params}: {status} {body}")
    return body if body.get("processed") else None


def personal_workspace(timeout_s: int) -> None:
    case = "personal-workspace"
    solo = Session(SOLO)
    memberships = solo.request("GET", "/api/memberships?page_size=100")
    if memberships["count"]:
        fail(case, f"{SOLO} should be a member of nothing: {memberships['results']}")
    ids = personal_job(solo)
    if ids.pop("new"):
        send_work(SOLO, "", ids, SOLO_MINUTES)
    want_ms = SOLO_MINUTES * 60_000

    admin = Session("ta-admin")
    started = time.monotonic()
    while True:
        body = details(admin, "", search=SOLO)
        rows = [(r["user_name"], r["working_time_ms"]) for r in body["rows"]] if body else None
        if rows == [(SOLO, want_ms)]:
            break
        if time.monotonic() - started > timeout_s:
            fail(case, f"instance scope details search={SOLO}: {rows}, expected {[(SOLO, want_ms)]} (waited {timeout_s} s)")
        time.sleep(5)
    log(f"ta-admin, org=- details search={SOLO}: {rows} after {time.monotonic() - started:.0f} s")
    projects = details(admin, "", by="projects", ids=str(ids["project_id"]))
    if projects is None or [r["id"] for r in projects["rows"]] != [ids["project_id"]]:
        fail(case, f"instance scope details by project {ids['project_id']}: {projects}")
    log(f"ta-admin, org=- details by project {ids['project_id']}: listed")

    orgs = [o["slug"] for o in admin.request("GET", "/api/organizations?page_size=100")["results"]]
    if not orgs:
        fail(case, "ta-admin lists no organization")
    for org in orgs:
        body = details(admin, org, search=SOLO)
        by_project = details(admin, org, by="projects", ids=str(ids["project_id"]))
        if body is None or by_project is None:
            fail(case, f"org={org}: the week is not processed, so absence shows nothing")
        if body["rows"] or by_project["rows"]:
            fail(case, f"org={org} lists {SOLO}'s personal work: {body['rows']} {by_project['rows']}")
    log(f"ta-admin, each of {len(orgs)} organizations: no {SOLO} row, no project {ids['project_id']}")
    passed(case, f"{SOLO}'s {SOLO_MINUTES} min in a personal workspace: under instance scope, under none of {len(orgs)} organizations")


# ---------------------------------------------------------------- credentials as a header

HEADER_CASES = [
    # (account, organization slug or "", expected status, expected error)
    ("ta-maintainer", "ta-org-a", 200, None),
    ("ta-worker", "ta-org-a", 403, "forbidden"),
    ("ta-outsider", "ta-org-a", 403, "forbidden"),
    ("ta-maintainer", "", 403, "organization_required"),
    (GROUP_ADMIN, "", 200, None),
]
HEADER_ENDPOINTS = ("status", "overview")
TOKEN_NAME = "ta-stack-access-case"


def header_get(authorization: str, path: str) -> tuple[int, object]:
    """A GET with only an Authorization header: an opener without a cookie jar."""
    request = urllib.request.Request(BASE_URL + path, headers={"Authorization": authorization})
    try:
        with urllib.request.build_opener().open(request, timeout=60) as resp:
            status, text = resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read().decode()
    try:
        return status, json.loads(text)
    except ValueError:
        return status, text[:200]


def decision(status: int, body: object, endpoint: str) -> tuple:
    """What the access rules decided, and for an overview the annotators it lists."""
    names = overview_names(body) if status == 200 and endpoint == "overview" else None
    return status, error_of(status, body), names


def issue_token(session: Session) -> dict:
    # revoked tokens are not listed, so only one left by an interrupted run is found here
    for token in session.request("GET", "/api/auth/access_tokens?page_size=100")["results"]:
        if token["name"] == TOKEN_NAME:
            session.request("DELETE", f"/api/auth/access_tokens/{token['id']}")
    expiry = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    return session.request("POST", "/api/auth/access_tokens", {"name": TOKEN_NAME, "read_only": True, "expiry_date": expiry})


def compare_scheme(scheme: str) -> str | None:
    """Every HEADER_CASES pair on every endpoint with the cookie and with `scheme`; the first
    difference, or None. Basic sends the account's password; Bearer a read-only personal access
    token issued for the case and revoked after it."""
    for username, org, want_status, want_error in HEADER_CASES:
        session = Session(username)
        token = issue_token(session) if scheme == "Bearer" else None
        try:
            authorization = (
                f"Bearer {token['value']}" if token
                else "Basic " + base64.b64encode(f"{username}:{PASSWORD}".encode()).decode()
            )
            for endpoint in HEADER_ENDPOINTS:
                path = endpoint_query(endpoint, org)
                # status and error never move with other work; an overview's annotators can, so
                # the pair is read again when only they differ (same_reads)
                cookie, got = same_reads(lambda: decision(*session.call(path), endpoint),
                                         lambda: decision(*header_get(authorization, path), endpoint))
                unprocessed = endpoint == "overview" and want_status == 200 and cookie[2] is None
                if cookie[:2] != (want_status, want_error) or unprocessed:
                    return f"{username}, org={org or '-'} {endpoint} with the cookie: {cookie}, expected {want_status} {want_error}"
                if got != cookie:
                    return f"{username}, org={org or '-'} {endpoint} with {scheme}: {got}, the cookie got {cookie}"
                log(f"{username}, org={org or '-'} {endpoint}: {want_status} {want_error or ''} with the cookie and with {scheme}")
        finally:
            if token:
                session.request("DELETE", f"/api/auth/access_tokens/{token['id']}")
    wrong = ("Basic " + base64.b64encode(b"ta-maintainer:not-the-password").decode()) if scheme == "Basic" else "Bearer not-a-token"
    status, body = header_get(wrong, query("status", org="ta-org-a"))
    if (status, error_of(status, body)) != (401, "not_authenticated"):
        return f"a wrong {scheme} credential: {status} {body}, expected 401 not_authenticated"
    log(f"a wrong {scheme} credential: 401 not_authenticated")
    return None


def header_credentials() -> None:
    """Basic and Bearer are judged apart, each on its own line, so one cannot hide the other."""
    case = "header-credentials"
    status, body = get_json(urllib.request.build_opener(), query("status", org="ta-org-a"))
    if (status, error_of(status, body)) != (401, "not_authenticated"):
        fail(case, f"no credentials: {status} {body}, expected 401 not_authenticated")
    log("no credentials: 401 not_authenticated")
    failures = []
    for scheme in ("Basic", "Bearer"):
        problem = compare_scheme(scheme)
        if problem:
            print(f"[access] FAIL {case} ({scheme}): {problem}", flush=True)
            failures.append(scheme)
        else:
            passed(f"{case} ({scheme})", f"{len(HEADER_CASES)} accounts x {len(HEADER_ENDPOINTS)} endpoints decided as with the cookie")
    if failures:
        raise SystemExit(f"[access] FAIL {case}: {', '.join(failures)}")


def main() -> None:
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "check-ingress":
        check_ingress(args[1])
    elif args == ["removed-member"]:
        removed_member()
    elif args == ["group-admin"]:
        group_admin()
    elif len(args) == 2 and args[0] == "personal-workspace":
        personal_workspace(int(args[1]))
    elif args == ["header-credentials"]:
        header_credentials()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
