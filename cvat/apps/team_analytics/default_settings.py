# SPDX-License-Identifier: MIT

"""Settings of Team Analytics, with their defaults. A value set in the Django settings wins."""

import logging
import math
import os

log = logging.getLogger(__name__)


def _number(name: str, default, kind=int, minimum=1):
    """The setting's value from the environment. A value that is not a number, or is below what the
    setting can work with, is reported and the default taken: a mistyped Team Analytics setting must
    neither keep CVAT from starting nor break every request of the feature."""
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        value = kind(raw)
    except ValueError:
        log.error("%s=%r is not a number; using %r", name, raw, default)
        return default
    if not math.isfinite(value) or value < minimum:
        log.error("%s=%r must be a number of at least %r; using %r", name, raw, minimum, default)
        return default
    return value


# Database of the stored totals, on the ClickHouse server of settings.CLICKHOUSE["events"].
TEAM_ANALYTICS_DB = os.getenv("TEAM_ANALYTICS_DB", "team_analytics")

# The Technical accounts list is not a setting: administrators edit it in the Team Analytics settings
# (models.TechnicalAccount). The environment variable that held it before is looked at only to warn:
# an instance upgraded with it still set is told once at start that its value has no effect and
# where the list is now kept, instead of losing the list without a word.
if os.getenv("TEAM_ANALYTICS_TECHNICAL_ACCOUNTS", "").strip():
    log.warning(
        "TEAM_ANALYTICS_TECHNICAL_ACCOUNTS is ignored: the Technical accounts list is edited by an "
        "administrator in Team Analytics settings (the Settings button of the Team Analytics page)"
    )

# The refresh of the stored totals: how often recent hours are recomputed, how many of them, and how
# far before them the computation reads events.
TEAM_ANALYTICS_REFRESH_INTERVAL_S = _number("TEAM_ANALYTICS_REFRESH_INTERVAL_S", 600)
TEAM_ANALYTICS_REFRESH_WINDOW_HOURS = _number("TEAM_ANALYTICS_REFRESH_WINDOW_HOURS", 48)
TEAM_ANALYTICS_LOOKBACK_S = _number("TEAM_ANALYTICS_LOOKBACK_S", 300, minimum=0)

# The refresh job is scheduled every minute. One run takes steps (a refresh, a day of history, the
# daily check) while there is work, and starts no new step once this many seconds have passed, so
# that it occupies one worker process for part of each minute at most.
TEAM_ANALYTICS_REFRESH_BUDGET_S = _number("TEAM_ANALYTICS_REFRESH_BUDGET_S", 45, minimum=0)

# What ClickHouse allows one statement of a refresh or of a day of history. It is far above what such
# a statement takes; it is there so that a statement gone wrong is stopped by ClickHouse itself.
TEAM_ANALYTICS_REFRESH_STATEMENT_S = _number("TEAM_ANALYTICS_REFRESH_STATEMENT_S", 300.0, float)

# How long a request waits for an answer that is not in the cache before it replies 429, and the
# Retry-After it replies with. A wait of 0 replies at once. The page's client asks again after
# Retry-After, three times: four waits and three pauses, 29 s with these defaults, before the page
# shows its error panel. The answer is taken from the cache whenever it has arrived by then.
TEAM_ANALYTICS_READ_WAIT_S = _number("TEAM_ANALYTICS_READ_WAIT_S", 5.0, float, minimum=0)
TEAM_ANALYTICS_READ_RETRY_AFTER_S = _number("TEAM_ANALYTICS_READ_RETRY_AFTER_S", 3, minimum=0)

# Reads waiting in the queue beyond which a request is not queued and replies 429.
TEAM_ANALYTICS_READ_QUEUE_LIMIT = _number("TEAM_ANALYTICS_READ_QUEUE_LIMIT", 32)

# What ClickHouse allows one statement of a read, and the worker one read as a whole.
TEAM_ANALYTICS_READ_STATEMENT_S = _number("TEAM_ANALYTICS_READ_STATEMENT_S", 20.0, float)
TEAM_ANALYTICS_READ_STATEMENT_MEMORY_BYTES = _number(
    "TEAM_ANALYTICS_READ_STATEMENT_MEMORY_BYTES", 512 * 1024 * 1024
)
TEAM_ANALYTICS_READ_JOB_TIMEOUT_S = _number("TEAM_ANALYTICS_READ_JOB_TIMEOUT_S", 90)

# How long an answer stays in the cache. An answer is used only while the generation of the totals
# it was computed on is the current one, and its key names the hour; this only clears entries
# nobody asks for again.
TEAM_ANALYTICS_ANSWER_TTL_S = _number("TEAM_ANALYTICS_ANSWER_TTL_S", 900)
# How long a failed read is remembered, so that a burst of requests does not repeat it at once.
TEAM_ANALYTICS_FAILURE_TTL_S = _number("TEAM_ANALYTICS_FAILURE_TTL_S", 5)
