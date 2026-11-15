"""Four access cases of Team Analytics against the stack's real CVAT (`/api/team-analytics/`).
Driven by run.sh; each command judges its own case and exits non-zero on a failure.

    access_cases.py removed-member       a maintainer removed from ta-org-r is refused on the next
                                         request, with no wait
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
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run with python3 -I, which leaves it out

from stack_api import API, PASSWORD, Session, get_json, refusal, send_work, upload_images

HERE = Path(__file__).resolve().parent
ACCESS_ACCOUNTS = json.loads((HERE / "access_accounts.json").read_text())
ADMIN_ONLY_HISTORY = {"first_day", "days_ready", "days_total"}  # status keys only administrators get (ticket 15)


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
    """forbidden, not_authenticated, organization_required, ... by the exact body (stack_api.refusal)."""
    return refusal(status, body)


# ---------------------------------------------------------------- a removed member


def removed_member() -> None:
    """CVAT's permission system decides on every request, and nothing caches who the caller is: the request
    right after the removal is refused, with and without the organization."""
    case = "removed-member"
    owner = Session(next(u for u, r in ACCESS_ACCOUNTS["organizations"][REMOVED_ORG]["members"].items() if r == "owner"))
    leaver = Session(LEAVER)  # one session throughout
    path = query("status", org=REMOVED_ORG)
    status, body = leaver.call(path)
    if status != 200:
        fail(case, f"{LEAVER} before the removal: {status} {body}, expected 200 (run.sh seed-access first)")
    log(f"{LEAVER}, org={REMOVED_ORG}, a maintainer: 200")

    rows = owner.request("GET", f"/api/memberships?org={REMOVED_ORG}&user={LEAVER}&page_size=100")["results"]
    if len(rows) != 1:
        fail(case, f"{REMOVED_ORG} has {len(rows)} memberships of {LEAVER}, expected 1")
    owner.request("DELETE", f"/api/memberships/{rows[0]['id']}?org={REMOVED_ORG}")
    removed_at = time.monotonic()
    log(f"{LEAVER} removed from {REMOVED_ORG} by its owner through CVAT's API")
    # judged at once: the first request after the removal, no wait in between
    for org in (REMOVED_ORG, ""):
        for endpoint in ("status", "overview"):
            status, body = leaver.call(endpoint_query(endpoint, org))
            if (status, error_of(status, body)) != (403, "forbidden"):
                fail(case, f"{LEAVER}, org={org or '-'} {endpoint} right after the removal: {status} {body}, expected 403 forbidden")
            log(f"{LEAVER}, org={org or '-'} {endpoint}: 403 {body}")
    elapsed = time.monotonic() - removed_at
    left = owner.request("GET", f"/api/memberships?org={REMOVED_ORG}&user={LEAVER}&page_size=100")["results"]
    if left:
        fail(case, f"the membership is still listed after the owner deleted it: {left}")
    passed(case, f"{LEAVER} removed from {REMOVED_ORG}: 403 forbidden with and without the organization on the "
                 f"next requests (all four within {elapsed:.1f} s of the removal)")


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
    return get_json(urllib.request.build_opener(), path, headers={"Authorization": authorization})


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
    if args == ["removed-member"]:
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
