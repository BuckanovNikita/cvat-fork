---
status: accepted
---

# Team Analytics lives in the CVAT backend, and its queries run on a worker of their own

Team Analytics got its figures from a separate service that asked CVAT who the caller was and then queried ClickHouse (ADR 0001). On 2026-11-15 the owner decided to merge it into the CVAT backend: a Django app, `cvat/apps/team_analytics/`, whose endpoints sit under `/api/team-analytics/` behind CVAT's own permission system. The owner's condition was that the feature must not slow the backend down, so the API process does no analytical work. It checks access, looks the answer up in the Redis cache, and on a miss queues the read for a dedicated worker and waits briefly; if the answer is not ready it replies `429` with `Retry-After`, which the client retries by itself. The worker, one Deployment of the fork server image, runs both the reads and the periodic refresh. This is how upstream already serves frame chunks.

## Considered Options

- **A separate service (ADR 0001, as built).** It isolates by being another process, and it keeps the stock backend. It also keeps its own access code, its own cache of CVAT's answers, an HTTP server, a lease in ClickHouse, an image, manifests and a route. An endpoint inside CVAT was what the owner first asked for; ADR 0001 never weighed it, because the backend was not in the tree.
- **A second API server of the same image, with the path routed to it.** The simplest code and the same isolation as the service. The isolation depends on a route that nothing checks: without it requests fall through to the main server and still work. It costs a whole API server in memory.
- **Queries in the API process, with a time limit, a cap on concurrent requests and a cache.** The least code and no extra pod. The Helm chart runs one API process per server pod, and the queries would still share it; the limits bound the damage and do not remove it.

## Consequences

- It replaces ADR 0001 as to where the code runs and who checks access. What ADR 0001 says about the figures stands: stored hourly totals, every calculation in SQL files, the trailing-window refresh, history filled a day at a time.
- It ends ADR 0004's "no Python change": the fork server image now carries the fork's backend tree, and a change to analytics code rolls out the backend image. The image is still the stock release with files copied over it, valid while the fork adds no Python dependency and changes nothing outside the copied paths; the build refuses otherwise.
- Access control stops being the fork's own code. A policy file and upstream's permission class replace the three calls to CVAT, their one-minute cache and the handling of malformed answers. A removed member is refused on the next request. An unknown organization is CVAT's own 404.
- An administrator with no organization selected still sees the whole instance. CVAT reads "no organization" as the personal workspace, so the app states this mapping itself; it is the one place where the app's scope differs from CVAT's context.
- The cached answer is keyed by the request: endpoint, scope, parameters and the hour. Access is checked before the cache is read, so an entry is never served across organizations. The worker stores each answer with the generation of the totals it was computed on, and the refresh advances the generation once at the end of a run that wrote. A stored answer is used only while its generation is the current one; a request that is already waiting takes any answer computed since it arrived. The generation is deliberately not in the key: with it there, a request that asked again while history was being filled queued a second job behind its own first, and that is how the first live run failed its load check.
- A worker process runs one read at a time, where the service answered on threads. The Deployment therefore runs several processes, and the refresh never takes more than one of them.
- The refresh is a periodic job. The lease in ClickHouse gives way to a Redis lock with an expiry; a step still proves it holds the lock before each write. Schema set-up and the first cutover search run when the first job finds them missing, since a backend has no service start.
- Reads gain what they lacked: a time and memory limit on every statement, a job timeout, and a cap on queued reads.
- The app is installed and its job scheduled only when analytics is enabled. With analytics off the endpoints do not exist. The queue alone is defined everywhere: CVAT removes a stored schedule only for queues it knows, so this is what clears the refresh schedule on an instance where analytics was switched off.
- Reads come before history. A run of the refresh job ends after a step as soon as a read is waiting, so filling history never keeps a worker process, or ClickHouse, from the people looking at the page. The refresh of recent hours is the first step of a run whenever it is due, and is never put off.
- Worker down, ClickHouse down, or a full queue shows as an error panel on the Team Analytics page and nothing else. This has to be shown on a running stack before the service is deleted, together with a load check on CVAT's own endpoints.
- The app depends on upstream internals that are not documented extension points: the permission base class, the periodic job list, the queue settings, the organization middleware, the entry point's component files and `core.server.request`. They are listed in the fork specification. Most changes to them fail at merge or test time.
- The endpoints are left out of the published schema, so `cvat/schema.yml` and the SDK do not change.
