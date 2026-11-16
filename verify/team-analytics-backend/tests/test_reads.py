"""How the API process gets an answer (the backend app's reads.py): from the cache, or by queueing the read
and waiting a short time. The cache and the queue are supplied; no Redis and no ClickHouse are involved."""

import unittest

from cvat.apps.team_analytics import reads

ORG_7 = {"org_id": 7}


class Supplied:
    """A cache, a queue and a clock for one test. `worker` is called with every queued read, as the worker
    would be: it may store the answer (`store`), and its result is the enqueueing's."""

    def __init__(self, worker=None, hour="2026-11-13T15", generation=None) -> None:
        self.values: dict = {}
        if generation is not None:
            self.values[reads.GENERATION_KEY] = generation
        self.queued: list[tuple] = []
        self.worker = worker
        self.now = 0.0
        self.slept: list[float] = []
        self.hour = hour

    def get(self, key, default=None):
        return self.values.get(key, default)

    def generation(self):
        return self.values.get(reads.GENERATION_KEY, 0)

    def advance_generation(self) -> None:
        """What the worker does after a refresh run that wrote."""
        self.values[reads.GENERATION_KEY] = self.generation() + 1

    def store(self, key: str, status: int, body: str, generation=None) -> None:
        """What the worker does with an answer: stores it with the generation it was computed on (the
        current one unless given)."""
        self.values[reads.ANSWER_KEY_PREFIX + key] = {
            "status": status, "body": body,
            "generation": self.generation() if generation is None else generation,
        }

    def enqueue(self, job_id, endpoint, scope, query, key) -> bool:
        self.queued.append((job_id, endpoint, scope, query, key))
        return True if self.worker is None else self.worker(self, key)

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def fetch(self, endpoint="overview", scope=ORG_7, query=None, wait_s=5.0) -> reads.Answer:
        return reads.fetch(endpoint, scope, query or {}, cache=self, enqueue=self.enqueue, wait_s=wait_s,
                           retry_after_s=3, hour=lambda: self.hour, monotonic=lambda: self.now, sleep=self.sleep)


def answers_at_once(supplied: Supplied, key: str) -> bool:
    supplied.store(key, 200, '{"figures": 1}')
    return True


class FetchTest(unittest.TestCase):
    def test_a_miss_queues_the_read_and_returns_the_answer_the_worker_stored(self):
        supplied = Supplied(worker=answers_at_once)
        self.assertEqual(supplied.fetch(query={"period": "week"}), reads.Answer(200, '{"figures": 1}'))
        (job_id, endpoint, scope, query, key), = supplied.queued
        self.assertEqual((endpoint, scope, query), ("overview", ORG_7, {"period": "week"}))
        self.assertEqual(job_id, reads.JOB_ID_PREFIX + key)

    def test_the_same_request_again_is_answered_from_the_cache(self):
        supplied = Supplied(worker=answers_at_once)
        supplied.fetch(query={"period": "week"})
        self.assertEqual(supplied.fetch(query={"period": "week"}), reads.Answer(200, '{"figures": 1}'))
        self.assertEqual(len(supplied.queued), 1, "the second request must not be queued")
        self.assertEqual(supplied.slept, [reads.POLL_S], "nor wait")

    def test_an_answer_that_does_not_arrive_in_time_is_a_retry(self):
        supplied = Supplied()  # the worker never answers
        answer = supplied.fetch(wait_s=5.0)
        self.assertEqual(answer, reads.Answer(429, None, 3))
        self.assertLess(sum(supplied.slept), 5.0 + 2 * reads.POLL_S, "the wait is bounded")
        self.assertGreaterEqual(sum(supplied.slept), 5.0 - reads.POLL_S)

    def test_a_wait_of_zero_replies_at_once(self):
        supplied = Supplied()
        self.assertEqual(supplied.fetch(wait_s=0), reads.Answer(429, None, 3))
        self.assertEqual(supplied.slept, [], "no waiting at all")
        self.assertEqual(len(supplied.queued), 1, "the read is still queued for the retry to find")

    def test_a_read_that_could_not_be_queued_is_a_retry_without_waiting(self):
        supplied = Supplied(worker=lambda supplied, key: False)  # the queue is full
        self.assertEqual(supplied.fetch(), reads.Answer(429, None, 3))
        self.assertEqual(supplied.slept, [])

    def test_an_answer_that_arrives_during_the_wait_is_returned(self):
        supplied = Supplied()
        real_sleep = supplied.sleep

        def sleep(seconds):
            real_sleep(seconds)
            if supplied.now >= 1.0:
                supplied.store(supplied.queued[0][4], 200, "{}")

        supplied.sleep = sleep
        self.assertEqual(supplied.fetch(), reads.Answer(200, "{}"))
        self.assertLess(supplied.now, 1.2)

    def test_a_refused_parameter_and_a_failed_read_are_answers_too(self):
        for status in (400, 503):
            with self.subTest(status=status):
                supplied = Supplied(worker=lambda supplied, key, status=status: supplied.store(key, status, "{}") or True)
                self.assertEqual(supplied.fetch().status, status)


