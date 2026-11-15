# 08: The analytics worker in the chart and the backend tree in the image

**What to build:** The chart gains a Deployment for the analytics worker, and the fork server image carries the fork's backend tree.

**Blocked by:** 05.

**Status:** resolved

- [x] The chart renders the worker Deployment only when analytics is enabled, with a configurable number of processes (default 3) and the same environment as the other workers.
- [x] With analytics disabled the chart renders as upstream's does.
- [x] The fork server image is the stock release image with the fork's `cvat/` tree and the entry-point component file copied over it; it builds without network.
- [x] The build refuses when the fork's tree differs from the release in the Python requirements, the entry point or the process configuration.
- [x] The image's own bundle builder still yields the two patched policies, and now the Team Analytics policy.
- [x] The render guard accepts the new Deployment.

## Comments

2026-11-15: `211e79a2` (template), `9c0d8248` (image). The stack's render holds `cvat-backend-worker-team-analytics` with `run worker team_analytics`, `NUMPROCS` 3 and a liveness probe for three workers. The template's values have their defaults in the template; upstream's `values.yaml` is not edited. `./build-server.sh` built `cvat/server:v2.82.0-fork` without network and its three bundle checks passed. Record: `docs/evidence/2026-11-15-full-fork-conversion.md`.

Open: the render with analytics disabled and the render guard, which the stack work shows; the refusal cases of the build script were read, not provoked.

2026-11-15: The launcher's `preflight` renders the chart with analytics on and off: the worker is required in the first and absent from the second (11 Deployments), and the render guard accepts both. The build's refusal was provoked once: with `STOCK_TAG` naming a tree that lacks the files the image is built from, `build-server.sh` listed them, said the image cannot stand in for upstream's own build, and tagged nothing. The refusals for a deleted file and for an unchanged tree were read, not provoked.
