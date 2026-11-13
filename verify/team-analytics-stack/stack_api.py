"""Talks to the test stack through its forwarded address, the way the CVAT UI does.

    stack_api.py seed               read every seeded account and role back through the API
    stack_api.py send-event MARKER  send one client event as ta-worker

Environment: TA_BASE_URL, TA_SEED_PASSWORD. Standard library only.
"""

import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = os.environ["TA_BASE_URL"]
PASSWORD = os.environ["TA_SEED_PASSWORD"]
ACCOUNTS = json.loads((Path(__file__).parent / "accounts.json").read_text())

# Payload field the Team Analytics UI adds to existing events; it must survive the way to
# ClickHouse (run.sh check-event looks for it).
EXTRA_PAYLOAD = {"shape_type": "rectangle"}


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
        try:
            with self.opener.open(req, timeout=60) as resp:
                text = resp.read().decode()
        except urllib.error.HTTPError as e:
            raise SystemExit(f"{self.username}: {method} {path} -> {e.code} {e.read().decode()[:300]}") from None
        return json.loads(text) if text.strip() else None


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
        page = Session(owner).request("GET", f"/api/memberships?org={slug}&page_size=100")
        found = {m["user"]["username"]: (m["role"], m["is_active"]) for m in page["results"]}
        expected = {u: (r, True) for u, r in spec["members"].items()}
        check(found == expected, f"{slug} memberships {found}")
        print(f"  {slug}: {found}")
    for username in ACCOUNTS["users"]:
        if any(username in o["members"] for o in ACCOUNTS["organizations"].values()):
            continue
        if ACCOUNTS["users"][username]["admin"]:
            continue
        page = Session(username).request("GET", "/api/memberships?page_size=100")
        check(page["count"] == 0, f"{username} should be a member of nothing: {page['results']}")
        print(f"  {username}: member of nothing")


def send_event(marker: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
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


def main() -> None:
    if sys.argv[1:] == ["seed"]:
        seed_check()
    elif len(sys.argv) == 3 and sys.argv[1] == "send-event":
        send_event(sys.argv[2])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
