"""Stopping the service as Kubernetes does (SIGTERM) while it works must not hold up the next replica.

Found in the final run on the test stack (ticket 18): after the service was stopped and started again, the
new replica ran no refresh for minutes. A replica that dies inside a step leaves the shared refresh lease
claimed until it expires (30 minutes then, two since; tests/test_lease.py), and every other replica waits
for it.
"""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from urllib.error import URLError
from urllib.request import Request, urlopen

from tests.support import FakeUser, StackTestCase, working_time
from tests.test_entry_point import SERVICE_DIR, free_port

ORG = 7
ALICE = (11, "alice")
DAYS = 300


class ShutdownTest(StackTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.cvat.add_user("lead", FakeUser(2, "lead", memberships={"org7": (ORG, "owner", True)}))
        # a long history, so the running service is busy one day after another
        now = datetime.now(UTC)
        self.stack.add_events([working_time(now - timedelta(days=day), 60_000, user=ALICE, org=ORG)
                               for day in range(DAYS)])

    def start(self) -> tuple[subprocess.Popen, int]:
        port = free_port()
        env = {
            **os.environ,
            "CLICKHOUSE_DB": self.stack.events_db,
            "TEAM_ANALYTICS_DB": self.stack.totals_db,
            "TEAM_ANALYTICS_CVAT_URL": self.stack.cvat.url,
            "TEAM_ANALYTICS_LISTEN_HOST": "127.0.0.1",
            "TEAM_ANALYTICS_LISTEN_PORT": str(port),
        }
        process = subprocess.Popen(  # noqa: S603 - our own module
            [sys.executable, "-B", "-m", "team_analytics"], cwd=SERVICE_DIR, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.addCleanup(self.stop, process)
        return process, port

    @staticmethod
    def stop(process: subprocess.Popen) -> None:
        if process.poll() is None:
            process.kill()
            process.wait()

    @staticmethod
    def days_ready(port: int) -> int | None:
        request = Request(f"http://127.0.0.1:{port}/team-analytics-api/v1/status?org=org7",
                          headers={"Cookie": "sessionid=lead"})
        try:
            with urlopen(request, timeout=5) as response:
                history = json.loads(response.read()).get("history")
        except (URLError, ConnectionError):
            return None
        return None if history is None else history["days_ready"]

    def wait_days(self, port: int, more_than: int, timeout_s: float) -> int | None:
        deadline = time.monotonic() + timeout_s
        seen = None
        while time.monotonic() < deadline:
            seen = self.days_ready(port)
            if seen is not None and seen > more_than:
                return seen
            time.sleep(0.5)
        return seen

    def test_a_replica_stopped_mid_work_lets_the_next_one_carry_on_at_once(self):
        first, first_port = self.start()
        busy = self.wait_days(first_port, 3, 90)
        self.assertIsNotNone(busy, "the first replica did not start processing history")

        first.send_signal(signal.SIGTERM)  # what Kubernetes sends when it stops a pod
        first.wait(30)  # within the pod's grace period
        self.assertIsNotNone(first.poll(), "the first replica is still running")

        _, second_port = self.start()
        before = self.wait_days(second_port, -1, 60)
        self.assertIsNotNone(before, "the second replica did not answer")
        later = self.wait_days(second_port, before, 30)
        self.assertGreater(later, before, "the second replica processed no history within 30 s of starting")
