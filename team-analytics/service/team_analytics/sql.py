"""Runs the SQL files under `sql/`. The service binds parameters and shapes rows; SQL does the rest.

A file names databases with `$events_db` and `$totals_db` (validated identifiers from the
configuration, substituted as text) and takes values as ClickHouse query parameters
(`{name:Type}`), bound server side.

One ClickHouse client serves every thread (HTTP requests and the refresh loop). It is created on first
use (ClickHouse may not be up when the service starts) and has no session: a session would serialize
queries and refuse concurrent ones, while a session-less client only shares its connection pool, which
is safe across threads. File texts are read once.
"""

from __future__ import annotations

import re
import threading
from functools import cache
from pathlib import Path
from string import Template
from typing import Any

import clickhouse_connect

from team_analytics.config import Config

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SETTINGS = {"query_plan_execute_functions_after_sorting": 0}
# Connections kept open for the threads that query at the same time.
POOL_SIZE = 16


def identifier(name: str) -> str:
    if not _IDENTIFIER.match(name):
        raise ValueError(f"not a plain identifier: {name!r}")
    return name


@cache
def _file(name: str) -> Template:
    return Template((SQL_DIR / name).read_text())


def _values(params: dict[str, Any] | None) -> dict[str, Any] | None:
    """The parameters as bound. A value given as a callable is taken when the statement runs, not when the
    caller built the parameters: a statement that waited carries the time it ran at (the lease's clock)."""
    if not params:
        return None
    return {name: value() if callable(value) else value for name, value in params.items()}


class Sql:
    def __init__(self, config: Config) -> None:
        self._names = {"events_db": identifier(config.events_db), "totals_db": identifier(config.totals_db)}
        self._config = config
        self._client = None
        self._lock = threading.Lock()

    def _shared_client(self):
        with self._lock:
            if self._client is None:
                self._client = clickhouse_connect.get_client(
                    host=self._config.clickhouse_host, port=self._config.clickhouse_port,
                    username=self._config.clickhouse_user, password=self._config.clickhouse_password,
                    autogenerate_session_id=False,
                    pool_mgr=clickhouse_connect.driver.httputil.get_pool_manager(maxsize=POOL_SIZE),
                )
            return self._client

    def text(self, name: str, **identifiers: str) -> str:
        names = {**self._names, **{key: identifier(value) for key, value in identifiers.items()}}
        return _file(name).substitute(names)

    @staticmethod
    def files(directory: str) -> list[str]:
        """The `.sql` files of one directory, in name order, as names relative to `sql/`."""
        return [f"{directory}/{path.name}" for path in sorted((SQL_DIR / directory).glob("*.sql"))]

    def statements(self, name: str, params: dict[str, Any] | None = None, **identifiers: str) -> None:
        """Runs a file of `;`-separated statements (DDL, inserts, mutations)."""
        client = self._shared_client()
        for statement in self.text(name, **identifiers).split(";\n"):
            if statement.strip():
                client.command(statement, parameters=_values(params), settings=SETTINGS)

    def rows(self, name: str, params: dict[str, Any] | None = None, **identifiers: str) -> list[dict[str, Any]]:
        result = self._shared_client().query(self.text(name, **identifiers), parameters=_values(params),
                                             settings=SETTINGS)
        return [dict(zip(result.column_names, row, strict=True)) for row in result.result_rows]
