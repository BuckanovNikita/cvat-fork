# SPDX-License-Identifier: MIT

"""GET /api/team-analytics/{status,overview,trends,list,details}.

A request is checked by CVAT's permission system, then answered from the cache or, on a miss, queued
for the app's worker (reads.py). Nothing here queries ClickHouse, and nothing here imports the code
that does: the worker's job is named by its path.
"""

from __future__ import annotations

import logging

import django_rq
from django.conf import settings
from django.core.cache import caches
from django.db import connection
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from redis.exceptions import LockError
from rest_framework import exceptions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rq.job import JobStatus
from rq.utils import utcnow

from cvat.apps.organizations.models import Membership

from . import QUEUE, reads
from .permissions import TeamAnalyticsPermission

log = logging.getLogger(__name__)

READ_JOB = "cvat.apps.team_analytics.jobs.read_answer"
# Roles that read their organization's figures (rules/team_analytics.rego).
READING_ROLES = (Membership.OWNER, Membership.MAINTAINER)
# States of a job that is still going to produce its answer.
_PENDING = (JobStatus.QUEUED, JobStatus.STARTED, JobStatus.DEFERRED, JobStatus.SCHEDULED)
# Beyond the time a job may wait (its time to live) and the time it may run (its timeout): the minute
# rq gives a job that ignores its timeout before it stops it by force, and as much again for clocks of
# API processes that disagree.
_ABANDONED_MARGIN_S = 120


def scope_of(request) -> dict:
    """Whose figures the caller reads, once the permission check has let them in.

    In an organization: that organization's. With no organization only an administrator gets this
    far, and reads instance scope: every organization and personal workspaces together. CVAT itself
    reads "no organization" as the caller's personal workspace; Team Analytics has no figures of
    one workspace, and this is the place where the two differ.
    """
    context = request.iam_context
    organization = context["organization"]
    return {
        "org_id": None if organization is None else organization.id,
        "admin": context["privilege"] == settings.IAM_ADMIN_ROLE,
    }


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
        """A refusal says why in one case: an owner or maintainer who named no organization is told to
        select one. The policy only allows or refuses, so that case is told apart here."""
        if request.authenticators and not request.successful_authenticator:
            raise exceptions.NotAuthenticated()
        if (
            request.iam_context["organization"] is None
            and Membership.objects.filter(
                user=request.user, is_active=True, role__in=READING_ROLES
            ).exists()
        ):
            raise exceptions.PermissionDenied({"error": "organization_required"})
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
