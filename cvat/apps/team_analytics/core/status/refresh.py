"""Freshness: when the last refresh succeeded, by the worker's clock, and whether that is too long ago."""

from __future__ import annotations

from datetime import UTC, timedelta

from ..request import Request

KEY = "refresh"

# The page warns once the figures are older than this.
STALE_AFTER = timedelta(minutes=30)


def build(request: Request) -> dict:
    last = request.sql.rows("read/status_last_refresh.sql")[0]["last_success_at"]
    if last is not None:
        last = (last if last.tzinfo else last.replace(tzinfo=UTC)).astimezone(UTC)
    return {
        "last_success_at": last.isoformat() if last else None,
        "now": request.now.isoformat(),
        "interval_s": request.config.refresh_interval_s,
        "stale_after_s": int(STALE_AFTER.total_seconds()),
        "stale": last is None or request.now - last > STALE_AFTER,
    }
