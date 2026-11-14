# 03: Tracer runs on the stack

**What to build:** The behaviour from ticket 02 working in a browser against a real CVAT on the test stack. A fork maintainer builds both images with scripts, adds the service to the stack with manifests, and sees a signed-in maintainer's page show the working time of the loaded data. See the spec (`../spec.md`) and ADR 0003.

**Blocked by:** 01 (Test stack comes up and tears down), 02 (Tracer: working time per annotator for the last week).

**Status:** resolved

- [x] A script builds the UI image with the feature included, in the way the existing UI image is built.
- [x] A script builds the service image from the stock server image, with the service code and its SQL copied in and no added dependency.
- [x] Kubernetes manifests add the service to an installation: workload, service, configuration and the route under its prefix.
- [x] On the stack, the organization's maintainer signs in, opens Team Analytics from the header and sees working time per annotator that matches the events loaded for the run.
- [x] On the stack, the organization's worker sees no link, gets the "not available" state on a direct visit, and is refused when calling the service directly.
- [x] The refresh runs on its schedule in the stack without anyone triggering it.
- [x] The check is part of the one-command run from ticket 01 and leaves nothing behind.

## Comments

2026-11-14: Resolved on `feat/team-analytics-page` by merge `5cf1127`. Review fixes that followed are in merge `401576e`. Live results, review outcomes and what remains unverified: `docs/evidence/2026-11-14-team-analytics-final-run.md`.
