"""Runs the SQL files under `sql/`. The service binds parameters and shapes rows; SQL does the rest.

A file names databases with `$events_db` and `$totals_db` (validated identifiers from the
configuration, substituted as text) and takes values as ClickHouse query parameters
(`{name:Type}`), bound server side.
"""

from __future__ import annotations

import re
from pathlib import Path
from string import Template
from typing import Any

import clickhouse_connect

from team_analytics.config import Config

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SETTINGS = {"query_plan_execute_functions_after_sorting": 0}


def identifier(name: str) -> str:
    if not _IDENTIFIER.match(name):
        raise ValueError(f"not a plain identifier: {name!r}")
    return name


class Sql:
    def __init__(self, config: Config) -> None:
        self._names = {"events_db": identifier(config.events_db), "totals_db": identifier(config.totals_db)}
        self._config = config

    def _client(self):
        # One client per call: clickhouse_connect clients are not safe to share between threads.
        return clickhouse_connect.get_client(
            host=self._config.clickhouse_host, port=self._config.clickhouse_port,
            username=self._config.clickhouse_user, password=self._config.clickhouse_password,
        )

    def text(self, name: str, **identifiers: str) -> str:
        names = {**self._names, **{key: identifier(value) for key, value in identifiers.items()}}
        return Template((SQL_DIR / name).read_text()).substitute(names)

    @staticmethod
    def files(directory: str) -> list[str]:
        """The `.sql` files of one directory, in name order, as names relative to `sql/`."""
        return [f"{directory}/{path.name}" for path in sorted((SQL_DIR / directory).glob("*.sql"))]

    def statements(self, name: str, params: dict[str, Any] | None = None, **identifiers: str) -> None:
        """Runs a file of `;`-separated statements (DDL, inserts, mutations)."""
        client = self._client()
        try:
            for statement in self.text(name, **identifiers).split(";\n"):
                if statement.strip():
                    client.command(statement, parameters=params or None, settings=SETTINGS)
        finally:
            client.close()

    def rows(self, name: str, params: dict[str, Any] | None = None, **identifiers: str) -> list[dict[str, Any]]:
        client = self._client()
        try:
            result = client.query(self.text(name, **identifiers), parameters=params or None, settings=SETTINGS)
            return [dict(zip(result.column_names, row, strict=True)) for row in result.result_rows]
        finally:
            client.close()
