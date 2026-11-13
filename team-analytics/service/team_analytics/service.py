"""The service: access check, endpoint dispatch, schema setup and refresh.

Endpoints are the modules of `team_analytics.endpoints`; each defines `PATH` (the part after
`/team-analytics-api/v1/`) and `handle(request) -> dict`. Adding an endpoint is adding a module.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import ModuleType
from typing import Any

from team_analytics import endpoints
from team_analytics.access import Access, Refused, Scope
from team_analytics.config import Config
from team_analytics.periods import BadRequest, Span, period_span
from team_analytics.refresh import Refresher, RefreshResult
from team_analytics.sql import Sql

log = logging.getLogger(__name__)

PREFIX = "/team-analytics-api/v1/"


def utc_now() -> datetime:
    return datetime.now(UTC)


def discover(package: ModuleType) -> list[ModuleType]:
    return [importlib.import_module(f"{package.__name__}.{info.name}")
            for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda info: info.name)]


@dataclass
class Request:
    """What an endpoint gets: the caller's scope (from CVAT), the query, and the means to read."""

    scope: Scope
    query: dict[str, str]
    sql: Sql
    config: Config
    now: datetime
    cache: dict[str, Any] = field(default_factory=dict)

    def span(self) -> Span:
        return period_span(self.now, self.query.get("period", "week"), self.query.get("tz", "UTC"))

    def scope_params(self) -> dict[str, Any]:
        """Parameters every read file takes to stay inside the caller's scope."""
        return {
            "instance": 1 if self.scope.instance else 0,
            "org_id": self.scope.org_id or 0,
            "technical_accounts": list(self.config.technical_accounts),
        }


class Service:
    def __init__(self, config: Config, clock: Callable[[], datetime] = utc_now) -> None:
        self.config = config
        self.sql = Sql(config)
        self._clock = clock
        self.access = Access(config, lambda: self._clock().astimezone(UTC))
        self.refresher = Refresher(config, self.sql, lambda: self._clock().astimezone(UTC))
        self.endpoints = {module.PATH: module for module in discover(endpoints)}

    def setup(self) -> None:
        """Creates the totals database and tables (idempotent)."""
        for name in self.sql.files("schema"):
            self.sql.statements(name)

    def refresh(self) -> RefreshResult:
        return self.refresher.run()

    def handle(self, method: str, path: str, query: dict[str, str], headers: dict[str, str]) -> tuple[int, dict]:
        if method != "GET":
            return 405, {"error": "method_not_allowed"}
        endpoint = self.endpoints.get(path.removeprefix(PREFIX)) if path.startswith(PREFIX) else None
        if endpoint is None:
            return 404, {"error": "not_found"}
        try:
            scope = self.access.scope(headers, query.get("org", ""))
            request = Request(scope=scope, query=query, sql=self.sql, config=self.config,
                              now=self._clock().astimezone(UTC))
            return 200, endpoint.handle(request)
        except Refused as refused:
            return refused.status, {"error": refused.reason}
        except BadRequest as error:
            return 400, {"error": "bad_request", "detail": str(error)}
        except Exception:
            log.exception("request failed: %s", path)
            return 500, {"error": "internal"}
