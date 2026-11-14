# 01: Test stack comes up and tears down

**What to build:** One command gives a fork maintainer a disposable CVAT v2.82.0 with analytics on the local Kubernetes cluster, reachable at one address, and removes it again. It is the place every later ticket is verified against a real CVAT. Definitions and constraints are in the spec (`../spec.md`) and ADR 0003.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] One command creates a namespace with a project-specific name, a resource quota and default limits, and recreates it if it has disappeared.
- [x] CVAT is installed from the upstream Helm chart for the pinned upstream commit, with analytics on and the smallest set of workers the chart allows.
- [x] The chart is downloaded into a cache outside the fork's filtered import, and its dependency versions are pinned to those in the dated evidence.
- [x] A reverse proxy in the namespace joins the UI and the CVAT API under one address and leaves a prefix free for the analytics service; the address is reached through the reserved forwarded host port.
- [x] The run loads an administrator, an organization with an owner, a maintainer, a supervisor and a worker, a user who is a member of nothing, and a second organization with its own maintainer.
- [x] A client event sent through the CVAT API as one of those users appears in the events table.
- [x] Teardown removes everything the run created, including volume claims the chart marks to keep, and succeeds when nothing exists.
- [x] Nothing cluster-wide is created, storage uses the default class, and only resources created by the run are touched.
- [x] The run needs no manual step; what it needs from the machine (network access, the approved images) is stated where a maintainer will read it.

## Comments

2026-11-14: Resolved on `feat/team-analytics-page` by merge `e9d073d`. Review fixes that followed are in merge `401576e`. Live results, review outcomes and what remains unverified: `docs/evidence/2026-11-14-team-analytics-final-run.md`.

2026-11-14: Note on the forwarded host port: 8490 is reserved in the k8s-infra host port table as an edit that is not committed in that repository (`skills/k8s-infra/SKILL.md`).
