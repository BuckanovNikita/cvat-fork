"""Service configuration, read from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_user: str = "user"
    clickhouse_password: str = "user"
    # Database holding CVAT's `events` table (read only).
    events_db: str = "cvat"
    # Database of the stored totals, owned by this service.
    totals_db: str = "team_analytics"
    # CVAT's backend, asked with the caller's credentials who the caller is.
    cvat_url: str = "http://localhost:8080"
    cvat_timeout_s: float = 5.0
    # User names of accounts that stand for automated processes.
    technical_accounts: tuple[str, ...] = ()
    refresh_interval_s: int = 600
    refresh_window_hours: int = 48
    # How far before the refresh window the computation reads events.
    lookback_s: int = 300
    listen_host: str = "0.0.0.0"  # noqa: S104 - a service in a pod listens on all interfaces
    listen_port: int = 8000

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> Config:
        accounts = tuple(name.strip() for name in env.get("TEAM_ANALYTICS_TECHNICAL_ACCOUNTS", "").split(",")
                         if name.strip())
        return cls(
            clickhouse_host=env.get("CLICKHOUSE_HOST", cls.clickhouse_host),
            clickhouse_port=int(env.get("CLICKHOUSE_PORT", cls.clickhouse_port)),
            clickhouse_user=env.get("CLICKHOUSE_USER", cls.clickhouse_user),
            clickhouse_password=env.get("CLICKHOUSE_PASSWORD", cls.clickhouse_password),
            events_db=env.get("CLICKHOUSE_DB", cls.events_db),
            totals_db=env.get("TEAM_ANALYTICS_DB", cls.totals_db),
            cvat_url=env.get("TEAM_ANALYTICS_CVAT_URL", cls.cvat_url).rstrip("/"),
            cvat_timeout_s=float(env.get("TEAM_ANALYTICS_CVAT_TIMEOUT_S", cls.cvat_timeout_s)),
            technical_accounts=accounts,
            refresh_interval_s=int(env.get("TEAM_ANALYTICS_REFRESH_INTERVAL_S", cls.refresh_interval_s)),
            refresh_window_hours=int(env.get("TEAM_ANALYTICS_REFRESH_WINDOW_HOURS", cls.refresh_window_hours)),
            lookback_s=int(env.get("TEAM_ANALYTICS_LOOKBACK_S", cls.lookback_s)),
            listen_host=env.get("TEAM_ANALYTICS_LISTEN_HOST", cls.listen_host),
            listen_port=int(env.get("TEAM_ANALYTICS_LISTEN_PORT", cls.listen_port)),
        )