class WaitTest(unittest.TestCase):
    """What a request holds while it waits, and what counts as a read waiting in the queue."""

    def fetch(self, supplied: Supplied, calls: list, wait_s=5.0) -> reads.Answer:
        return reads.fetch("overview", ORG_7, {}, cache=supplied, enqueue=supplied.enqueue, wait_s=wait_s,
                           retry_after_s=3, hour=lambda: supplied.hour, monotonic=lambda: supplied.now,
                           sleep=supplied.sleep, before_wait=lambda: calls.append(supplied.now))

    def test_the_request_lets_go_once_before_it_waits(self):
        supplied, calls = Supplied(), []  # the worker never answers
        self.fetch(supplied, calls)
        self.assertEqual(calls, [0.0], "once, before the first look, not at every look")

    def test_an_answer_from_the_cache_lets_go_of_nothing(self):
        supplied, calls = Supplied(worker=answers_at_once), []
        self.fetch(supplied, [])
        self.fetch(supplied, calls)
        self.assertEqual(calls, [])

    def test_a_request_that_does_not_wait_lets_go_of_nothing(self):
        for supplied, wait_s in ((Supplied(), 0), (Supplied(worker=lambda supplied, key: False), 5.0)):
            calls: list = []
            self.fetch(supplied, calls, wait_s=wait_s)
            self.assertEqual(calls, [])

    def test_only_reads_count_as_waiting_reads(self):
        refresh = "team_analytics_refresh"  # the periodic job, queued again every minute while no worker runs
        ids = [refresh, reads.JOB_ID_PREFIX + "a", refresh, refresh, reads.JOB_ID_PREFIX + "b"]
        self.assertEqual(reads.waiting_reads(ids), 2)
        self.assertEqual(reads.waiting_reads([refresh] * 40), 0, "piled-up refresh jobs must not refuse reads")
        self.assertEqual(reads.waiting_reads([]), 0)


