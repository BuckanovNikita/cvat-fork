"""Periods as half-open spans of whole stored hours (UTC), following the viewer's time zone."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class BadRequest(Exception):
    pass


@dataclass(frozen=True)
class Span:
    start: datetime  # inclusive, UTC, whole hour
    end: datetime  # exclusive, UTC, whole hour

    def params(self) -> dict[str, str]:
        return {"from": self.start.strftime("%Y-%m-%d %H:%M:%S"), "to": self.end.strftime("%Y-%m-%d %H:%M:%S")}


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise BadRequest(f"unknown time zone: {name}") from error


def _hour_floor(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def last_days(now: datetime, days: int, tz: ZoneInfo) -> Span:
    """The last `days` days of the viewer's calendar, today included, up to the current hour."""
    today = now.astimezone(tz).date()
    first = datetime.combine(today - timedelta(days=days - 1), time(0), tzinfo=tz)
    return Span(start=_hour_floor(first), end=_hour_floor(now) + timedelta(hours=1))


PERIODS = {"week": 7}


def period_span(now: datetime, period: str, tz_name: str) -> Span:
    tz = zone(tz_name)
    if period not in PERIODS:
        raise BadRequest(f"unknown period: {period}")
    return last_days(now, PERIODS[period], tz)
