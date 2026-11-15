"""The backend's path to the figures: the engine built as the worker builds it (the lock in Redis, the read limit),
asked for an answer directly with the scope the worker builds."""

from cvat.apps.team_analytics import reads
from cvat.apps.team_analytics.core.engine import Engine, UnknownEndpoint
from cvat.apps.team_analytics.core.periods import BadRequest
from cvat.apps.team_analytics.core.redis_lock import RedisLock
from cvat.apps.team_analytics.core.scope import Scope
from cvat.apps.team_analytics.core.sql import Limit
from tests.support import StackTestCase, at, working_time

ORG = 7
ALICE = (11, "alice")
BOB = (12, "bob")


class BackendCase(StackTestCase):
    """An engine built as the worker builds it, on a stack with a little work in two organizations."""

    def setUp(self) -> None:
        super().setUp()
        self.lock = RedisLock(self.stack.redis, 120, name=self.stack.lock_name)
        self.engine = Engine(self.stack.config, clock=lambda: self.stack.now, lock=self.lock,
                             read_limit=Limit(20, 512 * 1024 * 1024))
        self.stack.add_events([
            working_time(at("2026-11-13 09:10:00"), 600_000, user=ALICE, org=ORG),
            working_time(at("2026-11-11 08:00:00"), 3_600_000, user=BOB, org=ORG, project=2, task=2, job=2),
            working_time(at("2026-11-12 08:00:00"), 900_000, user=BOB, org=8, project=3, task=3, job=3),
            working_time(at("2026-11-12 09:00:00"), 300_000, user=ALICE, org=None),
        ])

    def settle(self) -> None:
        for _ in range(100):
            if self.engine.step() >= 1:
                return
        self.fail("the engine kept working")


class BackendPathTest(BackendCase):
    def test_the_figures_are_there_and_scoped(self):
        self.engine.setup()
        self.settle()
        other_worker = RedisLock(self.stack.redis, 120, name=self.stack.lock_name)
        self.assertTrue(other_worker.acquire(), "the lock is given back after every step")
        other_worker.release()
        rows = self.engine.answer("overview", Scope(ORG, 0, ""), {"period": "week"},
                                   technical_accounts=())["by_annotator"]["rows"]
        self.assertEqual([(row["user_name"], row["working_time_ms"]) for row in rows],
                         [("bob", 3_600_000), ("alice", 600_000)])

    def test_a_step_is_refused_while_another_worker_holds_the_lock(self):
        self.engine.setup()
        other_worker = RedisLock(self.stack.redis, 120, name=self.stack.lock_name)
        self.assertTrue(other_worker.acquire())
        try:
            self.assertFalse(self.engine.refresh().ran)
        finally:
            other_worker.release()
        self.assertTrue(self.engine.refresh().ran)

    def test_a_refused_parameter_and_an_unknown_endpoint(self):
        self.engine.setup()
        with self.assertRaises(BadRequest):
            self.engine.answer("overview", Scope(ORG, 0, ""), {"period": "century"}, technical_accounts=())
        with self.assertRaises(UnknownEndpoint):
            self.engine.answer("nothing", Scope(ORG, 0, ""), {}, technical_accounts=())


class Recording(dict):
    """A query that notes which parameters were asked for."""

    def __init__(self, values: dict, read: set) -> None:
        super().__init__(values)
        self._read = read

    def get(self, key, default=None):
        self._read.add(key)
        return super().get(key, default)

    def __getitem__(self, key):
        self._read.add(key)
        return super().__getitem__(key)


class EndpointParametersTest(BackendCase):
    """The API process passes on only the parameters it lists for an endpoint (reads.ENDPOINT_PARAMETERS). The
    list must be what the endpoint really reads: one name short and a parameter is silently ignored, one too
    many and a value nobody reads makes a new cache entry and a new job."""

    # queries that take every branch of each endpoint which reads a parameter
    QUERIES = {
        "status": [{}],
        "overview": [{}],
        "list": [{"by": "annotators"}, {"by": "projects"}, {"by": "hotkeys"}],
        "details": [{"by": "annotators"}, {"by": "projects"}, {"by": "projects", "ids": "1,2"}],
        "trends": [{}, {"compare": "projects", "ids": "1"}],
    }

    def test_each_endpoint_reads_exactly_the_parameters_listed_for_it(self):
        self.engine.setup()
        self.settle()
        self.assertEqual(set(self.QUERIES), set(reads.ENDPOINT_PARAMETERS))
        for endpoint, queries in self.QUERIES.items():
            read: set = set()
            for query in queries:
                self.engine.answer(endpoint, Scope(ORG, 0, ""), Recording(query, read), technical_accounts=())
            with self.subTest(endpoint=endpoint):
                self.assertEqual(read, set(reads.ENDPOINT_PARAMETERS[endpoint]))
