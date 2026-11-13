"""Entry point: `python -m team_analytics` (cwd = team-analytics/service, or on PYTHONPATH).

Applies the schema, starts the refresh loop (the refresh of recent hours every
TEAM_ANALYTICS_REFRESH_INTERVAL_S seconds, first run at start; history one day at a time in between)
and serves HTTP.
"""

from __future__ import annotations

import logging
import threading

from team_analytics.config import Config
from team_analytics.http_server import make_server
from team_analytics.service import Service

log = logging.getLogger("team_analytics")

# Seconds before trying again after a failed step (e.g. ClickHouse not up yet).
FAILURE_RETRY_S = 30


def refresh_loop(service: Service, interval_s: int, stop: threading.Event) -> None:
    """Runs the service's steps (worker.py): the ten-minute refresh when due, else history, one day at a time."""
    while not stop.is_set():
        try:
            wait = service.step()
        except Exception:
            log.exception("refresh failed")
            wait = min(interval_s, FAILURE_RETRY_S)
        if wait > 0:
            stop.wait(wait)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    config = Config.from_env()
    service = Service(config)
    service.setup()
    stop = threading.Event()
    threading.Thread(target=refresh_loop, args=(service, config.refresh_interval_s, stop), daemon=True).start()
    server = make_server(service, config.listen_host, config.listen_port)
    log.info("listening on %s:%s", config.listen_host, config.listen_port)
    try:
        server.serve_forever()
    finally:
        stop.set()


if __name__ == "__main__":
    main()
