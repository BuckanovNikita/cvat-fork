"""The service as deployed: `python -m team_analytics` configured by environment, refreshing on its own."""

import json
import os
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from tests.support import FakeUser, StackTestCase, working_time

SERVICE_DIR = Path(__file__).resolve().parent.parent
ORG = 7


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class EntryPointTest(StackTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.cvat.add_user("lead", FakeUser(2, "lead", memberships={"org7": (ORG, "maintainer", True)}))
        self.port = free_port()
        env = {
            **os.environ,
            "CLICKHOUSE_DB": self.stack.events_db,
            "TEAM_ANALYTICS_DB": self.stack.totals_db,
            "TEAM_ANALYTICS_CVAT_URL": self.stack.cvat.url,
            "TEAM_ANALYTICS_TECHNICAL_ACCOUNTS": "importer, robot",
            "TEAM_ANALYTICS_REFRESH_INTERVAL_S": "2",
            "TEAM_ANALYTICS_LISTEN_HOST": "127.0.0.1",
            "TEAM_ANALYTICS_LISTEN_PORT": str(self.port),
        }
        self.process = subprocess.Popen(  # noqa: S603 - our own module
            [sys.executable, "-B", "-m", "team_analytics"], cwd=SERVICE_DIR, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.addCleanup(self._stop)

    def _stop(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()

    def overview_rows(self):
        request = Request(f"http://127.0.0.1:{self.port}/team-analytics-api/v1/overview?org=org7",
                          headers={"Cookie": "sessionid=lead"})
        try:
            with urlopen(request, timeout=5) as response:
                return json.loads(response.read())["by_annotator"]["rows"]
        except (URLError, ConnectionError):
            return None

    def wait_for(self, predicate, timeout: float = 30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rows = self.overview_rows()
            if rows is not None and predicate(rows):
                return rows
            time.sleep(0.5)
        self.fail(f"not observed within {timeout} s; last answer: {self.overview_rows()}")

    def test_the_running_service_refreshes_on_its_interval_without_being_asked(self):
        now = datetime.now(UTC)
        self.stack.add_events([
            working_time(now, 100_000, user=(11, "alice"), org=ORG),
            working_time(now, 500_000, user=(99, "robot"), org=ORG),
        ])
        rows = self.wait_for(lambda rows: len(rows) > 0)
        self.assertEqual(rows, [{"user_id": 11, "user_name": "alice", "working_time_ms": 100_000}])

        self.stack.add_events([working_time(datetime.now(UTC), 50_000, user=(11, "alice"), org=ORG)])
        rows = self.wait_for(lambda rows: rows and rows[0]["working_time_ms"] == 150_000)
        self.assertEqual(len(rows), 1)
