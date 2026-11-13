"""Shared helpers for seam 1 tests: a real ClickHouse, a stand-in CVAT and the service over HTTP.

Each test builds its own `Stack`, which owns a fresh events database (created with CVAT's own
ClickHouse init script) and a fresh totals database, so test files can run in any order against one
ClickHouse. CVAT's identity answers come from `FakeCvat`, a small HTTP server that plays CVAT's
`/api/users/self`, `/api/organizations` and `/api/memberships` for the credentials a test defines.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import threading
import time
import unittest
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

import clickhouse_connect

from team_analytics.config import Config
from team_analytics.http_server import make_server
from team_analytics.service import Service

EVENT_COLUMNS = (
    "scope", "obj_name", "obj_id", "obj_val", "source", "timestamp", "count", "duration",
    "project_id", "task_id", "job_id", "user_id", "user_name", "user_email", "org_id", "org_slug",
    "payload",
)

# A fixed "now" for tests: Friday 2026-11-13 15:20 UTC.
NOW = datetime(2026, 11, 13, 15, 20, tzinfo=UTC)


def at(text: str) -> datetime:
    """'2026-11-13 10:00:00' (UTC) -> aware datetime."""
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def clickhouse_client(database: str = "default"):
    return clickhouse_connect.get_client(
        host=os.environ["CLICKHOUSE_HOST"],
        port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
        username=os.environ.get("CLICKHOUSE_USER", "user"),
        password=os.environ.get("CLICKHOUSE_PASSWORD", "user"),
        database=database,
    )


def wait_for_clickhouse(timeout: float = 90) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            clickhouse_client().command("SELECT 1")
            return
        except Exception:  # noqa: BLE001 - any failure means "not up yet"
            if time.monotonic() > deadline:
                raise
            time.sleep(0.5)


def _create_events_database(name: str) -> None:
    spec = importlib.util.spec_from_file_location("cvat_clickhouse_init", os.environ["TEAM_ANALYTICS_EVENTS_INIT"])
    init = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(init)
    with contextlib.redirect_stdout(io.StringIO()):  # the script reports each migration
        _run_init(init, name)


def _run_init(init, name: str) -> None:
    init.main([
        "--host", os.environ["CLICKHOUSE_HOST"], "--port", os.environ.get("CLICKHOUSE_PORT", "8123"),
        "--user", os.environ.get("CLICKHOUSE_USER", "user"),
        "--password", os.environ.get("CLICKHOUSE_PASSWORD", "user"), "--db", name,
    ])


def working_time(when: datetime, ms: int, *, user: tuple[int, str], org: int | None, project: int | None = 1,
                 task: int | None = 1, job: int | None = 1, duration: int | None = None) -> dict:
    """A `send:working_time` row as the CVAT server writes it."""
    return {
        "scope": "send:working_time", "source": "server", "timestamp": when, "count": 1,
        "duration": ms if duration is None else duration,
        "project_id": project, "task_id": task, "job_id": job,
        "user_id": user[0], "user_name": user[1], "user_email": f"{user[1]}@example.com",
        "org_id": org, "org_slug": None if org is None else f"org{org}",
        "payload": json.dumps({"working_time": ms, "request": {"id": str(uuid.uuid4()), "user_agent": "test"}},
                              separators=(",", ":")),
    }


# --- stand-in CVAT ---------------------------------------------------------------------------------

@dataclass
class FakeUser:
    id: int
    username: str
    groups: list[str] = field(default_factory=lambda: ["user"])
    # org slug -> (org id, role, is_active)
    memberships: dict[str, tuple[int, str, bool]] = field(default_factory=dict)
    # CVAT's is_staff/is_superuser flags; None = the usual case, set exactly when in the admin group
    superuser: bool | None = None


class FakeCvat:
    """Answers like CVAT's identity endpoints for the session cookies a test registers."""

    def __init__(self) -> None:
        self.users: dict[str, FakeUser] = {}  # sessionid -> user
        self.organizations: dict[str, int] = {}  # slug -> id
        self.requests: list[dict] = []
        self.down = False
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # keep test output quiet
                pass

            def do_GET(self):  # noqa: N802 - http.server API
                if fake.down:  # drop the connection without an answer, as an unreachable CVAT would
                    self.close_connection = True
                    return
                url = urlsplit(self.path)
                query = {k: v[-1] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
                fake.requests.append({"path": url.path, "query": query, "headers": dict(self.headers.items())})
                status, body = fake.answer(url.path, query, self.headers)
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def add_user(self, session: str, user: FakeUser) -> FakeUser:
        self.users[session] = user
        for slug, (org_id, _, _) in user.memberships.items():
            self.organizations[slug] = org_id
        return user

    def _caller(self, headers) -> FakeUser | None:
        for part in (headers.get("Cookie") or "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == "sessionid" and value in self.users:
                return self.users[value]
        return None

    def answer(self, path: str, query: dict, headers) -> tuple[int, dict]:
        if (headers.get("Accept") or "").strip() == "application/json":
            # observed on the v2.82.0 test stack: a plain JSON Accept header is not acceptable
            return 406, {"detail": 'Could not satisfy the request Accept header.'}
        user = self._caller(headers)
        if user is None:
            return 401, {"detail": "Authentication credentials were not provided."}
        slug = query.get("org")
        if slug and slug not in self.organizations:
            return 404, {"detail": f"{slug} organization does not exist."}
        is_admin = "admin" in user.groups
        if path == "/api/users/self":
            superuser = is_admin if user.superuser is None else user.superuser
            return 200, {"id": user.id, "username": user.username, "groups": user.groups,
                         "is_staff": superuser, "is_superuser": superuser, "is_active": True}
        if path == "/api/organizations":
            visible = [s for s in self.organizations if is_admin or s in user.memberships]
            if "slug" in query:
                visible = [s for s in visible if s == query["slug"]]
            return 200, self._page([{"id": self.organizations[s], "slug": s, "name": s} for s in visible])
        if path == "/api/memberships":
            if slug and not is_admin and slug not in user.memberships:
                return 403, {"detail": "You do not have permission to perform this action."}
            rows = []
            # CVAT's memberships.rego: without an organization a non-admin sees only their own
            # active memberships, across all organizations
            sandbox = not slug and not is_admin
            for owner in self.users.values():
                if sandbox and owner is not user:
                    continue
                for s, (org_id, role, active) in owner.memberships.items():
                    if sandbox and not active:
                        continue
                    if (not slug or s == slug) and query.get("user") in (None, owner.username):
                        rows.append({"id": len(rows) + 1, "organization": org_id, "role": role, "is_active": active,
                                     "user": {"id": owner.id, "username": owner.username}})
            return 200, self._page(rows)
        return 404, {"detail": "Not found."}

    @staticmethod
    def _page(rows: list[dict]) -> dict:
        return {"count": len(rows), "next": None, "previous": None, "results": rows}


# --- the stack a test runs against -------------------------------------------------------------------

class Stack:
    def __init__(self, *, now: datetime = NOW, technical_accounts: tuple[str, ...] = (),
                 cvat_url: str | None = None, refresh_window_hours: int = 48) -> None:
        suffix = uuid.uuid4().hex[:12]
        self.events_db = f"ta_test_events_{suffix}"
        self.totals_db = f"ta_test_totals_{suffix}"
        _create_events_database(self.events_db)
        self.cvat = FakeCvat()
        self.now = now
        self.config = Config(
            clickhouse_host=os.environ["CLICKHOUSE_HOST"],
            clickhouse_port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
            clickhouse_user=os.environ.get("CLICKHOUSE_USER", "user"),
            clickhouse_password=os.environ.get("CLICKHOUSE_PASSWORD", "user"),
            events_db=self.events_db,
            totals_db=self.totals_db,
            cvat_url=cvat_url or self.cvat.url,
            technical_accounts=technical_accounts,
            refresh_window_hours=refresh_window_hours,
        )
        self.service = self.new_service()
        self.http = make_server(self.service, "127.0.0.1", 0)
        self.url = f"http://127.0.0.1:{self.http.server_address[1]}"
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def new_service(self, clock=None) -> Service:
        """Another service instance (e.g. a second replica) on the same databases; same clock by default."""
        service = Service(self.config, clock=clock or (lambda: self.now))
        service.setup()
        return service

    def close(self) -> None:
        self.http.shutdown()
        self.http.server_close()
        self.cvat.close()
        client = clickhouse_client()
        client.command(f"DROP DATABASE IF EXISTS {self.events_db}")
        client.command(f"DROP DATABASE IF EXISTS {self.totals_db}")

    def add_events(self, rows: list[dict]) -> None:
        data = [[row.get(column) for column in EVENT_COLUMNS] for row in rows]
        clickhouse_client(self.events_db).insert("events", data, column_names=list(EVENT_COLUMNS))

    def refresh(self, now: datetime | None = None):
        if now is not None:
            self.now = now
        return self.service.refresh()

    def keep_refreshing_since(self, since: datetime) -> None:
        """Refresh as a service running since `since` would have, ending at the current clock."""
        end = self.now
        moment = since
        while moment < end:
            self.refresh(moment)
            moment += timedelta(hours=46)  # windows of 48 h overlap
        self.refresh(end)

    def get(self, path: str, session: str | None = None, headers: dict | None = None, **query) -> tuple[int, dict]:
        request = Request(f"{self.url}{path}?{urlencode(query)}", headers=dict(headers or {}))
        if session is not None:
            request.add_header("Cookie", f"csrftoken=abc; sessionid={session}")
        try:
            with urlopen(request, timeout=30) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")

    def overview(self, session: str | None, **query) -> tuple[int, dict]:
        return self.get("/team-analytics-api/v1/overview", session, **query)


class StackTestCase(unittest.TestCase):
    """Gives each test `self.stack`; ClickHouse readiness is awaited once per process."""

    _clickhouse_ready = False
    stack_options: dict = {}

    def setUp(self) -> None:
        if not StackTestCase._clickhouse_ready:
            wait_for_clickhouse()
            StackTestCase._clickhouse_ready = True
        self.stack = Stack(**self.stack_options)
        self.addCleanup(self.stack.close)


def hours_ago(hours: float) -> datetime:
    return NOW - timedelta(hours=hours)
