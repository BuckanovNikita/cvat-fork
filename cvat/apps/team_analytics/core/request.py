"""What an endpoint gets, and how endpoints and their sections are found."""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import cache
from types import ModuleType
from typing import Any

from .config import Config
from .cutover import Legacy, load_cutover
from .history import HistoryState, load_state
from .periods import BadRequest, Span, decimal, period_span
from .scope import Scope
from .sql import Sql

# values of the `shapes` query parameter (the page's Bounding boxes / All shapes switch)
SHAPES_BOUNDING_BOXES = "bounding_boxes"
SHAPES_ALL = "all"


def utc_now() -> datetime:
    return datetime.now(UTC)


@cache
def discover(package: ModuleType) -> tuple[ModuleType, ...]:
    """The modules of `package` (endpoints, overview or status sections), found once."""
    return tuple(
        importlib.import_module(f"{package.__name__}.{info.name}")
        for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda info: info.name)
    )


@dataclass
class Request:
    """What an endpoint gets: the caller's scope (from CVAT), the query, and the means to read.
    `technical_accounts`: the user ids of the accounts that stand for automated processes, for this
    answer."""

    scope: Scope
    query: dict[str, str]
    sql: Sql
    config: Config
    now: datetime
    technical_accounts: tuple[int, ...]
    cache: dict[str, Any] = field(default_factory=dict)

    def span(self) -> Span:
        return period_span(
            self.now,
            self.query.get("period", "week"),
            self.query.get("tz", "UTC"),
            self.query.get("month"),
        )

    def cutover(self) -> datetime | None:
        """The cutover to the new activity logging (cutover.py), read once per request."""
        if "cutover" not in self.cache:
            self.cache["cutover"] = load_cutover(self.sql)
        return self.cache["cutover"]

    def history(self) -> HistoryState:
        """How far history is processed (history.py), read once per request.

        An endpoint that answers with figures calls this before its first figure read. A history step that
        finishes after this reading can then only have made the figures more complete than the state says,
        never the reverse: the answer may say `processed: false` where it could have said true, but never
        sends figures read before the step as processed."""
        if "history" not in self.cache:
            self.cache["history"] = load_state(self.sql, self.now)
        return self.cache["history"]

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
            "technical_accounts": list(self.technical_accounts),
            "has_project": 0 if project is None else 1,
            "project": project or 0,
            "has_annotator": 0 if annotator is None else 1,
            "annotator": annotator or 0,
            # shape switch: a read file of an operation figure keeps `shape = 'bounding_box'` rows when 1
            # (unless the period is legacy: pass request.legacy(...).params() too); see read/overview_operations.sql
            "bounding_boxes": 1 if self.shapes() == SHAPES_BOUNDING_BOXES else 0,
        }
