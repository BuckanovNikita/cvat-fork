"""Who may read what: asks CVAT, with the caller's own credentials, and decides the scope.

Rules: a member of CVAT's admin group may read the named organization, or instance scope when none
is named. An owner or maintainer may read their organization. Everyone else is refused, including
an owner or maintainer who names no organization (they are asked to select one; anyone else
without an organization is simply refused). The organization id every query is limited to comes
from CVAT's answers, never from the request.

CVAT's successful answers are reused for at most `ANSWER_TTL` per caller: the cache key is the
exact credentials forwarded plus the path and parameters asked, and an entry is never renewed by
use. Failures are never cached, so an unreachable CVAT after the minute means a refusal.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import requests

from team_analytics.config import Config

FORWARDED_HEADERS = ("Cookie", "Authorization")
READING_ROLES = ("owner", "maintainer")
ANSWER_TTL = timedelta(minutes=1)


@dataclass(frozen=True)
class Scope:
    """`org_id` None means instance scope (every organization and personal workspaces). `admin`: the caller
    is in CVAT's admin group, whether or not an organization is named."""

    org_id: int | None
    user_id: int
    username: str
    admin: bool = False

    @property
    def instance(self) -> bool:
        return self.org_id is None


class Refused(Exception):
    """The caller may not read. `status` and `reason` go into the response."""

    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


class Access:
    def __init__(self, config: Config, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._config = config
        self._clock = clock
        self._lock = threading.Lock()
        # key -> (fetched at, CVAT's answer)
        self._answers: dict[str, tuple[datetime, dict[str, Any]]] = {}

    def scope(self, headers: dict[str, str], org_slug: str) -> Scope:
        credentials = {name: headers.get(name) for name in FORWARDED_HEADERS if headers.get(name)}
        if not credentials:
            raise Refused(401, "not_authenticated")
        me = self._get("/api/users/self", credentials, {})
        user_id, username = me["id"], me["username"]
        is_admin = "admin" in (me.get("groups") or [])  # a list of names (checked in _usable)
        if not org_slug:
            if is_admin:
                return Scope(org_id=None, user_id=user_id, username=username, admin=True)
            # Without an organization CVAT lists only the caller's own active memberships. An
            # owner or maintainer of some organization is asked to select it; anyone else is refused.
            # CVAT pages the list, so it is asked per reading role (its `role` filter): any row of the
            # first page answers, however many other memberships the caller has.
            for role in READING_ROLES:
                memberships = self._get("/api/memberships", credentials, {"user": username, "role": role})
                if any(self._reads(membership, user_id) for membership in memberships["results"]):
                    raise Refused(403, "organization_required")
            raise Refused(403, "forbidden")

        organizations = self._get("/api/organizations", credentials, {"slug": org_slug})
        matches = [org for org in organizations["results"] if org["slug"] == org_slug]
        if len(matches) != 1:
            raise Refused(403, "forbidden")
        org_id = matches[0]["id"]
        if is_admin:
            return Scope(org_id=org_id, user_id=user_id, username=username, admin=True)

        memberships = self._get("/api/memberships", credentials, {"org": org_slug, "user": username})
        for membership in memberships["results"]:
            if self._reads(membership, user_id) and membership.get("organization") == org_id:
                return Scope(org_id=org_id, user_id=user_id, username=username)
        raise Refused(403, "forbidden")

    @staticmethod
    def _reads(membership: dict[str, Any], user_id: int) -> bool:
        """An active owner or maintainer membership of the caller."""
        return (
            (membership.get("user") or {}).get("id") == user_id
            and membership.get("is_active") is True
            and membership.get("role") in READING_ROLES
        )

    def _get(self, path: str, credentials: dict[str, str], params: dict[str, str]) -> dict[str, Any]:
        # hashed so the cache holds no credentials; any difference in them is a different caller
        key = hashlib.sha256(json.dumps([credentials, path, params], sort_keys=True).encode()).hexdigest()
        now = self._clock()
        with self._lock:
            cached = self._answers.get(key)
        if cached is not None and timedelta(0) <= now - cached[0] < ANSWER_TTL:
            return cached[1]
        answer = self._ask(path, credentials, params)
        with self._lock:
            self._answers = {k: v for k, v in self._answers.items() if timedelta(0) <= now - v[0] < ANSWER_TTL}
            self._answers[key] = (now, answer)
        return answer

    def _ask(self, path: str, credentials: dict[str, str], params: dict[str, str]) -> dict[str, Any]:
        try:
            response = requests.get(
                # no Accept header: CVAT's API answers a plain application/json with 406
                f"{self._config.cvat_url}{path}", headers=credentials,
                params={**params, "page_size": 100} if path != "/api/users/self" else params,
                timeout=self._config.cvat_timeout_s, allow_redirects=False,
            )
        except requests.RequestException as error:
            raise Refused(503, "cvat_unavailable") from error
        if response.status_code == 401:
            raise Refused(401, "not_authenticated")
        if response.status_code in (403, 404):
            raise Refused(403, "forbidden")
        if response.status_code != 200:
            raise Refused(503, "cvat_unavailable")
        try:
            answer = response.json()
        except ValueError as error:
            raise Refused(503, "cvat_unavailable") from error
        # an answer the rules cannot be applied to is a refusal, and is never cached
        if not _usable(path, answer):
            raise Refused(503, "cvat_unavailable")
        return answer


def _is_id(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _usable(path: str, answer: Any) -> bool:
    """Whether CVAT's 200 answer has the shape `Access.scope` reads."""
    if not isinstance(answer, dict):
        return False
    if path == "/api/users/self":
        groups = answer.get("groups")
        return (_is_id(answer.get("id")) and isinstance(answer.get("username"), str)
                and (groups is None or (isinstance(groups, list) and all(isinstance(g, str) for g in groups))))
    results = answer.get("results")
    if not isinstance(results, list) or not all(isinstance(row, dict) for row in results):
        return False
    if path == "/api/organizations":
        return all(_is_id(row.get("id")) and isinstance(row.get("slug"), str) for row in results)
    if path == "/api/memberships":
        return all(isinstance(row.get("user") or {}, dict) for row in results)
    return True
