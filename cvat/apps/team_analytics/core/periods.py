"""Periods as half-open spans of whole stored hours (UTC), following the viewer's time zone.

A period is chosen by the query: `period` (a key of `PERIODS`, default `week`), `month` (`YYYY-MM`, only
for `month`; default the viewer's current month) and `tz` (IANA name, default UTC). Days are the viewer's
calendar days; a span starts and ends at the stored hour that holds the viewer's midnight, so a zone
offset by part of an hour gets days assembled from whole hours (accepted in the spec).
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class BadRequest(Exception):
    pass


_DECIMAL = re.compile(r"[0-9]+")


def decimal(text: str, max_digits: int) -> int | None:
    """`text` as a number when it is 1 to `max_digits` ASCII decimal digits, else None.

    Query values are checked with this, not `str.isdigit()`, which also accepts other Unicode digits.
    """
    return int(text) if len(text) <= max_digits and _DECIMAL.fullmatch(text) else None


@dataclass(frozen=True)
class Span:
    start: datetime  # inclusive, UTC, whole hour
    end: datetime  # exclusive, UTC, whole hour
    name: str = "week"
    tz: str = "UTC"
    first_day: date | None = None  # the viewer's first calendar day of the period
    last_day: date | None = None  # the viewer's last calendar day (today for a period ending today)
    month: str | None = None  # YYYY-MM for a month
    to_date: bool = False  # the period is still running (the current month)
    unit: str = "day"  # the step of the time chart: day, or week for long periods

    def params(self) -> dict[str, str]:
        return {
            "from": self.start.strftime("%Y-%m-%d %H:%M:%S"),
            "to": self.end.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def day_params(self) -> dict[str, str | int]:
        """For reads laid out per viewer day: the span plus the days, the zone and the step."""
        return {
            **self.params(),
            "tz": self.tz,
            "first_day": self.first_day.isoformat(),
            "last_day": self.last_day.isoformat(),
            "weekly": 1 if self.unit == "week" else 0,
        }

    def describe(self) -> dict:
        """The period as responses echo it."""
        return {
            "from": self.start.isoformat(),
            "to": self.end.isoformat(),
            "name": self.name,
            "tz": self.tz,
            "first_day": self.first_day.isoformat(),
            "last_day": self.last_day.isoformat(),
            "month": self.month,
            "to_date": self.to_date,
            "unit": self.unit,
        }


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise BadRequest(f"unknown time zone: {name}") from error


def hour_floor(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def midnight(day: date, tz: ZoneInfo) -> datetime:
    """The stored hour (UTC) holding the viewer's midnight at the start of `day`."""
    return hour_floor(datetime.combine(day, time(0), tzinfo=tz))


def today(now: datetime, tz: ZoneInfo) -> date:
    return now.astimezone(tz).date()


def months_before(day: date, months: int) -> date:
    """The same day `months` calendar months earlier, or that month's last day when it is shorter."""
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _ending_today(name: str, first_day: Callable[[date], date], unit: str = "day"):
    def build(now: datetime, tz: ZoneInfo, tz_name: str, _month: str | None) -> Span:
        last = today(now, tz)
        first = first_day(last)
        return Span(
            start=midnight(first, tz),
            end=hour_floor(now) + timedelta(hours=1),
            name=name,
            tz=tz_name,
            first_day=first,
            last_day=last,
            unit=unit,
        )

    return build


_MONTH = re.compile(r"([0-9]{4})-([0-9]{2})")


def _month(now: datetime, tz: ZoneInfo, tz_name: str, month: str | None) -> Span:
    current = today(now, tz)
    if month:
        match = _MONTH.fullmatch(month)
        # ClickHouse dates start in 1970, so no earlier month can hold figures
        if not match or not 1 <= int(match.group(2)) <= 12 or int(match.group(1)) < 1970:
            raise BadRequest(f"not a month (YYYY-MM): {month}")
        first = date(int(match.group(1)), int(match.group(2)), 1)
    else:
        first = current.replace(day=1)
    if first > current:
        raise BadRequest(f"month not reached yet: {month}")
    following = date(first.year + first.month // 12, first.month % 12 + 1, 1)
    to_date = following > current
    if to_date:
        last, end = current, hour_floor(now) + timedelta(hours=1)
    else:
        last, end = following - timedelta(days=1), midnight(following, tz)
    return Span(
        start=midnight(first, tz),
        end=end,
        name="month",
        tz=tz_name,
        first_day=first,
        last_day=last,
        month=first.strftime("%Y-%m"),
        to_date=to_date,
    )


# Period key -> builder(now, tz, tz name, month) -> Span. Week and Two weeks end today; Month is one
# calendar month; Year is the last twelve months ending today, laid out in Monday weeks.
PERIODS = {
    "week": _ending_today("week", lambda last: last - timedelta(days=6)),
    "two_weeks": _ending_today("two_weeks", lambda last: last - timedelta(days=13)),
    "month": _month,
    "year": _ending_today(
        "year", lambda last: months_before(last, 12) + timedelta(days=1), unit="week"
    ),
}


def period_span(now: datetime, period: str, tz_name: str, month: str | None = None) -> Span:
    tz = zone(tz_name)
    if period not in PERIODS:
        raise BadRequest(f"unknown period: {period}")
    return PERIODS[period](now, tz, tz_name or "UTC", month)