class GenerationTest(unittest.TestCase):
    """An answer is used only while the totals it was computed on are the current ones, and the totals moving
    never makes a request pay for two reads."""

    def test_a_refresh_that_wrote_makes_the_next_request_compute_again(self):
        supplied = Supplied(worker=answers_at_once, generation=5)
        supplied.fetch()
        supplied.advance_generation()
        supplied.worker = lambda supplied, key: supplied.store(key, 200, '{"figures": 2}') or True
        self.assertEqual(supplied.fetch().body, '{"figures": 2}', "the answer of the older totals must not be used")
        self.assertEqual(len(supplied.queued), 2)

    def test_the_request_keeps_one_key_and_one_job_while_the_totals_move(self):
        supplied = Supplied(generation=5)  # the worker is busy: nothing is stored yet
        self.assertEqual(supplied.fetch().status, 429)
        supplied.advance_generation()  # a history step wrote while the request was away
        self.assertEqual(supplied.fetch().status, 429)
        first, second = supplied.queued
        self.assertEqual(first[0], second[0], "the retry must find the job of its request, not queue another")
        self.assertEqual(first[4], second[4])

    def test_a_waiting_request_takes_the_answer_although_the_totals_moved_during_its_wait(self):
        supplied = Supplied(generation=5)
        real_sleep = supplied.sleep

        def sleep(seconds):
            real_sleep(seconds)
            if supplied.now >= 1.0 and reads.ANSWER_KEY_PREFIX + supplied.queued[0][4] not in supplied.values:
                # the worker read generation 5, computed, and stored; a history step then wrote
                supplied.store(supplied.queued[0][4], 200, '{"figures": 1}', generation=5)
                supplied.advance_generation()

        supplied.sleep = sleep
        self.assertEqual(supplied.fetch(), reads.Answer(200, '{"figures": 1}'))
        self.assertEqual(len(supplied.queued), 1)

    def test_a_waiting_request_does_not_take_an_answer_older_than_its_arrival(self):
        supplied = Supplied(generation=5)
        key = reads.request_key("overview", ORG_7, {}, supplied.hour)
        supplied.store(key, 200, '{"figures": "old"}', generation=4)
        self.assertEqual(supplied.fetch(), reads.Answer(429, None, 3), "the stored answer is of older totals")
        self.assertEqual(len(supplied.queued), 1, "and the read is queued")

    def test_an_answer_computed_while_a_run_was_writing_is_computed_again(self):
        # the worker read generation 5 before computing; the run that was writing then ended (6)
        supplied = Supplied(generation=6)
        key = reads.request_key("overview", ORG_7, {}, supplied.hour)
        supplied.store(key, 200, '{"figures": "during"}', generation=5)
        supplied.worker = lambda supplied, key: supplied.store(key, 200, '{"figures": "after"}') or True
        self.assertEqual(supplied.fetch().body, '{"figures": "after"}')

    def test_before_the_first_refresh_the_generation_counts_as_zero(self):
        supplied = Supplied(worker=answers_at_once)  # no generation stored yet
        supplied.fetch()
        self.assertEqual(supplied.fetch().status, 200)
        self.assertEqual(len(supplied.queued), 1)


class RequestKeyTest(unittest.TestCase):
    """What an answer belongs to is in its key, so an entry is never served where it does not belong."""

    def key(self, endpoint="overview", scope=ORG_7, query=None, hour="2026-11-13T15") -> str:
        return reads.request_key(endpoint, scope, query or {"period": "week"}, hour)

    def test_the_same_request_has_the_same_key(self):
        self.assertEqual(self.key(query={"period": "week", "tz": "UTC"}), self.key(query={"tz": "UTC", "period": "week"}))

    def test_another_organization_has_another_key(self):
        self.assertNotEqual(self.key(scope={"org_id": 7}), self.key(scope={"org_id": 8}))

    def test_instance_scope_is_not_an_organization(self):
        self.assertNotEqual(self.key(scope={"org_id": None}), self.key(scope={"org_id": 0}))

    def test_an_organization_is_not_instance_scope(self):
        # only administrators read: the organization alone keeps an organization's answer from instance scope
        for endpoint in ("status", "overview", "details"):
            with self.subTest(endpoint=endpoint):
                self.assertNotEqual(self.key(endpoint, scope={"org_id": 7}), self.key(endpoint, scope={"org_id": None}))

    def test_endpoint_parameters_and_hour_each_change_the_key(self):
        base = self.key()
        self.assertNotEqual(base, self.key(endpoint="list"))
        self.assertNotEqual(base, self.key(query={"period": "month"}))
        self.assertNotEqual(base, self.key(hour="2026-11-13T16"))

    def test_one_organizations_entry_is_not_returned_to_another(self):
        supplied = Supplied(worker=answers_at_once)
        supplied.fetch(scope={"org_id": 7})
        supplied.worker = lambda supplied, key: supplied.store(key, 200, '{"figures": 2}') or True
        self.assertEqual(supplied.fetch(scope={"org_id": 8}).body, '{"figures": 2}')
        supplied.worker = lambda supplied, key: supplied.store(key, 200, '{"figures": 3}') or True
        self.assertEqual(supplied.fetch(scope={"org_id": None}).body, '{"figures": 3}')


