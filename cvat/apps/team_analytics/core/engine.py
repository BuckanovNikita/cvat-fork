"""Team Analytics put together: the SQL runner, the refresh of the stored totals, history, the prioritised
step and the endpoints, on one configuration and one clock. The backend's worker jobs build one per job;
nothing here knows who the caller is or how a request arrived."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime

from . import endpoints
from .config import Config
from .cutover import look_for_cutover
from .history import History
from .refresh import Refresher, RefreshLock, RefreshResult
from .request import Request, discover, utc_now
from .scope import Scope
from .sql import Limit, Sql
from .worker import Worker

log = logging.getLogger(__name__)


class UnknownEndpoint(LookupError):
    pass


class Engine:
    def __init__(
        self,
        config: Config,
        lock: RefreshLock,
        clock: Callable[[], datetime] = utc_now,
        read_limit: Limit | None = None,
        statement_limit: Limit | None = None,
    ) -> None:
        """`lock`: what lets one step run at a time. `read_limit`: what ClickHouse allows each statement of
        an answer. `statement_limit`: what it allows every other statement that has no limit of its own
        (a refresh, a day of history). No limit when None."""
        self.config = config
        self.sql = Sql(config, read_limit, statement_limit)
        self._clock = clock
        self.refresher = Refresher(config, self.sql, self.now, lock)
        self.history = History(
            self.sql,
            self.refresher,
            self.now,
            Limit(config.cutover_search_in_check_s, config.cutover_search_memory_bytes),
        )
        self.worker = Worker(config, self.sql, self.refresher, self.history, self.now)
        self.endpoints = {module.PATH: module for module in discover(endpoints)}

    def now(self) -> datetime:
        return self._clock().astimezone(UTC)

    def create_schema(self) -> None:
        """Creates the totals database and its tables; changes nothing that exists."""
        for name in self.sql.files("schema"):
            self.sql.statements(name)

    def look_for_cutover(self) -> None:
        """Looks for the cutover in the recorded events, within the limit of a search at start, so that
        the first answer already has it. A search that fails is left to the daily check."""
        try:
            look_for_cutover(
                self.sql,
                self._clock(),
                Limit(
                    self.config.cutover_search_at_start_s, self.config.cutover_search_memory_bytes
                ),
            )
        except Exception:
            # e.g. CVAT has not created its events table yet, or the search reached its limit
            log.exception("could not look for the cutover at start")

    def setup(self) -> None:
        self.create_schema()
        self.look_for_cutover()

    def refresh(self) -> RefreshResult:
        return self.refresher.run()

    def step(self) -> float:
        """One step (see worker.py); returns the seconds to wait before the next."""
        return self.worker.step()

    def answer(
        self,
        endpoint: str,
        scope: Scope,
        query: dict[str, str],
        *,
        technical_accounts: tuple[int, ...],
    ) -> dict:
        """What `endpoint` answers for `scope` and `query`, with the user ids of the technical accounts
        as they were read for this answer (the backend keeps the list; nothing here reads it). Raises
        `periods.BadRequest` for a parameter it refuses."""
        module = self.endpoints.get(endpoint)
        if module is None:
            raise UnknownEndpoint(endpoint)
        request = Request(
            scope=scope,
            query=query,
            sql=self.sql,
            config=self.config,
            now=self.now(),
            technical_accounts=tuple(technical_accounts),
        )
        return module.handle(request)
