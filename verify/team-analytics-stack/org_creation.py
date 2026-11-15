"""Only administrators create organizations (the fork's ORGANIZATIONS_MIN_ROLE_TO_CREATE = "admin",
cvat/settings/base.py; upstream's rule in cvat/apps/organizations/rules/organizations.rego). Driven by run.sh
check-org-creation, part of up; judges itself and exits non-zero on a failure.

    org_creation.py check

1. Non-administrators are refused: an account with the global role user and no organization (ta-outsider), one with
   the global role worker (ta-worker-i2 of issue_accounts.json; set to worker by ta-admin here, the value the issue
   matrix gives it), and an owner and a maintainer of an organization (ta-owner, ta-maintainer of ta-org-a) each send
   POST /api/organizations with a slug of their own: 403, and no organization with that slug exists afterwards.
2. An administrator (ta-admin) creates one: 201; it is deleted again by the check, also when a later step fails.
3. The seeded organizations still work: GET /api/team-analytics/status as the administrator in ta-org-a and in
   ta-org-b answers 200 (Team Analytics answers only administrators). The seed creates organizations through the
   ORM (seed_users.py), so the rule does not reach it; this asserts it.

Environment: TA_BASE_URL, TA_SEED_PASSWORD. Standard library only.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run with python3 -I, which leaves it out

from stack_api import API, BASE_URL, Session, reader  # noqa: E402

ADMIN = "ta-admin"
# (account, the global role it must have, the organization it must own or maintain, or None)
REFUSED = [
    ("ta-outsider", "user", None),
    ("ta-worker-i2", "worker", None),
    ("ta-owner", "user", ("ta-org-a", "owner")),
    ("ta-maintainer", "user", ("ta-org-a", "maintainer")),
]
SEEDED = ["ta-org-a", "ta-org-b"]


def send(session: Session, method: str, path: str, body: object = None) -> tuple[int, object]:
    """One request, not retried and not raising on a refusal: (status, JSON body or text)."""
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(BASE_URL + path, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if method != "GET":
        request.add_header("Origin", BASE_URL)
        request.add_header("X-CSRFTOKEN", session._csrf())
    try:
        with session.opener.open(request, timeout=60) as resp:
            status, text = resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read().decode()
    try:
        return status, json.loads(text) if text.strip() else None
    except ValueError:
        return status, text[:200]


def slug() -> str:
    return f"ta-oc-{uuid.uuid4().hex[:8]}"  # CVAT allows 16 characters


def organizations_with(admin: Session, value: str) -> list:
    status, body = send(admin, "GET", f"/api/organizations?slug={value}&page_size=10")
    if status != 200:
        raise SystemExit(f"[org-creation] FAIL: ta-admin could not list organizations: {status} {body}")
    return [o for o in body["results"] if o["slug"] == value]


def check() -> None:
    admin = Session(ADMIN)
    problems: list[str] = []

    # the worker account's global role, as the issue matrix sets it (the seed gives every account user)
    worker_id = Session("ta-worker-i2").request("GET", "/api/users/self")["id"]
    status, answer = send(admin, "PATCH", f"/api/users/{worker_id}", {"groups": ["worker"]})
    if status != 200:
        raise SystemExit(f"[org-creation] FAIL: setting ta-worker-i2's role worker: {status} {answer}")

    # 1. every non-administrator is refused, and nothing is created
    for username, role, membership in REFUSED:
        session = Session(username)
        me = session.request("GET", "/api/users/self")
        groups = sorted(me["groups"])
        if groups != [role]:
            problems.append(f"{username} has the global roles {groups}, expected [{role!r}]")
            continue
        if membership:
            org, want = membership
            rows = admin.request("GET", f"/api/memberships?org={org}&user={username}&page_size=10")["results"]
            if [r["role"] for r in rows] != [want]:
                problems.append(f"{username} in {org}: {[r['role'] for r in rows]}, expected [{want!r}]")
                continue
        value = slug()
        status, body = send(session, "POST", "/api/organizations", {"slug": value, "name": f"refused {value}"})
        left = organizations_with(admin, value)
        for o in left:  # never leave one behind, whatever the answer was
            send(admin, "DELETE", f"/api/organizations/{o['id']}")
        what = f"{username} (global role {role}{', ' + membership[1] + ' of ' + membership[0] if membership else ''})"
        print(f"  {what}: POST /api/organizations {value} -> {status} {str(body)[:120]}; organizations with that slug "
              f"afterwards: {len(left)}", flush=True)
        if status != 403 or left:
            problems.append(f"{what}: {status} {str(body)[:200]}, {len(left)} organization(s) {value} created")

    # 2. an administrator creates one, and it is removed again
    value = slug()
    created = None
    try:
        status, body = send(admin, "POST", "/api/organizations", {"slug": value, "name": f"admin {value}"})
        created = body.get("id") if isinstance(body, dict) else None
        print(f"  {ADMIN}: POST /api/organizations {value} -> {status}", flush=True)
        if status != 201 or not organizations_with(admin, value):
            problems.append(f"{ADMIN}: {status} {str(body)[:200]}, expected 201 and the organization listed")
    finally:
        for o in organizations_with(admin, value):
            send(admin, "DELETE", f"/api/organizations/{o['id']}")
        left = organizations_with(admin, value)
        print(f"  {ADMIN}'s organization {value} (id {created}) deleted again; left: {len(left)}", flush=True)
        if left:
            problems.append(f"the administrator's organization {value} could not be deleted")

    # 3. the seeded organizations still work: the administrator reads each
    for org in SEEDED:
        session = reader(org)
        status, body = session.call(API + f"status?tz=UTC&org={org}")
        print(f"  {session.username}: GET {API}status -> {status}", flush=True)
        if status != 200:
            problems.append(f"{session.username}: status {status} {str(body)[:200]}, expected 200")

    if problems:
        raise SystemExit("[org-creation] FAIL: " + "; ".join(problems))
    print(f"[org-creation] PASS: {len(REFUSED)} non-administrators refused (403, nothing created), the administrator "
          f"created one (201, deleted again) and reads the {len(SEEDED)} seeded organizations", flush=True)


if __name__ == "__main__":
    if sys.argv[1:] != ["check"]:
        raise SystemExit(__doc__)
    check()
