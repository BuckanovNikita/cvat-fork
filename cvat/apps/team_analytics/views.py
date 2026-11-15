# SPDX-License-Identifier: MIT

"""/api/team-analytics/: the figures and the settings of Team Analytics, for administrators only.

GET status, overview, trends, list and details: a request is checked by CVAT's permission system,
then answered from the cache or, on a miss, queued for the app's worker (reads.py). Nothing here
queries ClickHouse, and nothing here imports the code that does: the worker's job is named by its
path.

GET and PUT settings (the Technical accounts list), GET settings/users (the user search of the
settings screen) and GET project-names: answered here from Postgres, never through the queue
(technical_accounts.py has the rules).
"""

from __future__ import annotations

import logging

import django_rq
from django.conf import settings
from django.core.cache import caches
from django.db import connection, transaction
from django.db.models import Q
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from redis.exceptions import LockError
from rest_framework import exceptions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rq.job import JobStatus
from rq.utils import utcnow

from cvat.apps.engine.models import Project
from cvat.apps.iam.models import User

from . import QUEUE, reads
from . import technical_accounts as rules
from .models import TechnicalAccount
from .permissions import TeamAnalyticsPermission
from .serializers import (
    ProjectNamesSerializer,
    TechnicalAccountsWriteSerializer,
    UserSearchSerializer,
    first_error,
)

log = logging.getLogger(__name__)

READ_JOB = "cvat.apps.team_analytics.jobs.read_answer"
# States of a job that is still going to produce its answer.
_PENDING = (JobStatus.QUEUED, JobStatus.STARTED, JobStatus.DEFERRED, JobStatus.SCHEDULED)
# Beyond the time a job may wait (its time to live) and the time it may run (its timeout): the minute
# rq gives a job that ignores its timeout before it stops it by force, and as much again for clocks of
# API processes that disagree.
_ABANDONED_MARGIN_S = 120


def scope_of(request) -> dict:
    """Whose figures the caller reads, once the permission check has let them in.

    Only administrators get this far (rules/team_analytics.rego). With an organization selected they
    read that organization's figures; with none, instance scope: every organization and personal
    workspaces together. CVAT itself reads "no organization" as the caller's personal workspace;
    Team Analytics has no figures of one workspace, and this is the place where the two differ.
    """
    organization = request.iam_context["organization"]
    return {"org_id": None if organization is None else organization.id}


def enqueue_read(job_id: str, endpoint: str, scope: dict, query: dict, key: str) -> bool:
    """Queues one read for the worker; see reads.Enqueue. One job per key: a job that is waiting or
    running is left alone, unless it has been so for longer than a read may take. Its worker is gone
    then, and the read is queued again."""
    queue = django_rq.get_queue(QUEUE)
    try:
        with queue.connection.lock(
            f"lock-for-{job_id}", timeout=10, blocking_timeout=reads.ENQUEUE_LOCK_WAIT_S
        ):
            job = queue.fetch_job(job_id)
            if job is not None and job.get_status(refresh=False) in _PENDING:
                if not _abandoned(job):
                    return True
                job.delete()
            waiting = reads.waiting_reads(queue.get_job_ids())
            if waiting >= settings.TEAM_ANALYTICS_READ_QUEUE_LIMIT:
                return False
            queue.enqueue(
                READ_JOB,
                endpoint,
                scope,
                query,
                key,
                job_id=job_id,
                job_timeout=settings.TEAM_ANALYTICS_READ_JOB_TIMEOUT_S,
                # a read nobody collected in time is not worth starting: its request has replied
                ttl=settings.TEAM_ANALYTICS_READ_JOB_TIMEOUT_S,
                result_ttl=0,
                failure_ttl=60,
            )
            return True
    except LockError:
        return False


