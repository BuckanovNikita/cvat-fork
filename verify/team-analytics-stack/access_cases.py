"""Four access cases of Team Analytics against the stack's real CVAT (`/api/team-analytics/`).
Driven by run.sh; each command judges its own case and exits non-zero on a failure.

    access_cases.py revoked-admin        an account in the admin group reads (with and without an
                                         organization, and the settings); ta-admin takes it out of the
                                         group; its very next requests, in its old session and in a fresh
                                         one, are 403 with no wait; it is put back in the group
    access_cases.py group-admin          an administrator by group who is not a superuser reads
                                         instance scope and a named organization, as ta-admin does
    access_cases.py personal-workspace SECS
                                         job work in ta-solo's personal workspace appears under
                                         instance scope and under no organization (waits up to SECS
                                         for the scheduled refresh)
    access_cases.py header-credentials   credentials sent as an Authorization header (Basic, and a
                                         personal access token as Bearer) get the decisions a
                                         session cookie gets: administrators 200 (404 for an unknown
                                         organization), every other account 403 (members of every role,
                                         ta-org-r's maintainer ta-leaver among them, and an outsider)

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

from stack_api import (  # noqa: E402
    ADMIN,
    API,
    PASSWORD,
    Session,
    admin_session,
    get_json,
    reader,
    refusal,
    send,
    send_work,
    upload_images,
)

HERE = Path(__file__).resolve().parent
ACCESS_ACCOUNTS = json.loads((HERE / "access_accounts.json").read_text())
ADMIN_ONLY_HISTORY = {"first_day", "days_ready", "days_total"}  # status keys only administrators get (ticket 15)


ANY = object()  # an expected error that is not judged (a 404 of an unknown organization)
REMOVED_ORG = "ta-org-r"
LEAVER = "ta-leaver"  # a maintainer of ta-org-r: a plain member, refused like every member
GROUP_ADMIN = "ta-group-admin"
REVOKED = "ta-revoked-admin"  # in the admin group; revoked-admin takes it out and puts it back
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
    """forbidden, not_authenticated, bad_request, ... by the exact body (stack_api.refusal)."""
    return refusal(status, body)


# ---------------------------------------------------------------- an administrator who stops being one


# what the revoked administrator asks, in its old session and in a fresh one: reads with and without an organization,
# and the settings
REVOKED_PATHS = (
    ("status, org=-", query("status")),
    ("status, org=ta-org-a", query("status", org="ta-org-a")),
    ("overview, org=ta-org-a", endpoint_query("overview", "ta-org-a")),
    ("settings", API + "settings"),
)


def set_groups(case: str, admin: Session, user_id: int, groups: list[str]) -> None:
    status, answer = send(admin.opener, "PATCH", f"/api/users/{user_id}", {"groups": groups}, admin._csrf())
    if status != 200 or sorted(answer.get("groups", [])) != sorted(groups):
        fail(case, f"{ADMIN} PATCH /api/users/{user_id} groups={groups}: {status} {str(answer)[:200]}")


def revoked_admin() -> None:
    """Who may read Team Analytics is decided on every request: an account in the admin group reads; once ta-admin
    has taken it out of the group through CVAT's API, its very next request, in the session it already has and in a
    fresh one, is the plain 403, with no wait. The account is put back in the admin group afterwards (seed-access
    also does that on every run)."""
    case = "revoked-admin"
    old = Session(REVOKED)  # one session throughout: signed in while an administrator
    me = old.request("GET", "/api/users/self")
    if me["groups"] != ["admin"] or me.get("is_superuser") is not False:
        fail(case, f"{REVOKED} is groups={me['groups']} is_superuser={me.get('is_superuser')}, expected only the admin "
                   "group and no superuser flag (run.sh seed-access first)")
    for what, path in REVOKED_PATHS:
        status, body = old.call(path)
        if status != 200:
            fail(case, f"{REVOKED} {what} as an administrator: {status} {str(body)[:200]}, expected 200")
    log(f"{REVOKED} in the admin group: 200 on {', '.join(w for w, _ in REVOKED_PATHS)}")
    admin = admin_session()
    failure: BaseException | None = None
    try:
        set_groups(case, admin, me["id"], ["user"])
        revoked_at = time.monotonic()
        log(f"{ADMIN} took {REVOKED} out of the admin group (PATCH /api/users/{me['id']} groups=['user'])")
        # judged at once: the old session's next requests, then a fresh session's, no wait in between
        seen = []
        for label, session in (("its old session", old), ("a fresh session", None)):
            session = session or Session(REVOKED)
            for what, path in REVOKED_PATHS:
                status, body = session.call(path)
                seen.append((label, what, status))
                if (status, error_of(status, body)) != (403, "forbidden"):
                    fail(case, f"{REVOKED} {what} in {label} {time.monotonic() - revoked_at:.1f} s after leaving the "
                               f"admin group: {status} {str(body)[:200]}, expected 403 forbidden")
        elapsed = time.monotonic() - revoked_at
        log(f"after: {seen}")
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            set_groups(case, admin, me["id"], ["admin"])
            log(f"{REVOKED} back in the admin group")
        except BaseException as restore:
            # the restore's own failure must not hide the case's: both are printed, the case's first
            if failure is not None:
                print(f"[access] FAIL {case}: {failure}", flush=True)
            print(f"[access] FAIL {case}: putting {REVOKED} back in the admin group failed: {restore}", flush=True)
            raise SystemExit(f"[access] FAIL {case}: {failure or 'the case passed'}; then putting {REVOKED} back "
                             f"in the admin group failed: {restore} (run.sh seed-access puts it back)") from None
    status, _ = old.call(REVOKED_PATHS[0][1])
    if status != 200:
        fail(case, f"{REVOKED} back in the admin group: status {status}, expected 200")
    passed(case, f"{REVOKED}: 200 in the admin group; out of it, 403 forbidden on its next {len(seen)} requests (old "
                 f"session and fresh, all within {elapsed:.1f} s); back in the group, 200 again")


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
        status, body = reader(org, GROUP_ADMIN).call(query("status", org=org))
        history = body.get("history") if isinstance(body, dict) else None
        if status != 200 or not isinstance(history, dict) or not ADMIN_ONLY_HISTORY <= set(history):
            fail(case, f"status org={org or '-'}: {status} {str(body)[:300]}, expected 200 with the administrator's history")
        log(f"{GROUP_ADMIN}, org={org or '-'} status: 200 with {sorted(ADMIN_ONLY_HISTORY)}")
    named, superusers_org = same_reads(lambda: annotators(reader("ta-org-a", GROUP_ADMIN), "ta-org-a"),
                                       lambda: annotators(reader("ta-org-a"), "ta-org-a"))
    if not named or named != superusers_org:
        fail(case, f"overview org=ta-org-a: {named}, expected the superuser's view {superusers_org}")
    instance, superusers_view = same_reads(lambda: annotators(reader("", GROUP_ADMIN), ""),
                                           lambda: annotators(reader(""), ""))
    if instance != superusers_view or instance == named:
        fail(case, f"overview org=-: {instance}, expected the superuser's instance scope {superusers_view}")
    log(f"{GROUP_ADMIN}, org=ta-org-a overview: {named}, as the superuser ta-admin sees it")
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

    admin = reader("")
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

    orgs = [o["slug"] for o in admin.session.request("GET", "/api/organizations?page_size=100")["results"]]
    if not orgs:
        fail(case, "ta-admin lists no organization")
    for org in orgs:
        body = details(reader(org), org, search=SOLO)
        by_project = details(reader(org), org, by="projects", ids=str(ids["project_id"]))
        if body is None or by_project is None:
            fail(case, f"org={org}: the week is not processed, so absence shows nothing")
        if body["rows"] or by_project["rows"]:
            fail(case, f"org={org} lists {SOLO}'s personal work: {body['rows']} {by_project['rows']}")
    log(f"ta-admin, each of {len(orgs)} organizations: no {SOLO} row, no project {ids['project_id']}")
    passed(case, f"{SOLO}'s {SOLO_MINUTES} min in a personal workspace: under instance scope, under none of {len(orgs)} organizations")


# ---------------------------------------------------------------- credentials as a header

UNKNOWN_ORG = "ta-no-such-org"
HEADER_CASES = [
    # (account, organization slug or "", expected status, expected error): administrators, by group or as the
    # superuser, read with and without an organization (an unknown one is 404, whatever its body); every other
    # account is refused with DRF's plain 403, with or without its organization
    (GROUP_ADMIN, "", 200, None),
    (GROUP_ADMIN, "ta-org-a", 200, None),
    (GROUP_ADMIN, UNKNOWN_ORG, 404, ANY),
    (ADMIN, "", 200, None),
    (ADMIN, "ta-org-a", 200, None),
    ("ta-owner", "ta-org-a", 403, "forbidden"),
    ("ta-maintainer", "ta-org-a", 403, "forbidden"),
    ("ta-supervisor", "ta-org-a", 403, "forbidden"),
    ("ta-worker", "ta-org-a", 403, "forbidden"),
    ("ta-outsider", "ta-org-a", 403, "forbidden"),
    ("ta-maintainer", "", 403, "forbidden"),
    ("ta-owner-r", REMOVED_ORG, 403, "forbidden"),
    (LEAVER, REMOVED_ORG, 403, "forbidden"),
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
                if cookie[0] != want_status or (want_error is not ANY and cookie[1] != want_error) or unprocessed:
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
    if args == ["revoked-admin"]:
        revoked_admin()
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
