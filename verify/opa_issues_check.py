"""Runs the issue/comment permission matrix for both organization members.

Prints one row per (user, action) with the HTTP status the API answered, so the
same script run against stock rules and against the patched ones shows exactly
which denials the patch removes. The delete check gets a freshly created
throwaway issue each time, so the matrix is repeatable.

Usage: opa_issues_check.py <label>   # label goes into the JSON dump name
"""

import json
import os
import sys

import requests

STATE = os.environ.get("OPA_ISSUES_STATE", "/tmp/opa-issues-state.json")
LABEL = sys.argv[1] if len(sys.argv) > 1 else "run"
OUT = f"/tmp/opa-issues-{LABEL}.json"

state = json.load(open(STATE))
BASE, ORG = state["base"], state["org"]
PASSWORDS = {"admin": "verify-pass-123", "worker1": "worker-pass-123", "worker2": "worker-pass-123"}


def session(username: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"username": username, "password": PASSWORDS[username]}, timeout=30)
    r.raise_for_status()
    s.headers["Authorization"] = f"Token {r.json()['key']}"
    s.headers["X-Organization"] = ORG
    return s


admin = session("admin")


def throwaway_issue() -> int:
    r = admin.post(
        f"{BASE}/issues",
        json={
            "frame": 0,
            "job": state["job_id"],
            "position": [1.0, 1.0, 9.0, 9.0],
            "message": "throwaway target for the delete check",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["id"]


def probe(name, call):
    response = call()
    ok = response.status_code < 400
    return {"check": name, "status": response.status_code, "allowed": ok}


results = {}
for username in ("admin", "worker1", "worker2"):
    s = session(username)
    issue, comment = state["issue_id"], state["admin_comment_id"]
    victim = throwaway_issue()
    rows = [
        probe("list issues of the job", lambda: s.get(f"{BASE}/issues", params={"job_id": state["job_id"]}, timeout=30)),
        probe("read admin's issue", lambda: s.get(f"{BASE}/issues/{issue}", timeout=30)),
        probe("edit admin's issue", lambda: s.patch(f"{BASE}/issues/{issue}", json={"resolved": True}, timeout=30)),
        probe("list comments of the issue", lambda: s.get(f"{BASE}/comments", params={"issue_id": issue}, timeout=30)),
        probe("add a comment", lambda: s.post(f"{BASE}/comments", json={"issue": issue, "message": f"comment by {username}"}, timeout=30)),
        probe("edit admin's comment", lambda: s.patch(f"{BASE}/comments/{comment}", json={"message": f"admin's comment, edited by {username}"}, timeout=30)),
        probe("delete an issue admin opened", lambda: s.delete(f"{BASE}/issues/{victim}", timeout=30)),
    ]
    # the list check only means anything if the issue is actually in the page
    listing = s.get(f"{BASE}/issues", params={"job_id": state["job_id"]}, timeout=30)
    if listing.status_code < 400:
        rows[0]["allowed"] = issue in [i["id"] for i in listing.json()["results"]]
    results[username] = rows
    if not rows[-1]["allowed"]:
        admin.delete(f"{BASE}/issues/{victim}", timeout=30)

    # leave the shared issue unresolved so the next run starts from the same place
    admin.patch(f"{BASE}/issues/{issue}", json={"resolved": False}, timeout=30)

json.dump(results, open(OUT, "w"), indent=2)

width = max(len(r["check"]) for rows in results.values() for r in rows)
print(f"\n{LABEL}: {BASE}  organization={ORG}\n")
print(f"{'check'.ljust(width)}  " + "  ".join(u.center(11) for u in results))
print("-" * (width + 2 + 13 * len(results)))
for i, name in enumerate(r["check"] for r in results["admin"]):
    cells = []
    for username in results:
        row = results[username][i]
        cells.append(f"{'ALLOW' if row['allowed'] else 'DENY '} {row['status']}".center(11))
    print(f"{name.ljust(width)}  " + "  ".join(cells))
print()
