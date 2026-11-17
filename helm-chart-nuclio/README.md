# nuclio chart

This chart is the [Nuclio](https://nuclio.io) deployment that the `cvat` chart in
this repository used to pull in as a public Helm dependency
(`nuclio/nuclio`, version line `0.22.*`). It is vendored here as a normal chart
so it can be installed on its own (`helm install nuclio helm-chart-nuclio`) and
so a deployment can supply its own image and registry settings without forking
a third-party chart.

The templates are the upstream ones. Everything environment specific is a
value:

- all container images (controller, dashboard, autoscaler, dlx, kaniko and its
  init containers) are `*.image.repository` / `*.image.tag` values, and the
  defaults point at the public registries (`quay.io/nuclio/...`,
  `gcr.io/kaniko-project/...`, `docker.io/...`);
- registry push/pull/login URLs (`registry.pushPullUrl`,
  `registry.runRegistryURL`, `registry.loginUrl`,
  `registry.defaultBaseRegistryURL`, `registry.defaultOnbuildRegistryURL`,
  `registry.dependantImageRegistryURL`) are empty by default and are expected to
  be set by the deploying environment;
- the dashboard ingress host is `dashboard.ingress.hosts`, defaulting to
  `nuclio.local`, and is the only place the host appears.

No credentials are committed with this chart. Registry credentials are either
referenced by an existing secret (`registry.secretName`) or supplied at install
time as an extra values file.
