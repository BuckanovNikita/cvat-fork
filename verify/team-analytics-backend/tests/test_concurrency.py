"""Requests served at the same time as each other and as a refresh get the same figures as one at a time."""

import threading
from concurrent.futures import ThreadPoolExecutor

from tests.support import FakeUser, StackTestCase, at, working_time

ORG = 7


class ConcurrentRequestsTest(StackTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.stack.callers.add_user("lead", FakeUser(2, "lead", groups=["admin"], memberships={"org7": (ORG, "maintainer", True)}))
        self.stack.add_events([
            working_time(at(f"2026-11-1{day} 10:00:00"), (n + 1) * 60_000, user=(100 + n, f"user{n}"), org=ORG,
                         project=1 + n % 3)
            for n in range(12) for day in (0, 1, 2)
        ])
        self.stack.refresh()

    def overview(self) -> tuple[int, dict]:
        return self.stack.overview("lead", org="org7")

    def test_parallel_requests_during_a_refresh_all_get_the_figures(self):
        status, expected = self.overview()
        self.assertEqual(status, 200, expected)
        refreshing = threading.Thread(target=self.stack.engine.refresh)
        refreshing.start()
        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                answers = list(pool.map(lambda _: self.overview(), range(16)))
        finally:
            refreshing.join(60)
        for status, body in answers:
            self.assertEqual(status, 200, body)
            self.assertEqual(body["by_annotator"], expected["by_annotator"])
            self.assertEqual(body["by_project"], expected["by_project"])
