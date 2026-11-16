# SPDX-License-Identifier: MIT

"""The rules of the Team Analytics settings: the Technical accounts list and the two lookups the
settings screen and the page use (user search, project names).

The Technical accounts list is one list for the instance, kept in Postgres by user id with the last
known user name (models.TechnicalAccount). A user deleted from CVAT stays on the list until someone
removes it. Membership is applied when figures are read, so a change applies to every past period
on the next read.

Pure functions only, without Django: the view set (views.py) and the serializers (serializers.py)
call them, and the calculation suite tests them without a configured Django.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

# The longest the list may be.
MAX_ACCOUNTS = 1000
# The largest id Postgres keeps in a bigint column (and ClickHouse's UInt64 holds).
MAX_ID = 2**63 - 1
# The user search: the longest text (Django's username length) and how many users it returns.
SEARCH_MAX_LENGTH = 150
SEARCH_LIMIT = 20
# The project names lookup: how many ids one request may name.
MAX_PROJECT_IDS = 500


class Refused(ValueError):
    """A value the settings API does not accept; the message is the sentence the caller is told."""


def clean_account_ids(value: Any) -> list[int]:
    """The ids of a whole Technical accounts list as a client sends it: a list of positive integers
    without duplicates, at most MAX_ACCOUNTS of them. Order is kept."""
    if not isinstance(value, list):
        raise Refused("technical_accounts must be a list of user ids")
    if len(value) > MAX_ACCOUNTS:
        raise Refused(f"technical_accounts may name at most {MAX_ACCOUNTS} users")
    seen: set[int] = set()
    for item in value:
        # bool is an int in Python, and JSON's true must not stand for user 1
        if isinstance(item, bool) or not isinstance(item, int) or not 0 < item <= MAX_ID:
            raise Refused("every technical account must be a user id: a positive integer")
        if item in seen:
            raise Refused(f"user {item} is named twice")
        seen.add(item)
    return list(value)


def check_new_ids(ids: Iterable[int], listed: Iterable[int], existing: Iterable[int]) -> None:
    """An id that is not on the list yet must be a user that exists. An id already on the list is
    kept even when its user is gone: it is removed only by leaving it out."""
    listed, existing = set(listed), set(existing)
    unknown = [user_id for user_id in ids if user_id not in listed and user_id not in existing]
    if unknown:
        raise Refused(f"there is no user {unknown[0]}")


def changes(before: Iterable[int], after: Iterable[int]) -> tuple[list[int], list[int]]:
    """The ids added and the ids removed by a save, each in ascending order."""
    before, after = set(before), set(after)
    return sorted(after - before), sorted(before - after)


# How a committed save ended: the answer generation advanced; the advance failed; or the step after
# the commit never ran. Only the first answers 200: in the other two the list is saved, but answers
# computed on the old list are still used, and the caller is told so (503; a repeat save repairs it).
SAVE_DONE = "done"
SAVE_NOT_ADVANCED = "not_advanced"
SAVE_NOT_ANNOUNCED = "not_announced"


def save_outcome(advanced: bool | None) -> str:
    """`advanced`: what the step after the commit returned, None when it did not run."""
    if advanced is None:
        return SAVE_NOT_ANNOUNCED
    return SAVE_DONE if advanced else SAVE_NOT_ADVANCED


def names_to_store(
    ids: Iterable[int], stored: Mapping[int, str], live: Mapping[int, str]
) -> dict[int, str]:
    """The name each listed id is stored with: the live user's current name, or the last known name
    of a user that no longer exists."""
    return {user_id: live[user_id] if user_id in live else stored[user_id] for user_id in ids}


def listing(stored: Mapping[int, str], live: Mapping[int, str]) -> list[dict[str, Any]]:
    """The list as the settings API answers it, ordered by user name, then id. `stored` is the list
    (id -> last known name), `live` the names of those of its users that still exist."""
    rows = [
        {
            "user_id": user_id,
            "user_name": live.get(user_id, name),
            "deleted": user_id not in live,
        }
        for user_id, name in stored.items()
    ]
    return sorted(rows, key=lambda row: (row["user_name"], row["user_id"]))


def clean_search(value: str | None) -> str:
    """The user search text: anything up to SEARCH_MAX_LENGTH characters; absent is empty."""
    value = value or ""
    if len(value) > SEARCH_MAX_LENGTH:
        raise Refused(f"search may be at most {SEARCH_MAX_LENGTH} characters long")
    return value


def clean_project_ids(value: str | None) -> list[int]:
    """The `ids` of the project names lookup: positive integers in ASCII digits separated by commas,
    at most MAX_PROJECT_IDS of them. Absent or empty names no project. Duplicates count once."""
    if not value:
        return []
    parts = value.split(",")
    if len(parts) > MAX_PROJECT_IDS:
        raise Refused(f"ids may name at most {MAX_PROJECT_IDS} projects")
    ids: list[int] = []
    for part in parts:
        # at most 19 digits (MAX_ID has 19) before int() reads it
        if (
            not (part.isascii() and part.isdigit() and len(part) <= 19)
            or not 0 < int(part) <= MAX_ID
        ):
            raise Refused("ids must be project ids separated by commas")
        if int(part) not in ids:
            ids.append(int(part))
    return ids
