---
status: accepted
---

# Team Analytics targets Kubernetes only and is verified on the upstream Helm chart

The feature is delivered and verified on Kubernetes against CVAT v2.82.0 and nothing else. It ships as two custom images built by scripts in this repository (the UI, and the analytics service built from the stock server image) plus Kubernetes manifests for the service. Verification runs in a disposable namespace of the local cluster where CVAT itself is installed from the upstream Helm chart, with our service and a small reverse proxy added beside it as separate manifests. The Compose overlay in this repository is not extended for this feature, and the air-gapped production installation is out of scope.

## Considered Options

- **Our own minimal manifests mirroring the Compose file.** Fewer pods and no chart dependencies, but a second description of CVAT to keep in step with every upgrade. Rejected once the upstream chart was shown to resolve and render here.
- **Extending the existing Compose verification.** It is the current practice, but the repository's infrastructure migration removes Compose launchers, and the owner requires Kubernetes.

## Consequences

- The chart is not part of the fork's filtered source tree, so it has to be obtained from the matching upstream release.
- The stack needs network access when it is built and when it starts: chart dependencies, stock images, and Grafana's ClickHouse plugin.
- With the chart's ingress off, nothing joins the UI, the API and the service under one address. The reverse proxy in the namespace does that, reached through a forwarded host port. The chart's Traefik option was not used because it adds cluster-wide objects to a shared cluster.
- Most chart pods declare no resource requests, so the namespace needs default limits alongside its quota.
- The chart runs a newer ClickHouse than the Compose file. The design must not depend on anything that differs between the two.
- The two existing Compose checks (task progress, issue permissions) are not migrated by this work.