def _abandoned(job) -> bool:
    """A job that should have ended long ago: it waits in the queue no longer than its time to live,
    and runs no longer than its timeout."""
    queued_at = job.enqueued_at
    if queued_at is None:
        return False
    limit_s = 2 * settings.TEAM_ANALYTICS_READ_JOB_TIMEOUT_S + _ABANDONED_MARGIN_S
    return (utcnow() - queued_at).total_seconds() > limit_s


@extend_schema(exclude=True)
class TeamAnalyticsViewSet(viewsets.ViewSet):
    serializer_class = None
    iam_supports_organization_params = False
    iam_permission_class = TeamAnalyticsPermission

    def permission_denied(self, request, message=None, code=None):
        """A caller who is not signed in is told so (401); every other refusal is the plain 403."""
        if request.authenticators and not request.successful_authenticator:
            raise exceptions.NotAuthenticated()
        raise exceptions.PermissionDenied(detail=message, code=code)

    def finalize_response(self, request, response, *args, **kwargs):
        """No answer of this view set is kept by a browser or a proxy, a refusal included."""
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    def _answer(self, request, endpoint: str):
        try:
            query = reads.clean_query(endpoint, request.query_params.dict())
        except reads.QueryRefused as error:
            return self._json(
                status.HTTP_400_BAD_REQUEST, {"error": "bad_request", "detail": str(error)}
            )
        try:
            answer = reads.fetch(
                endpoint,
                scope_of(request),
                query,
                cache=caches["default"],
                enqueue=enqueue_read,
                wait_s=settings.TEAM_ANALYTICS_READ_WAIT_S,
                retry_after_s=settings.TEAM_ANALYTICS_READ_RETRY_AFTER_S,
                # the permission check is done: the wait needs no database connection
                before_wait=connection.close,
            )
        except Exception:
            # the cache or the queue cannot be reached, or holds something unreadable: no figures, and
            # no error of CVAT's own
            log.exception("Team Analytics could not use its cache or its queue")
            return self._json(status.HTTP_503_SERVICE_UNAVAILABLE, {"error": "unavailable"})
        if answer.body is None:
            return self._json(answer.status, None, {"Retry-After": str(answer.retry_after_s)})
        # the worker's JSON text, sent as it is
        return HttpResponse(answer.body, status=answer.status, content_type="application/json")

    @staticmethod
    def _json(code: int, body, headers: dict | None = None) -> Response:
        return Response(body, status=code, headers=headers)

    @action(detail=False, methods=["GET"], url_path="status")
    def status(self, request):
        return self._answer(request, "status")

    @action(detail=False, methods=["GET"], url_path="overview")
    def overview(self, request):
        return self._answer(request, "overview")

    @action(detail=False, methods=["GET"], url_path="trends")
    def trends(self, request):
        return self._answer(request, "trends")

    @action(detail=False, methods=["GET"], url_path="list")
    def list_rows(self, request):
        return self._answer(request, "list")

    @action(detail=False, methods=["GET"], url_path="details")
    def details(self, request):
        return self._answer(request, "details")

    # DRF's APIView has an attribute `settings`: the action is named otherwise
    @action(detail=False, methods=["GET", "PUT"], url_path="settings")
    def team_settings(self, request):
        if request.method == "PUT":
            return self._save_settings(request)
        return Response(_settings_answer())

    def _save_settings(self, request):
        # a body that is not JSON, or not sent as JSON, is told in the app's own form, not DRF's
        try:
            data = request.data
        except (exceptions.ParseError, exceptions.UnsupportedMediaType) as error:
            return self._refuse(f"the body could not be read: {error.detail}")
        body = TechnicalAccountsWriteSerializer(data=data)
        if not body.is_valid():
            return self._refuse(first_error(body.errors))
        ids = body.validated_data["technical_accounts"]
        # what the callback after the commit did: None while it has not run
        advanced: dict[str, bool | None] = {"advanced": None}
        try:
            with transaction.atomic():
                added, removed = _replace_technical_accounts(ids)
                # after the commit, never before: a read that starts in between must not store an
                # answer computed on the old list under the new generation
                transaction.on_commit(
                    lambda: advanced.update(advanced=_after_save(request.user, added, removed))
                )
        except rules.Refused as error:
            return self._refuse(str(error))
        outcome = rules.save_outcome(advanced["advanced"])
        if outcome == rules.SAVE_NOT_ANNOUNCED:
            log.error(
                "the Technical accounts list was saved, but nothing ran after the commit: the answer "
                "generation was not advanced"
            )
        if outcome != rules.SAVE_DONE:
            return self._json(status.HTTP_503_SERVICE_UNAVAILABLE, {"error": "unavailable"})
        return Response(_settings_answer())

    @staticmethod
    def _refuse(detail: str) -> Response:
        return Response(
            {"error": "bad_request", "detail": detail}, status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=False, methods=["GET"], url_path="settings/users")
    def settings_users(self, request):
        query = UserSearchSerializer(data=request.query_params)
        if not query.is_valid():
            return self._refuse(first_error(query.errors))
        text = query.validated_data["search"]
        users = User.objects.all()
        if text:
            users = users.filter(
                Q(username__icontains=text)
                | Q(first_name__icontains=text)
                | Q(last_name__icontains=text)
            )
        found = users.order_by("username").values("id", "username", "first_name", "last_name")
        return Response({"users": list(found[: rules.SEARCH_LIMIT])})

    @action(detail=False, methods=["GET"], url_path="project-names")
    def project_names(self, request):
        query = ProjectNamesSerializer(data=request.query_params)
        if not query.is_valid():
            return self._refuse(first_error(query.errors))
        names = Project.objects.filter(id__in=query.validated_data["ids"]).values_list("id", "name")
        return Response({"names": {str(project_id): name for project_id, name in names}})


