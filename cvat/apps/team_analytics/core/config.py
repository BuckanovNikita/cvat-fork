"""What the calculation code is configured with. The backend builds one from Django's settings (jobs.py)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_user: str = "user"
    clickhouse_password: str = "user"
    # Database holding CVAT's `events` table (read only).
    events_db: str = "cvat"
    # Database of the stored totals, owned by Team Analytics.
    totals_db: str = "team_analytics"
    refresh_interval_s: int = 600
    refresh_window_hours: int = 48
    # How far before the refresh window the computation reads events.
    lookback_s: int = 300
    # Length of the refresh lock, extended every third of it (40 s) while a step runs. A worker killed
    # inside a step holds up the others for this long at most. Not a setting.
    refresh_lease_s: int = 120
    # Limits of the cutover search (cutover.py), enforced by ClickHouse on the statement. The search of the
    # first job, before the first answer, gets the shorter one; in the daily check it runs under the lock
    # and gets a tenth of the refresh interval. Fixed with the measurement of
    # docs/evidence/2026-11-14-cutover-search-cost.md. Not settings.
    cutover_search_at_start_s: float = 23
    cutover_search_in_check_s: float = 60
    cutover_search_memory_bytes: int = 512 * 1024 * 1024
