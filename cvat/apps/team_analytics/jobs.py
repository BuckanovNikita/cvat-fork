# SPDX-License-Identifier: MIT

"""The work of the app's worker (`run worker team_analytics`): answers, and the refresh of the totals.

Every query to ClickHouse the feature makes runs in one of these two jobs. Neither lets an exception
out: a failure is logged and shows as an error panel on the Team Analytics page, and CVAT's handlers
for failed jobs never see it.
"""

from __future__ import annotations

import json
import logging

import django_rq
from django.conf import settings
from django.core.cache import caches
from django.db import connection

from . import QUEUE, reads
from .core.config import Config
from .core.engine import Engine
from .core.periods import BadRequest
from .core.redis_lock import RedisLock
from .core.run import WatchedLock, refresh_run
from .core.scope import Scope
from .core.sql import Limit
from .models import TechnicalAccount
from .reads import ANSWER_KEY_PREFIX, GENERATION_KEY, advance_generation

log = logging.getLogger(__name__)

# The id of the periodic refresh job (cvat/settings/base.py).
REFRESH_JOB_ID = "team_analytics_refresh"

# Set once the first job has looked for the cutover in the recorded events. It has no expiry: when
# the cache is emptied the search runs once more.
READY_KEY = "team_analytics:ready"


def config() -> Config:
    clickhouse = settings.CLICKHOUSE["events"]
    return Config(
        clickhouse_host=clickhouse["HOST"],
        clickhouse_port=int(clickhouse["PORT"]),
        clickhouse_user=clickhouse["USER"],
        clickhouse_password=clickhouse["PASSWORD"],
        events_db=clickhouse["NAME"],
        totals_db=settings.TEAM_ANALYTICS_DB,
        refresh_interval_s=settings.TEAM_ANALYTICS_REFRESH_INTERVAL_S,
        refresh_window_hours=settings.TEAM_ANALYTICS_REFRESH_WINDOW_HOURS,
        lookback_s=settings.TEAM_ANALYTICS_LOOKBACK_S,
    )


def technical_account_ids() -> tuple[int, ...]:
    """The user ids on the Technical accounts list, from Postgres (models.TechnicalAccount). The
    database connection is closed right after: the read that follows may take as long as its
    statement limit and needs none (a later use of the ORM in the same process opens a new one)."""
    try:
        return tuple(sorted(TechnicalAccount.objects.values_list("user_id", flat=True)))
    finally:
        connection.close()


def _engine(read_limit: Limit | None = None) -> tuple[Engine, WatchedLock]:
    conf = config()
    lock = WatchedLock(RedisLock(django_rq.get_connection(QUEUE), conf.refresh_lease_s))
    # every statement of a refresh or a day of history is stopped by ClickHouse at this limit: the
    # job's own timeout stops the client only, and the statement would run on without it
    statement_limit = Limit(settings.TEAM_ANALYTICS_REFRESH_STATEMENT_S)
    engine = Engine(conf, lock=lock, read_limit=read_limit, statement_limit=statement_limit)
    return engine, lock


def _make_ready(engine: Engine, cache) -> bool:
    """Before the first answer: the schema exists and the cutover has been looked for. False when
    another job is doing it right now."""
    if cache.get(READY_KEY):
        return True
    engine.create_schema()
    ran, _ = engine.refresher.leased(engine.look_for_cutover)
    if ran:
        cache.set(READY_KEY, 1, None)
        advance_generation(cache)
    return ran


def refresh_totals() -> None:
    """The periodic job, every minute: takes steps (the refresh of recent hours, a day of history, the
    daily check) while there is work, and starts no new step after its budget. Each step takes the
    refresh lock for itself, so two runs never write at once and a run that finds it taken leaves.

    Reads come before history: after a step the run ends as soon as a read is waiting in the queue,
    so that it does not keep a worker process, and ClickHouse, from the people looking at the page.
    The first step of a run is the refresh of recent hours whenever that is due, so it is never put
    off; history goes on at the next run. The rules of a run are core/run.py's.
    """
    cache = caches["default"]
    try:
        queue = django_rq.get_queue(QUEUE)
        # the scheduler queues this job again every minute whether or not the last one was taken: what
        # piled up while no worker ran is one run's work, not many
        queue.connection.lrem(queue.key, 0, REFRESH_JOB_ID)
        engine, lock = _engine()
        # every run: restores a totals database that was removed, and costs nothing when it exists
        engine.create_schema()
        if not _make_ready(engine, cache):
            return
        refresh_run(
            engine.step,
            lock,
            budget_s=settings.TEAM_ANALYTICS_REFRESH_BUDGET_S,
            reads_waiting=lambda: reads.waiting_reads(queue.get_job_ids()) > 0,
            advance_generation=lambda: advance_generation(cache),
        )
    except Exception:
        log.exception("the refresh of the Team Analytics totals failed; the next run tries again")


def read_answer(endpoint: str, scope: dict, query: dict, key: str) -> None:
    """Computes one answer and stores it under `key` for the request that waits for it (reads.fetch)
    and for those that ask again. A parameter the endpoint refuses is an answer too (400). A read
    that failed is remembered for a few seconds as 503."""
    try:
        cache = caches["default"]
        _read_answer(cache, endpoint, scope, query, key)
    except Exception:
        log.exception("a Team Analytics answer could not be computed or stored: %s", endpoint)


def _read_answer(cache, endpoint: str, scope: dict, query: dict, key: str) -> None:
    ttl = settings.TEAM_ANALYTICS_ANSWER_TTL_S
    generation = cache.get(GENERATION_KEY, 0)
    try:
        engine, _ = _engine(
            Limit(
                settings.TEAM_ANALYTICS_READ_STATEMENT_S,
                settings.TEAM_ANALYTICS_READ_STATEMENT_MEMORY_BYTES,
            )
        )
        if not _make_ready(engine, cache):
            return  # the request replies "not ready" and is sent again
        # read before computing: an answer computed while a run was writing is stored as older than
        # the totals that run leaves, and is computed again when it is next asked for
        generation = cache.get(GENERATION_KEY, 0)
        # the list after the generation, never before: a save commits, then advances the generation,
        # so an answer computed on a list read before a save is stored as older than that save
        technical_accounts = technical_account_ids()
        body = engine.answer(
            endpoint,
            Scope(org_id=scope["org_id"], user_id=0, username=""),
            query,
            technical_accounts=technical_accounts,
        )
        stored = {"status": 200, "body": json.dumps(body)}
    except BadRequest as error:
        stored = {"status": 400, "body": json.dumps({"error": "bad_request", "detail": str(error)})}
        ttl = settings.TEAM_ANALYTICS_FAILURE_TTL_S  # computed without a query: not worth keeping
    except Exception:
        log.exception("a Team Analytics read failed: %s", endpoint)
        stored = {"status": 503, "body": json.dumps({"error": "unavailable"})}
        ttl = settings.TEAM_ANALYTICS_FAILURE_TTL_S
    cache.set(ANSWER_KEY_PREFIX + key, {**stored, "generation": generation}, ttl)
