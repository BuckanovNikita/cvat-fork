"""The service as deployed: `python -m team_analytics` configured by environment, refreshing on its own, and knowing
the cutover from its first answer."""

import json
import os
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from tests.support import FakeUser, StackTestCase, working_time
from tests.test_bounding_boxes import BOX
from tests.test_operations import client, draw

SERVICE_DIR = Path(__file__).resolve().parent.parent
ORG = 7


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class RunningServiceCase(StackTestCase):
    """Starts `python -m team_analytics` on the stack's databases, after the events of `recorded_before_start`."""

    def recorded_before_start(self) -> list[dict]:
        return []

    def setUp(self) -> None:
        super().setUp()
        self.stack.cvat.add_user("lead", FakeUser(2, "lead", memberships={"org7": (ORG, "maintainer", True)}))
        self.stack.add_events(self.recorded_before_start())
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

    def read(self, endpoint: str) -> dict | None:
        """The answer of an endpoint for the maintainer of org7, or None while the service does not answer."""
        request = Request(f"http://127.0.0.1:{self.port}/team-analytics-api/v1/{endpoint}?org=org7",
                          headers={"Cookie": "sessionid=lead"})
        try:
            with urlopen(request, timeout=5) as response:
                return json.loads(response.read())
        except (URLError, ConnectionError):
            return None

    def overview_rows(self):
        overview = self.read("overview")
        section = None if overview is None else overview["by_annotator"]
        # null until the week reads as processed (before the first refresh, or while one lands mid-request)
        return None if section is None else section["rows"]

    def wait_for(self, predicate, timeout: float = 30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            rows = self.overview_rows()
            if rows is not None and predicate(rows):
                return rows
            time.sleep(0.5)
        self.fail(f"not observed within {timeout} s; last answer: {self.overview_rows()}")


class EntryPointTest(RunningServiceCase):

    def test_the_running_service_refreshes_on_its_interval_without_being_asked(self):
        now = datetime.now(UTC)
        self.stack.add_events([
            working_time(now, 100_000, user=(11, "alice"), org=ORG),
            working_time(now, 500_000, user=(99, "robot"), org=ORG),
        ])
        rows = self.wait_for(lambda rows: len(rows) > 0)
        self.assertEqual([(row["user_id"], row["user_name"], row["working_time_ms"]) for row in rows],
                         [(11, "alice", 100_000)])

        self.stack.add_events([working_time(datetime.now(UTC), 50_000, user=(11, "alice"), org=ORG)])
        rows = self.wait_for(lambda rows: rows and rows[0]["working_time_ms"] == 150_000)
        self.assertEqual(len(rows), 1)


class CutoverOnTheFirstAnswerTest(RunningServiceCase):
    """The running service knows the cutover from its first answer: it looks for it when it starts, before it opens
    its port, while its loop would reach the day of the first shape-tagged event only after hundreds of days."""

    DAYS = 300

    def recorded_before_start(self) -> list[dict]:
        now = datetime.now(UTC)
        self.tagged = now - timedelta(days=self.DAYS)
        # untagged work every day since, which history computes newest first, one day per step
        return [client("load:job", self.tagged, org=ORG), draw(self.tagged, input_method="mouse", org=ORG, **BOX)] + [
            working_time(now - timedelta(days=day), 60_000, user=(11, "alice"), org=ORG) for day in range(self.DAYS)]

    def test_the_first_answer_of_the_running_service_has_the_cutover(self):
        deadline = time.monotonic() + 60
        while (first := self.read("status")) is None:
            self.assertLess(time.monotonic(), deadline, "the service never answered")
            time.sleep(0.2)
        cutover = self.tagged.replace(minute=0, second=0, microsecond=0)
        self.assertEqual(first["cutover"], {"at": cutover.isoformat()})
