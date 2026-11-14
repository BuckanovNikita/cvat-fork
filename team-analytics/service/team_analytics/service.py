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
from functools import cache
from types import ModuleType
from typing import Any

from team_analytics import endpoints
from team_analytics.access import Access, Refused, Scope
from team_analytics.config import Config
from team_analytics.cutover import Legacy, load_cutover, look_for_cutover
from team_analytics.history import History
from team_analytics.periods import BadRequest, Span, decimal, period_span
from team_analytics.refresh import LeaseClock, Refresher, RefreshResult
from team_analytics.sql import Limit, Sql
from team_analytics.worker import Worker

log = logging.getLogger(__name__)

PREFIX = "/team-analytics-api/v1/"

# values of the `shapes` query parameter (the page's Bounding boxes / All shapes switch)
SHAPES_BOUNDING_BOXES = "bounding_boxes"
SHAPES_ALL = "all"


def utc_now() -> datetime:
    return datetime.now(UTC)


@cache
def discover(package: ModuleType) -> tuple[ModuleType, ...]:
    """The modules of `package` (endpoints, overview or status sections), found once."""
    return tuple(importlib.import_module(f"{package.__name__}.{info.name}")
                 for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda info: info.name))


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
        return period_span(self.now, self.query.get("period", "week"), self.query.get("tz", "UTC"),
                           self.query.get("month"))

    def cutover(self) -> datetime | None:
        """The cutover to the new activity logging (cutover.py), read once per request."""
        if "cutover" not in self.cache:
            self.cache["cutover"] = load_cutover(self.sql)
        return self.cache["cutover"]

    def legacy(self, start: datetime, end: datetime) -> Legacy:
        """What the cutover makes of [start, end): pass `.params()` to read files, `.describe()` to responses."""
        return Legacy(self.cutover(), start, end)

    def filter_id(self, key: str) -> int | None:
        """The page's `project` or `annotator` filter: an id (project 0 = No project) or None when not set."""
        value = self.query.get(key, "")
        if value == "":
            return None
        number = decimal(value, 19)
        if number is None:
            raise BadRequest(f"{key} must be an identifier")
        return number

    def shapes(self) -> str:
        """The page's shape switch: `bounding_boxes` or `all` (the default when not given)."""
        value = self.query.get("shapes", "") or SHAPES_ALL
        if value not in (SHAPES_BOUNDING_BOXES, SHAPES_ALL):
            raise BadRequest(f"shapes must be {SHAPES_BOUNDING_BOXES} or {SHAPES_ALL}")
        return value

    def scope_params(self) -> dict[str, Any]:
        """Parameters every read file takes to stay inside the caller's scope and the page's filters.

        Filters only narrow: a read file adds `AND ({has_project:UInt8} = 0 OR project_id = {project:UInt64})`
        and `AND ({has_annotator:UInt8} = 0 OR user_id = {annotator:UInt64})` beside the scope conditions.
        """
        project, annotator = self.filter_id("project"), self.filter_id("annotator")
        return {
            "instance": 1 if self.scope.instance else 0,
            "org_id": self.scope.org_id or 0,
            "technical_accounts": list(self.config.technical_accounts),
            "has_project": 0 if project is None else 1,
            "project": project or 0,
            "has_annotator": 0 if annotator is None else 1,
            "annotator": annotator or 0,
            # shape switch: a read file of an operation figure keeps `shape = 'bounding_box'` rows when 1
            # (unless the period is legacy: pass request.legacy(...).params() too); see read/overview_operations.sql
            "bounding_boxes": 1 if self.shapes() == SHAPES_BOUNDING_BOXES else 0,
        }


class Service:
    def __init__(self, config: Config, clock: Callable[[], datetime] = utc_now,
                 lease_clock: LeaseClock | None = None) -> None:
        self.config = config
        self.sql = Sql(config)
        self._clock = clock
        self.access = Access(config, lambda: self._clock().astimezone(UTC))
        self.refresher = Refresher(config, self.sql, lambda: self._clock().astimezone(UTC), lease_clock)
        self.history = History(self.sql, self.refresher, lambda: self._clock().astimezone(UTC),
                               Limit(config.cutover_search_in_check_s, config.cutover_search_memory_bytes))
        self.worker = Worker(config, self.sql, self.refresher, self.history, lambda: self._clock().astimezone(UTC))
        self.endpoints = {module.PATH: module for module in discover(endpoints)}

    def setup(self) -> None:
        """The start of the service, before it answers: creates the totals database and tables (idempotent),
        then looks for the cutover in the recorded events, so that the first answer already has it. The search
        is bounded (Config.cutover_search_at_start_s): it runs before the port opens."""
        for name in self.sql.files("schema"):
            self.sql.statements(name)
        try:
            look_for_cutover(self.sql, self._clock(),
                             Limit(self.config.cutover_search_at_start_s, self.config.cutover_search_memory_bytes))
        except Exception:
            # e.g. CVAT has not created its events table yet, or the search reached its limit: the service
            # starts all the same, and the cutover is looked for again by the daily check
            log.exception("could not look for the cutover at start")

    def refresh(self) -> RefreshResult:
        return self.refresher.run()

    def step(self) -> float:
        """One step of the service's loop (see worker.py); returns the seconds to wait before the next."""
        return self.worker.step()

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