class CleanQueryTest(unittest.TestCase):
    def test_only_parameters_the_endpoint_reads_are_kept(self):
        sent = {"period": "week", "org": "org7", "org_id": "7", "x": "1", "tz": "UTC", "search": "a", "step": "week"}
        self.assertEqual(reads.clean_query("overview", sent), {"period": "week", "tz": "UTC"})
        self.assertEqual(reads.clean_query("status", sent), {"tz": "UTC"})
        self.assertEqual(reads.clean_query("details", sent), {"period": "week", "tz": "UTC", "search": "a"})
        self.assertEqual(reads.clean_query("trends", sent), {"tz": "UTC", "step": "week"})

    def test_a_parameter_the_endpoint_does_not_read_makes_no_second_entry_and_no_second_job(self):
        # `search` is read by the details table only: an overview asked with ever new values of it is one request
        supplied = Supplied(worker=answers_at_once)
        for value in ("a", "b", "c"):
            query = reads.clean_query("overview", {"period": "week", "search": value, "cachebust": value})
            self.assertEqual(supplied.fetch("overview", query=query).status, 200)
        self.assertEqual(len(supplied.queued), 1)

    def test_every_endpoint_has_its_parameters_and_every_parameter_its_length(self):
        self.assertEqual(set(reads.ENDPOINT_PARAMETERS), {"status", "overview", "list", "details", "trends"})
        named = {name for names in reads.ENDPOINT_PARAMETERS.values() for name in names}
        self.assertEqual(named, set(reads.MAX_LENGTH))

    def test_a_value_longer_than_any_valid_one_is_refused(self):
        for name, value in (("tz", "A" * 65), ("month", "2026-011"), ("period", "x" * 17), ("project", "1" * 20)):
            with self.subTest(name=name), self.assertRaises(reads.QueryRefused):
                reads.clean_query("overview", {name: value})
        with self.assertRaises(reads.QueryRefused):
            reads.clean_query("details", {"ids": "1" * 100_001})
        reads.clean_query("details", {"ids": ",".join(["9" * 19] * 5000)})  # the longest the details table sends
        reads.clean_query("overview", {"tz": "America/Argentina/ComodRivadavia", "month": "2026-11"})


class FakeCache:
    """Django's cache as far as the generation needs it: `incr` refuses a key that is not there, `add` stores
    only when there is none."""

    def __init__(self) -> None:
        self.values: dict = {}

    def incr(self, key):
        if key not in self.values:
            raise ValueError(key)
        self.values[key] += 1
        return self.values[key]

    def add(self, key, value, timeout):
        if key in self.values:
            return False
        self.values[key] = value
        return True


class AdvanceGenerationTest(unittest.TestCase):
    def test_the_generation_is_a_counter_that_only_grows(self):
        cache = FakeCache()
        seen = []
        for _ in range(3):
            reads.advance_generation(cache)
            seen.append(cache.values[reads.GENERATION_KEY])
        self.assertEqual(seen, [seen[0], seen[0] + 1, seen[0] + 2])

    def test_a_counter_that_was_lost_starts_above_the_answers_that_stayed(self):
        # the counter's key is gone while answers computed under it are still in the cache
        supplied = Supplied()
        key = reads.request_key("overview", ORG_7, {}, supplied.hour)
        supplied.store(key, 200, '{"figures": "old"}', generation=57)
        cache = FakeCache()
        reads.advance_generation(cache)  # the next run that wrote starts the counter again
        supplied.values[reads.GENERATION_KEY] = cache.values[reads.GENERATION_KEY]
        self.assertGreater(supplied.generation(), 57)
        self.assertEqual(supplied.fetch(), reads.Answer(429, None, 3), "the old answer must not be taken for new")

    def test_two_workers_storing_the_first_generation_at_once_leave_it_advanced_twice(self):
        cache = FakeCache()
        add = cache.add

        def add_after_the_other_worker(key, value, timeout):
            add(key, 1, None)  # the other worker's first generation lands just before ours
            return add(key, value, timeout)

        cache.add = add_after_the_other_worker
        reads.advance_generation(cache)
        self.assertEqual(cache.values[reads.GENERATION_KEY], 2)
