# 07: Reads are answered from the cache or computed on the worker

**What to build:** The five endpoints. The API process validates, looks in the cache and queues; the worker computes. See "Reads" and "Worker" in the spec and ADR 0006.

**Blocked by:** 05, 06.

**Status:** resolved

- [x] Each endpoint returns what the service returned for the same parameters and scope.
- [x] A second identical request is answered from the cache; a refresh that wrote makes the next one compute again.
- [ ] Two identical requests in flight cause one job.
- [x] A request waits at most the configured time and then answers 429 with `Retry-After`; with the wait set to 0 it answers at once.
- [ ] When the queue is deeper than its limit a miss answers 429 without queueing.
- [ ] A read whose statement exceeds its time or memory limit answers 503 and does not occupy the worker beyond the job timeout.
- [x] An entry computed for one organization is never returned for another, nor an administrator's status to a maintainer.
- [x] The view, permission and read modules import with `clickhouse_connect` unavailable.
- [x] The endpoints are absent from the published schema.

## Comments

2026-11-15: `6e74221c`. `tests/test_reads.py` (19 tests, cache and queue supplied): a miss queues and returns what the worker stored; the same request again comes from the cache; no answer in time is a 429 within the wait; a wait of 0 replies at once and still queues; a read that could not be queued is a 429 without waiting; the key changes with organization, instance scope, the administrator mark, endpoint, parameters, generation and hour; unknown parameters are dropped. `tests/test_api_side.py` reads the sources: the API-side modules import neither `core`, `jobs` nor `clickhouse_connect`.

Parameters are checked for meaning by the worker, not by the API process: the API keeps the twelve parameters an endpoint reads and refuses a value over 120,000 characters; a parameter an endpoint refuses comes back as a stored 400.

Open until the stack run: every criterion that needs a served request, the worker, or ClickHouse limits.

2026-11-15: Changed twice after the first live run. `2c653fe6`: the default Retry-After is 3 s, and every response of the view set carries `Cache-Control: no-store`. `919d7ea0`: the generation left the cache key. On the stack, during a history fill, a request that waited and asked again built a new key each time the generation moved, queued a second job behind its own first, and six to ten of thirty-six overviews got no answer within the client's retries. The key is now the request (endpoint, scope, parameters, hour); the stored answer carries the generation it was computed on; a stored answer is used only while that generation is current, and a waiting request takes any answer computed since it arrived. `tests/test_reads.py` gained the cases: one key and one job while the totals move; a waiting request takes the answer although the totals moved; it does not take an answer older than its arrival; an answer computed while a run was writing is computed again. 22 tests, none failed.

2026-11-15: Shown on the stack (`docs/evidence/2026-11-15-backend-acceptance.md`): a cold overview in 2.3 to 2.6 s within the wait, a warm one in 0.03 to 0.04 s; with the worker at zero every request answered 429 after 5.2 to 5.3 s; with ClickHouse down overview and trends answered 503; one organization's cached answer was not served to another, nor an administrator's status to a maintainer; the engine asked directly answered as the service did over HTTP, for all five endpoints.

Three criteria stay unticked. One job for two identical requests in flight rests on the job id being the request key (tested) and on the timing of the load check; the queued jobs themselves were not counted. The queue depth limit lives in the view's enqueueing and was never reached on the stack ("none was refused at once by the queue limit"); the rule that a read that cannot be queued answers 429 is tested with a supplied queue. No read reached its statement limit, so the 503 for it was not seen.

2026-11-15: After the independent review (`b1655b51`) and the rerun on the stack. In six bursts of twelve different requests the worker's log shows twelve read jobs, none twice, and a request asked again with ignored parameters started no job. Two identical requests in flight were not sent, so that criterion still rests on the job id being the request key. The queue depth limit now counts reads only; it was still not reached on the stack, and a read stopped by its statement limit was still not seen. The three criteria stay unticked.
