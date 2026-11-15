---
status: accepted
---

# The backend runs a fork server image that adds the patched policies and nothing else

The patched issue and comment policies reached a server only through bind mounts in a Compose overlay. That mount went stale unnoticed when upstream moved the installed sources, and nothing delivered the policies on Kubernetes, the only supported target (ADR 0003). On 2026-11-14 the owner decided to deliver them in a fork server image: the stock release image with the two patched policy files copied over the stock ones. The chart has one backend image setting, so the server and every worker run it. The image holds no Python change and no added dependency, so everything except those two policies behaves as the stock release does, and the premise of ADR 0002 (the events API is not ours to change) stands.

## Considered Options

- **A ConfigMap mounted over the stock files through the chart's extra volumes.** No third image to build. The owner chose the image. A mount keeps the weakness that prompted this decision: when upstream moves the directory, the mount lands somewhere the server does not read and nothing fails.
- **Converting the repository into a full-source fork.** Drafted on 2026-11-14 and dropped by the owner the same day; the draft is in history up to commit `fb3148e`.

## Consequences

- It reverses three written rules: the Team Analytics specification's "the backend stays the stock image" and its out-of-scope line on changing the stock backend, as far as the policies go; the fork specification's BUILD-1 ("the custom image tag belongs only to the UI"); and ADR 0003's "two custom images".
- The image is rebuilt on every upstream upgrade and whenever a policy changes, and like the other two it must be present on the node.
- The policies are edited in place inside the import, which the owner widened to bring the stock policy files in; the copied `opa/` directory and the Compose overlay that mounted it go away.
- The Team Analytics service keeps its own image on the stock base, so a change to analytics code never rolls out the CVAT backend.

## Amendments, 2026-11-15

- **The image is no longer "nothing else".** With Team Analytics inside the backend ([ADR 0006](0006-team-analytics-inside-the-backend-with-reads-on-a-worker.md)) the fork server image carries the fork's backend tree: the patched policies and the Team Analytics app. It is still the stock release image with files copied over it, and still holds no added dependency. The last consequence above, that a change to analytics code never rolls out the CVAT backend, no longer holds.
- **The policies are edited in the tree, not in an import.** The repository became a full-source fork ([ADR 0005](0005-a-full-source-fork-joined-to-upstream-history.md)); the policies sit at upstream's paths, and a release is merged, not re-imported.
- **The second considered option was taken after all.** The conversion to a full-source fork, dropped on 2026-11-14, was decided by the owner on 2026-11-15.