def _settings_answer() -> dict:
    """The Technical accounts list with the current names of the users that still exist."""
    stored = dict(TechnicalAccount.objects.values_list("user_id", "user_name"))
    live = dict(User.objects.filter(id__in=stored).values_list("id", "username"))
    return {"technical_accounts": rules.listing(stored, live)}


def _after_save(user, added: list[int], removed: list[int]) -> bool:
    """Once a save is committed: logs who changed what, and advances the answer generation so that
    no answer computed on the old list is used again. False when the generation could not be
    advanced: the list is saved, and older answers are used until the totals next change."""
    log.info(
        "Team Analytics technical accounts changed by %s (user %s): added %s, removed %s",
        user.username,
        user.id,
        added,
        removed,
    )
    try:
        reads.advance_generation(caches["default"])
    except Exception:
        log.exception(
            "the Technical accounts list was saved, but the answer generation was not advanced"
        )
        return False
    return True


def _replace_technical_accounts(ids: list[int]) -> tuple[list[int], list[int]]:
    """Replaces the whole list with `ids` (technical_accounts.check_new_ids decides which may be
    added), storing each user's current name or, for a user that is gone, its last known one.
    Returns the ids added and removed. Runs inside the caller's transaction; two saves at once take
    turns: the table is locked against other writers until it ends, readers are not held up."""
    table = connection.ops.quote_name(TechnicalAccount._meta.db_table)
    with connection.cursor() as cursor:
        cursor.execute(f"LOCK TABLE {table} IN EXCLUSIVE MODE")
    stored = dict(TechnicalAccount.objects.values_list("user_id", "user_name"))
    live = dict(User.objects.filter(id__in=ids).values_list("id", "username"))
    rules.check_new_ids(ids, listed=stored, existing=live)
    names = rules.names_to_store(ids, stored, live)
    TechnicalAccount.objects.exclude(user_id__in=ids).delete()
    changed = [
        TechnicalAccount(user_id=user_id, user_name=name)
        for user_id, name in names.items()
        if stored.get(user_id) != name
    ]
    TechnicalAccount.objects.bulk_create(
        changed,
        update_conflicts=True,
        unique_fields=["user_id"],
        update_fields=["user_name", "updated_date"],
    )
    return rules.changes(stored, ids)
