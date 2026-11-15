# 04: The refresh runs under a lock that can be Redis

**What to build:** The lock that lets one refresh run at a time becomes an interface the refresher is given. Two implementations exist until the service is deleted: today's lease in ClickHouse, which the service keeps using, and a Redis lock for the backend job. See ADR 0006.

**Blocked by:** 03.

**Status:** resolved

- [x] The refresher, history and cutover code ask the lock whether it is still held before every write, as today, and know nothing of how it is kept.
- [x] The Redis lock is taken without waiting, expires by itself, is extended while a run goes on, and is released on every way out.
- [x] A run that can no longer prove it holds the lock stops before its next write.
- [x] A holder that died is overtaken once the lock has expired (120 s by default).
- [x] The lease tests keep passing on the ClickHouse lease; the same cases pass on the Redis lock against a real Redis.
- [x] The test runner starts a throwaway Redis beside ClickHouse and removes it on exit.

## Comments

2026-11-15: `d27271ce`. `Refresher` takes an optional lock (`RefreshLock`); without one it keeps the lease in ClickHouse, which the service still uses. `core/redis_lock.py` is the Redis lock: taken without waiting, 120 s by default, extended every third by a thread, released on every way out. The runner starts `redis:7.2.11` beside ClickHouse. `tests/test_redis_lock.py`, against that Redis: one holder at a time; a step longer than the lock keeps it; a dead holder is overtaken after the length; the lock counts as lost in its last tenth and stays lost; a holder whose key was taken over learns it at its next extension; a Refresher given the lock runs a step under it, is refused while another holds it, gives it back when the step fails, and stops before its next write once it cannot prove the lock. 11 tests, none failed. The lease tests (`tests.test_lease`, 11) passed on the same tree.

A difference from the criterion as written: the lock is extended by a thread while a step runs, as the lease was, not only when a write asks. A single statement can outlast the lock's length, and without the thread the lock would expire under a live holder.
