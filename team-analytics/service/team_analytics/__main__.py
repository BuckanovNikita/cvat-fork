"""Entry point: `python -m team_analytics` (cwd = team-analytics/service, or on PYTHONPATH).

Applies the schema, starts the refresh loop (every TEAM_ANALYTICS_REFRESH_INTERVAL_S seconds,
first run at start) and serves HTTP.
"""

from __future__ import annotations

import logging
import threading
import time

from team_analytics.config import Config
from team_analytics.http_server import make_server
from team_analytics.service import Service

log = logging.getLogger("team_analytics")


def refresh_loop(service: Service, interval_s: int, stop: threading.Event) -> None:
    while not stop.is_set():
        started = time.monotonic()
        try:
            result = service.refresh()
            if not result.ran:
                log.info("refresh skipped: another refresh is running")
        except Exception:
            log.exception("refresh failed")
        stop.wait(max(1.0, interval_s - (time.monotonic() - started)))


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
