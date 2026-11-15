# 10: The test stack on the backend path

**What to build:** The launcher installs the chart with the analytics worker and checks the feature through CVAT's API. The service's manifests, proxy route and Ingress leave the stack.

**Blocked by:** 08, 09.

**Status:** resolved

- [x] `up` no longer applies or waits for the service, its route or its Ingress.
- [x] The tracer, final, access and fixes checks call `/api/team-analytics/`.
- [x] The check that read the service's log reads the worker's; the check that held the ClickHouse lease holds the Redis lock; the removed-member case no longer waits out a cache.
- [x] A stack of this checkout does not collide with a stack another checkout of the same user is running.
- [x] A fresh `up` passes.

## Comments

2026-11-15: `3fa20bc3`. The service's steps, image, proxy route and Ingress left the launcher; the render guard refuses any Ingress and requires the worker where analytics is on. The tracer waits for the status stamp to advance twice, the unprocessed check holds the Redis lock, the cutover check clears the ready mark, the removed-member case is judged on the next request. New: `check-worker` (in `up`), `check-cross-org`, `check-isolation`, `check-load`, `check-analytics-off`. The runs were made as a second stack (`TA_RUN_ID=fork`, port 8491, reserved in the machine's port table) beside the default one, which was not touched. Fresh `up`, second `up` and `down` passed on the final files (`docs/evidence/2026-11-15-backend-acceptance.md`).
