"""Shared helpers for the calculation tests: a real ClickHouse, a real Redis and the backend's engine.

Each test builds its own `Stack`, which owns a fresh events database (created with CVAT's own
ClickHouse init script), a fresh totals database and a refresh lock in Redis of its own name, so test
files can run in any order against one ClickHouse and one Redis. The figures are asked of the core's
`Engine` as the backend's worker asks them (jobs.read_answer): the query cleaned as the API process
cleans it (reads.clean_query), an engine with the worker's read limit, the scope as the worker builds
it, a refused parameter as a 400 and the answer as JSON text.

Who may read is decided by CVAT's permission system before a read is queued; it is not tested here.
Tests still name their callers by a session and an organization slug, and `PermissionStandIn` turns
those into the scope the permission system would hand over. It is test scaffolding: nothing here
asserts on its decisions.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import time
import unittest
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlencode

import clickhouse_connect
import redis

from cvat.apps.team_analytics import reads
from cvat.apps.team_analytics.core.config import Config
from cvat.apps.team_analytics.core.engine import Engine
from cvat.apps.team_analytics.core.periods import BadRequest
from cvat.apps.team_analytics.core.redis_lock import RedisLock
from cvat.apps.team_analytics.core.scope import Scope
from cvat.apps.team_analytics.core.sql import Limit

EVENT_COLUMNS = (
    "scope", "obj_name", "obj_id", "obj_val", "source", "timestamp", "count", "duration",
    "project_id", "task_id", "job_id", "user_id", "user_name", "user_email", "org_id", "org_slug",
    "payload",
)

# A fixed "now" for tests: Friday 2026-11-13 15:20 UTC.
NOW = datetime(2026, 11, 13, 15, 20, tzinfo=UTC)

# Where the backend serves the endpoints (cvat/apps/team_analytics/urls.py).
API = "/api/team-analytics/"
# What the worker allows each statement of an answer: the app's defaults for
# TEAM_ANALYTICS_READ_STATEMENT_S and TEAM_ANALYTICS_READ_STATEMENT_MEMORY_BYTES.
READ_LIMIT = Limit(20, 512 * 1024 * 1024)
# What the worker allows every other statement (jobs._engine: TEAM_ANALYTICS_REFRESH_STATEMENT_S).
STATEMENT_LIMIT = Limit(300)


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


def redis_connection() -> redis.Redis:
    return redis.Redis(host=os.environ["REDIS_HOST"], port=int(os.environ.get("REDIS_PORT", "6379")))


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


# --- who the caller is ---------------------------------------------------------------------------------

@dataclass
class FakeUser:
    id: int
    username: str
    groups: list[str] = field(default_factory=lambda: ["user"])
    # org slug -> (org id, role, is_active)
    memberships: dict[str, tuple[int, str, bool]] = field(default_factory=dict)


class NotAllowed(Exception):
    """The stand-in found no scope for the caller. Tests never expect it: who may read is not tested here."""


class PermissionStandIn:
    """A stand-in for CVAT's permission check (rules/team_analytics.rego and views.scope_of), so that tests can
    name their callers. It hands over the scope the backend would: a member of the admin group reads the named
    organization, or instance scope when none is named. Anyone else raises `NotAllowed`: only administrators read
    Team Analytics. A user's memberships only make the organizations' slugs known. Test scaffolding, not product
    code."""

    def __init__(self) -> None:
        self.users: dict[str, FakeUser] = {}  # session -> user
        self.organizations: dict[str, int] = {}  # slug -> id, of every registered user's memberships

    def add_user(self, session: str, user: FakeUser) -> FakeUser:
        self.users[session] = user
        for slug, (org_id, _, _) in user.memberships.items():
            self.organizations[slug] = org_id
        return user

    def scope(self, session: str | None, org_slug: str) -> Scope:
        user = self.users.get(session or "")
        if user is None or (org_slug and org_slug not in self.organizations):
            raise NotAllowed(session, org_slug)
        if "admin" not in user.groups:
            raise NotAllowed(session, org_slug)
        return Scope(org_id=self.organizations[org_slug] if org_slug else None, user_id=0, username="")


# --- the stack a test runs against -------------------------------------------------------------------

class Stack:
    def __init__(self, *, now: datetime = NOW, technical_accounts: tuple[int, ...] = (),
                 refresh_window_hours: int = 48, config_options: dict | None = None) -> None:
        suffix = uuid.uuid4().hex[:12]
        self.events_db = f"ta_test_events_{suffix}"
        self.totals_db = f"ta_test_totals_{suffix}"
        # one refresh lock per stack: the engines of a stack are workers sharing it, stacks never meet
        self.lock_name = f"ta_test_refresh_{suffix}"
        self.redis = redis_connection()
        _create_events_database(self.events_db)
        self.callers = PermissionStandIn()
        self.now = now
        # the user ids on the Technical accounts list, as the worker reads them from Postgres for each answer
        # (jobs.technical_account_ids); a test may change them between two reads
        self.technical_accounts = tuple(technical_accounts)
        self.config = Config(
            clickhouse_host=os.environ["CLICKHOUSE_HOST"],
            clickhouse_port=int(os.environ.get("CLICKHOUSE_PORT", "8123")),
            clickhouse_user=os.environ.get("CLICKHOUSE_USER", "user"),
            clickhouse_password=os.environ.get("CLICKHOUSE_PASSWORD", "user"),
            events_db=self.events_db,
            totals_db=self.totals_db,
            refresh_window_hours=refresh_window_hours,
            **(config_options or {}),  # any other setting of the engine, e.g. a shorter limit
        )
        # the engine that refreshes and steps (the worker's refresh job: no read limit)
        self.engine = self.new_engine()

    def lock(self, length_s: float | None = None, clock=None) -> RedisLock:
        """A worker process's handle on the stack's refresh lock (jobs._engine: Config.refresh_lease_s long by default)."""
        return RedisLock(self.redis, length_s or self.config.refresh_lease_s, name=self.lock_name, clock=clock)

    def new_engine(self, clock: Callable[[], datetime] | None = None, *, lock: RedisLock | None = None,
                   read_limit: Limit | None = None) -> Engine:
        """Another worker's engine on the same databases and lock (same clock by default), made ready as the first
        job of a worker that finds no readiness mark makes it (jobs._make_ready): the schema created, then the
        cutover looked for under the refresh lock."""
        engine = Engine(self.config, clock=clock or (lambda: self.now), lock=lock or self.lock(),
                        read_limit=read_limit, statement_limit=STATEMENT_LIMIT)
        engine.create_schema()
        engine.refresher.leased(engine.look_for_cutover)
        return engine

    def close(self) -> None:
        self.redis.delete(self.lock_name)
        client = clickhouse_client()
        client.command(f"DROP DATABASE IF EXISTS {self.events_db}")
        client.command(f"DROP DATABASE IF EXISTS {self.totals_db}")

    def add_events(self, rows: list[dict]) -> None:
        data = [[row.get(column) for column in EVENT_COLUMNS] for row in rows]
        clickhouse_client(self.events_db).insert("events", data, column_names=list(EVENT_COLUMNS))

    def refresh(self, now: datetime | None = None):
        if now is not None:
            self.now = now
        return self.engine.refresh()

    def keep_refreshing_since(self, since: datetime) -> None:
        """Refresh as a worker running since `since` would have, ending at the current clock, with its history
        computed: every period then holds its figures (one not fully processed would carry none)."""
        end = self.now
        moment = since
        while moment < end:
            self.refresh(moment)
            moment += timedelta(hours=46)  # windows of 48 h overlap
        self.refresh(end)
        self.settle()

    def settle(self, steps: int = 100) -> None:
        """Steps the engine until it has nothing more to do (it would wait for the next refresh)."""
        for _ in range(steps):
            if self.engine.step() >= 1:
                return
        raise AssertionError(f"the engine kept working after {steps} steps")

    def answer(self, endpoint: str, scope: Scope, query: dict[str, str],
               clock: Callable[[], datetime] | None = None) -> tuple[int, dict]:
        """What the worker's read job stores for one read (jobs.read_answer), as a client decodes it: the engine is
        built for the read with the worker's read limit and given the stack's technical accounts; a refused
        parameter is a 400."""
        engine = Engine(self.config, clock=clock or (lambda: self.now), lock=self.lock(), read_limit=READ_LIMIT,
                        statement_limit=STATEMENT_LIMIT)
        try:
            status, body = 200, engine.answer(endpoint, scope, query, technical_accounts=self.technical_accounts)
        except BadRequest as error:
            status, body = 400, {"error": "bad_request", "detail": str(error)}
        return status, json.loads(json.dumps(body))

    def get(self, path: str, session: str | None = None, *, clock: Callable[[], datetime] | None = None,
            **query) -> tuple[int, dict]:
        """A request to `path` (API + endpoint) by the caller registered under `session`, `org` naming the
        organization; `clock` is the reading worker's clock (the stack's by default)."""
        endpoint = path.removeprefix(API)
        assert path.startswith(API) and "/" not in endpoint, path
        # the values a client can send: text, as the query string carries it
        sent = {key: values[-1] for key, values in parse_qs(urlencode(query), keep_blank_values=True).items()}
        scope = self.callers.scope(session, sent.pop("org", ""))
        try:
            cleaned = reads.clean_query(endpoint, sent)  # views._answer: what the API process passes on
        except reads.QueryRefused as error:
            return 400, {"error": "bad_request", "detail": str(error)}
        return self.answer(endpoint, scope, cleaned, clock)

    def overview(self, session: str | None, **query) -> tuple[int, dict]:
        return self.get(API + "overview", session, **query)


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
