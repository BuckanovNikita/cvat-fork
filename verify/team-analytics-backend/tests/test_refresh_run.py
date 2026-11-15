"""One run of the refresh job (the app's core/run.py): which steps it takes, when it ends, and when it advances
the generation of the totals. Steps, the clock and the queue are supplied; nothing is stored anywhere."""

import unittest

from cvat.apps.team_analytics.core.run import WatchedLock, refresh_run


class Lock:
    """A refresh lock that is held until the test takes it away."""

    def __init__(self) -> None:
        self.is_held = True
        self.released = 0

    def acquire(self) -> bool:
        return True

    def held(self) -> bool:
        return self.is_held

    def release(self) -> None:
        self.released += 1


class Run:
    """A run with supplied steps: each entry of `steps` is what one step returns (0: it did work, a number
    above 0: nothing to do or the lock was taken, wait that long), or an exception it raises."""

    def __init__(self, steps, *, seconds_per_step=1.0, reads_waiting_after=None, budget_s=45.0) -> None:
        self.steps = list(steps)
        self.taken = 0
        self.now = 0.0
        self.seconds_per_step = seconds_per_step
        self.reads_waiting_after = reads_waiting_after
        self.budget_s = budget_s
        self.advanced = 0
        self.inner = Lock()
        self.lock = WatchedLock(self.inner)
        self.before_step = None

    def step(self) -> float:
        if self.before_step is not None:
            self.before_step(self)
        outcome = self.steps[self.taken]
        self.taken += 1
        self.now += self.seconds_per_step
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def reads_waiting(self) -> bool:
        return self.reads_waiting_after is not None and self.taken >= self.reads_waiting_after

    def advance(self) -> None:
        self.advanced += 1

    def go(self) -> None:
        refresh_run(self.step, self.lock, budget_s=self.budget_s, reads_waiting=self.reads_waiting,
                    advance_generation=self.advance, monotonic=lambda: self.now)


class RefreshRunTest(unittest.TestCase):
    def test_steps_are_taken_while_there_is_work(self):
        run = Run([0, 0, 0, 540.0])
        run.go()
        self.assertEqual(run.taken, 4, "three steps of work, then the one that found none")

    def test_the_generation_is_advanced_once_for_a_run_that_did_work(self):
        run = Run([0, 0, 0, 540.0])
        run.go()
        self.assertEqual(run.advanced, 1, "once for the run, not once a step")

    def test_a_run_with_nothing_to_do_advances_nothing(self):
        run = Run([540.0])
        run.go()
        self.assertEqual((run.taken, run.advanced), (1, 0), "answers stay cached between refreshes")

    def test_a_run_that_finds_the_lock_taken_advances_nothing(self):
        run = Run([5.0])  # another worker is in a step: retry soon
        run.go()
        self.assertEqual(run.advanced, 0)

    def test_no_new_step_is_started_once_the_budget_has_passed(self):
        run = Run([0] * 100, seconds_per_step=10.0, budget_s=45.0)
        run.go()
        self.assertEqual(run.taken, 5, "the step that crosses the budget is the last")
        self.assertEqual(run.advanced, 1)

    def test_reads_come_before_history(self):
        run = Run([0] * 100, reads_waiting_after=2)
        run.go()
        self.assertEqual(run.taken, 2, "the run ends after the step during which a read arrived")
        self.assertEqual(run.advanced, 1)

    def test_the_first_step_runs_although_reads_are_waiting(self):
        # the first step is the refresh of recent hours whenever that is due: it is never put off
        run = Run([0] * 100, reads_waiting_after=0)
        run.go()
        self.assertEqual(run.taken, 1)

    def test_a_step_that_fails_after_reaching_a_write_advances_the_generation(self):
        # the step may have made hours visible before it failed: answers computed before it must not stay current
        failure = RuntimeError("the record of the refresh could not be written")
        run = Run([failure])
        run.before_step = lambda run: run.lock.held()  # a step asks before each write, and it had got that far
        with self.assertRaises(RuntimeError):
            run.go()
        self.assertEqual(run.advanced, 1)

    def test_a_step_that_fails_before_any_write_advances_nothing(self):
        # ClickHouse cannot be reached: every run fails at its first read. The answers in the cache are all there
        # is, and must stay usable
        run = Run([ConnectionError("ClickHouse cannot be reached")])
        with self.assertRaises(ConnectionError):
            run.go()
        self.assertEqual(run.advanced, 0)

    def test_a_step_that_asked_and_found_nothing_to_do_advances_nothing(self):
        # deciding under the lock that there is no history to compute is not a write
        run = Run([540.0])
        run.before_step = lambda run: run.lock.held()
        run.go()
        self.assertEqual(run.advanced, 0)

    def test_a_failure_after_steps_of_work_advances_once(self):
        run = Run([0, 0, RuntimeError("ClickHouse went away")])
        with self.assertRaises(RuntimeError):
            run.go()
        self.assertEqual((run.taken, run.advanced), (3, 1))

    def test_a_step_that_lost_the_lock_on_the_way_advances_the_generation(self):
        # the Refresher turns a lost lock into "did not run" and the step returns a wait, as when the lock was
        # taken; but this step had started writing
        def lose_the_lock(run: Run) -> None:
            run.inner.is_held = False
            run.lock.held()  # the step's check before its next write finds the lock gone

        run = Run([5.0])
        run.before_step = lose_the_lock
        run.go()
        self.assertEqual(run.advanced, 1)


class WatchedLockTest(unittest.TestCase):
    def test_it_is_the_lock_it_watches(self):
        inner = Lock()
        lock = WatchedLock(inner)
        self.assertTrue(lock.acquire())
        self.assertFalse(lock.asked, "taking the lock is not asking whether it is held")
        self.assertTrue(lock.held())
        self.assertTrue(lock.asked)
        self.assertFalse(lock.lost)
        lock.release()
        self.assertEqual(inner.released, 1)

    def test_it_remembers_that_the_lock_was_lost(self):
        inner = Lock()
        lock = WatchedLock(inner)
        inner.is_held = False
        self.assertFalse(lock.held())
        inner.is_held = True
        self.assertTrue(lock.lost, "lost once is lost for the run")
