"""Entry point: `python -m team_analytics` (cwd = team-analytics/service, or on PYTHONPATH).

Applies the schema and looks for the cutover (`Service.setup`), starts the refresh loop (the refresh of recent
hours every TEAM_ANALYTICS_REFRESH_INTERVAL_S seconds, first run at start; history one day at a time in
between) and serves HTTP.
"""

from __future__ import annotations

import logging
import signal
import threading

from team_analytics.config import Config
from team_analytics.http_server import make_server
from team_analytics.service import Service

log = logging.getLogger("team_analytics")

# Seconds before trying again after a failed step (e.g. ClickHouse not up yet).
FAILURE_RETRY_S = 30
# Seconds to wait at shutdown for the step in progress; within Kubernetes' default 30 s grace period.
STOP_WAIT_S = 25


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
    loop = threading.Thread(target=refresh_loop, args=(service, config.refresh_interval_s, stop), daemon=True)
    loop.start()
    server = make_server(service, config.listen_host, config.listen_port)

    # SIGTERM (a stopping pod): stop serving, let the step in progress finish so it releases the shared
    # refresh lease, then exit. Killed inside a step, the replica would leave the lease claimed until it
    # expires and hold up every other replica.
    def terminate(_signum: int, _frame: object) -> None:
        stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, terminate)
    log.info("listening on %s:%s", config.listen_host, config.listen_port)
    try:
        server.serve_forever()
    finally:
        stop.set()
        loop.join(STOP_WAIT_S)
        log.info("stopped")


if __name__ == "__main__":
    main()
