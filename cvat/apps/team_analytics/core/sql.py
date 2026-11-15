"""Runs the SQL files under `sql/`. Python binds parameters and shapes rows; SQL does the rest.

A file names databases with `$events_db` and `$totals_db` (validated identifiers from the
configuration, substituted as text) and takes values as ClickHouse query parameters
(`{name:Type}`), bound server side.

One ClickHouse client serves every thread of a process. It is created on first
use (ClickHouse may not be up when a worker starts) and has no session: a session would serialize
queries and refuse concurrent ones, while a session-less client only shares its connection pool, which
is safe across threads. File texts are read once.

A statement run with a `Limit` gets that limit as ClickHouse settings, so the server stops it there; that is
the bound. It is sent through a client of the same kind kept for that limit (one client per limit, so the cutover
search's two limits make two more clients), which gives up only after hearing nothing from the server for a few
seconds longer than the limit. No client's wait bounds a whole statement: the client
asks for progress headers, which reset its read timeout. The shared client keeps the library's wait (300 s).
"""

from __future__ import annotations

import math
import re
import threading
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from string import Template
from typing import Any

import clickhouse_connect

from .config import Config

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SETTINGS = {"query_plan_execute_functions_after_sorting": 0}
# Connections kept open for the threads that query at the same time.
POOL_SIZE = 16
# Seconds beyond a statement's limit that the client waits without hearing from the server before it gives
# up: ClickHouse stops the statement at its limit and answers with an error, so the client does not give up
# on a statement that still runs.
LIMIT_ANSWER_MARGIN_S = 5


@dataclass(frozen=True)
class Limit:
    """What ClickHouse allows one statement: `seconds` of execution and, when given, `memory_bytes`. A
    statement that reaches either is stopped by the server and fails."""

    seconds: float
    memory_bytes: int | None = None

    def settings(self) -> dict[str, Any]:
        settings: dict[str, Any] = {
            "max_execution_time": self.seconds,
            "timeout_overflow_mode": "throw",
        }
        if self.memory_bytes is not None:
            settings["max_memory_usage"] = self.memory_bytes
        return settings

    def answer_wait_s(self) -> int:
        """The client's read timeout for this statement: how long it waits without hearing from the server
        (whole seconds, as the client takes them)."""
        return math.ceil(self.seconds) + LIMIT_ANSWER_MARGIN_S


def identifier(name: str) -> str:
    if not _IDENTIFIER.match(name):
        raise ValueError(f"not a plain identifier: {name!r}")
    return name


@cache
def _file(name: str) -> Template:
    return Template((SQL_DIR / name).read_text())


class Sql:
    def __init__(
        self,
        config: Config,
        read_limit: Limit | None = None,
        statement_limit: Limit | None = None,
    ) -> None:
        self._names = {
            "events_db": identifier(config.events_db),
            "totals_db": identifier(config.totals_db),
        }
        self._config = config
        # the limit of every statement run with `rows` when given; set where only answers are read
        self._read_limit = read_limit
        # the limit of every other statement that is given none of its own (None: no limit): what bounds
        # a refresh or a day of history on the ClickHouse server, where a client that gave up stops nothing
        self._statement_limit = statement_limit
        # clients by how long they wait for an answer (None: the library's default), each made on first use
        self._clients: dict[int | None, Any] = {}
        self._lock = threading.Lock()

    def _shared_client(self, answer_wait_s: int | None = None):
        with self._lock:
            if answer_wait_s not in self._clients:
                wait = {} if answer_wait_s is None else {"send_receive_timeout": answer_wait_s}
                self._clients[answer_wait_s] = clickhouse_connect.get_client(
                    host=self._config.clickhouse_host,
                    port=self._config.clickhouse_port,
                    username=self._config.clickhouse_user,
                    password=self._config.clickhouse_password,
                    autogenerate_session_id=False,
                    pool_mgr=clickhouse_connect.driver.httputil.get_pool_manager(maxsize=POOL_SIZE),
                    **wait,
                )
            return self._clients[answer_wait_s]

    def text(self, name: str, **identifiers: str) -> str:
        names = {**self._names, **{key: identifier(value) for key, value in identifiers.items()}}
        return _file(name).substitute(names)

    @staticmethod
    def files(directory: str) -> list[str]:
        """The `.sql` files of one directory, in name order, as names relative to `sql/`."""
        return [f"{directory}/{path.name}" for path in sorted((SQL_DIR / directory).glob("*.sql"))]

    def statements(
        self,
        name: str,
        params: dict[str, Any] | None = None,
        limit: Limit | None = None,
        **identifiers: str,
    ) -> None:
        """Runs a file of `;`-separated statements (DDL, inserts, mutations), each within `limit`, or within
        the runner's statement limit when none is given."""
        limit = limit or self._statement_limit
        client = self._shared_client(None if limit is None else limit.answer_wait_s())
        settings = SETTINGS if limit is None else {**SETTINGS, **limit.settings()}
        for statement in self.text(name, **identifiers).split(";\n"):
            if statement.strip():
                client.command(statement, parameters=params, settings=settings)

    def rows(
        self, name: str, params: dict[str, Any] | None = None, **identifiers: str
    ) -> list[dict[str, Any]]:
        limit = self._read_limit or self._statement_limit
        client = self._shared_client(None if limit is None else limit.answer_wait_s())
        settings = SETTINGS if limit is None else {**SETTINGS, **limit.settings()}
        result = client.query(self.text(name, **identifiers), parameters=params, settings=settings)
        return [dict(zip(result.column_names, row, strict=True)) for row in result.result_rows]
