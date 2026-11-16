# SPDX-License-Identifier: MIT

"""How the API process gets an answer without querying ClickHouse.

An answer is looked up in the cache under a key that names the request: the endpoint, whose figures,
the parameters and the hour. The worker stores each answer with the generation of the totals it was
computed on. A stored answer is used only while that generation is still the current one. Otherwise
the read is queued for the app's worker (jobs.read_answer), one job per request key, and the request
waits a short time for an answer computed since it arrived; if none comes, the caller is told to
retry. This module never computes an answer
and imports nothing that connects to ClickHouse.

The cache and the queue are passed in, so the rules here are tested without Redis.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

# The generation of the totals: a counter the worker sets higher after every run that wrote totals
# (advance_generation), so answers computed before it are no longer used. Absent until the first: 0
# stands for it.
GENERATION_KEY = "team_analytics:generation"
ANSWER_KEY_PREFIX = "team_analytics:answer:"
JOB_ID_PREFIX = "team-analytics-read-"

# The query parameters each endpoint reads (core/endpoints and what they call). Anything else is dropped
# before the key is built: a parameter an endpoint does not read can neither reach the worker nor make
# a second cache entry, and a second job, for the same answer. A test of the calculation suite holds
# this list to what the endpoints really read.
_PERIOD = ("period", "tz", "month")
_FILTERS = ("project", "annotator", "shapes")
ENDPOINT_PARAMETERS = {
    "status": ("tz",),
    "overview": (*_PERIOD, *_FILTERS),
    "list": (*_PERIOD, *_FILTERS, "by"),
    "details": (*_PERIOD, *_FILTERS, "by", "page", "search", "ids"),
    "trends": ("tz", *_FILTERS, "step", "compare", "ids"),
}
# The longest value each parameter may have. They are what a valid value needs: an answer to a refused
# value repeats it, and every value is kept in the job and in the key's making. `ids` carries up to
# 5,000 identifiers of up to 19 digits.
MAX_LENGTH = {
    "period": 16,
    "tz": 64,
    "month": 7,
    "project": 19,
    "annotator": 19,
    "shapes": 16,
    "by": 16,
    "page": 9,
    "search": 200,
    "ids": 100_000,
    "step": 16,
    "compare": 16,
}

# Seconds between two looks into the cache while a request waits.
POLL_S = 0.05
# How long the enqueueing of one key may wait for another request that is enqueueing the same key.
ENQUEUE_LOCK_WAIT_S = 1.0


@dataclass(frozen=True)
class Answer:
    """What a request replies: an HTTP status and, when the worker produced one, the body as JSON text."""

    status: int
    body: str | None = None
    retry_after_s: int | None = None


class Cache(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...


class Enqueue(Protocol):
    def __call__(self, job_id: str, endpoint: str, scope: dict, query: dict, key: str) -> bool:
        """Queues the read unless a job for this key is already waiting or running. False when it
        could not (the queue is full, or the queue could not be reached in time)."""
        ...


class QueryRefused(ValueError):
    """A parameter value the API process does not pass on."""


def clean_query(endpoint: str, query: Mapping[str, str]) -> dict[str, str]:
    """The parameters `endpoint` reads, and no others. Their meaning is checked by the worker; a value
    longer than any valid one is refused here."""
    cleaned = {}
    for name in ENDPOINT_PARAMETERS[endpoint]:
        if name not in query:
            continue
        value = query[name]
        if len(value) > MAX_LENGTH[name]:
            raise QueryRefused(f"{name} is too long")
        cleaned[name] = value
    return cleaned


def waiting_reads(job_ids: Iterable[str]) -> int:
    """How many of the queue's waiting jobs are reads. The periodic refresh job waits in the same queue,
    and several copies of it when no worker ran for a while: they are not reads."""
    return sum(1 for job_id in job_ids if job_id.startswith(JOB_ID_PREFIX))


def advance_generation(cache: Any) -> None:
    """Sets the generation of the totals higher: answers computed so far are no longer used. It is a
    counter kept in the cache, so it only grows and no worker's clock decides between two answers.

    When there is no counter it starts at the current time in seconds, not at 1: a counter that was
    lost while answers stayed in the cache then starts above every generation those answers carry (it
    grows by one for a run, less often than a second passes), and none of them is taken for new."""
    try:
        cache.incr(GENERATION_KEY)
    except ValueError:  # no generation yet
        if not cache.add(GENERATION_KEY, int(time.time()), None):
            cache.incr(GENERATION_KEY)  # another worker stored the first one just now


def request_key(
    endpoint: str, scope: Mapping[str, Any], query: Mapping[str, str], hour: str
) -> str:
    """Names one request: the endpoint, whose figures (the organization, or the whole instance), the
    parameters and the hour (a period ends at the current hour). Who asks is not part of it: only
    administrators read, and they all get the same answer for the same scope. The state of the
    totals is not part of it either: it is stored with the answer, so a request that asks again
    while the totals move still finds the one job and the one entry of its request."""
    parts = [
        endpoint,
        scope["org_id"],
        sorted(query.items()),
        hour,
    ]
    return hashlib.sha256(json.dumps(parts, separators=(",", ":")).encode()).hexdigest()


def current_hour() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H")


def fetch(
    endpoint: str,
    scope: Mapping[str, Any],
    query: Mapping[str, str],
    *,
    cache: Cache,
    enqueue: Enqueue,
    wait_s: float,
    retry_after_s: int,
    hour: Callable[[], str] = current_hour,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    before_wait: Callable[[], None] = lambda: None,
) -> Answer:
    """The answer for one request: from the cache, or after queueing it and waiting up to `wait_s`.

    A stored answer is taken as it is only when it was computed on the current generation of the
    totals. A request that waits takes any answer computed on the generation it saw when it arrived
    or a later one: a step that writes during the wait does not send it back to the queue.

    `before_wait` is called once, when the request is about to wait: the place to let go of what the
    request holds and does not need while it waits."""
    generation = cache.get(GENERATION_KEY, 0)
    key = request_key(endpoint, scope, query, hour())
    cache_key = ANSWER_KEY_PREFIX + key

    stored = cache.get(cache_key)
    if stored is not None and stored["generation"] == generation:
        return Answer(stored["status"], stored["body"])

    not_ready = Answer(429, retry_after_s=retry_after_s)
    if not enqueue(JOB_ID_PREFIX + key, endpoint, dict(scope), dict(query), key):
        return not_ready

    deadline = monotonic() + wait_s
    if monotonic() < deadline:
        before_wait()
    while monotonic() < deadline:
        sleep(POLL_S)
        stored = cache.get(cache_key)
        if stored is not None and stored["generation"] >= generation:
            return Answer(stored["status"], stored["body"])
    return not_ready
