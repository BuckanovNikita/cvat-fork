# Team Analytics test stack: pinned chart and first runs (2026-11-13)

Evidence for ticket 01 (test stack). Tooling: `verify/team-analytics-stack/`.

## Chart source

- Upstream `cvat-ai/cvat` raw commit `02bd74fde78e00f770b7dfc3c33761ad9ab00095` (tag v2.82.0,
  `docs/evidence/2026-11-13-fork-baseline.md`), downloaded as the commit archive from
  `codeload.github.com`. Only `helm-chart/` and `components/analytics/` (the target of the
  chart's `analytics` symlink) are kept, in
  `${XDG_CACHE_HOME:-$HOME/.cache}/cvat-fork/team-analytics/upstream-<commit>/`.
- The chart ships no `Chart.lock`; its `Chart.yaml` gives ranges.

## Resolved dependency versions

`helm dependency update` on the pristine chart, 2026-11-13 20:38 +03:00, helm v3.16.3:

| Dependency | Range in Chart.yaml | Resolved | Repository | sha256 of archive |
|---|---|---|---|---|
| postgresql | 12.1.* | 12.1.15 | https://charts.bitnami.com/bitnami | 91b472ac9d855bfba4ab973a577074a638c17d74eccb4dcaa5a7d7924cec7b92 |
| nuclio | 0.22.* | 0.22.13 | https://nuclio.github.io/nuclio/charts | 173d117a783953c8836b63eb08bc4fb010f7863ab7d4a2056fd010ba8f136848 |
| vector | 0.19.* | 0.19.2 | https://helm.vector.dev | a2ec56c1c734e5ddc0ed7860c74825c84564628973bc7d3b0c0b5562efe65157 |
| clickhouse | 4.1.* | 4.1.16 | https://charts.bitnami.com/bitnami | ed85b749dfa895e5a21daad3eb5f71ad0603e26aa66608a2bd95dc52d2725573 |
| grafana | 6.60.* | 6.60.6 | https://grafana.github.io/helm-charts | 2d649a7e824c4318b62bcd1b7e35461cb0215b527cc87e46f5f66aa6e3d06d05 |
| traefik | 37.3.* | 37.3.0 | https://helm.traefik.io/traefik | 5e09f73c9ef20982b58769da9ddaac0ee49841aa482084b1a6b08ac996f49ffb |
| redis | 19.6.4 | 19.6.4 | https://charts.bitnami.com/bitnami | 488b39d7dbf107c3749aedb11fd76a8be04762de91920d1b607590ffdd99bd9d |

Lock digest `sha256:c44563b1315781bc38610e1575f6d096d1495eafaa2c362cbeebbacbbb4e2c6b`.
The generated lock is committed as `verify/team-analytics-stack/Chart.lock` and the archive
hashes as `verify/team-analytics-stack/chart-deps.sha256`. The tooling copies the lock into
the cached chart, runs `helm dependency build` (exact versions, private repository list)
and refuses archives whose hashes differ. Two later builds from the lock the same evening gave
identical hashes. nuclio and traefik are downloaded but disabled.

## Images of the render

`helm template` with `verify/team-analytics-stack/values.yaml`: `cvat/server:v2.82.0`,
`busybox:1.36.1`, `apache/kvrocks:2.15.0`, `openpolicyagent/opa:1.12.2`,
`docker.io/cvat/clickhouse:23.12.2-debian-11-r0`, `docker.io/cvat/postgresql:15.2.0-debian-11-r0`,
`docker.io/library/redis:7.2.11`, `docker.io/grafana/grafana:10.1.5`,
`timberio/vector:0.26.0-alpine`, plus the UI image. Grafana's test pod
(`docker.io/bats/bats:v1.4.1`) is disabled with `grafana.testFramework.enabled: false`.
The render has no cluster-scoped kinds (checked against `kubectl api-resources
--namespaced=false` by the tooling on every run).

## Host port

Reserved 8490 (TCP) in the k8s-infra host port table on 2026-11-13. A first hold of the
table's `flock` took this snapshot: no WSL listener on 8480-8499
(`ss -ltnup`), no Docker published port, no Kubernetes LoadBalancer/NodePort on it (only
ingress-nginx 80/443 and mongodb-lb 27018), no Windows TCP listener or UDP endpoint on
8480-8500 (`Get-NetTCPConnection`, `Get-NetUDPEndpoint`), not in a Windows excluded range
(`netsh ... show excludedportrange`; lowest project-relevant ranges 1462, 2869, 10243,
13508, 49733+), and below the Windows dynamic range (49152-65535) and the Linux ephemeral
range (32768+). The table edit ran under a second hold of the lock, which re-read the
table (no 848x/849x row) and rechecked the WSL listeners only. The row is live in the
installed skill (read back through its link) but not committed in the k8s-infra checkout.

## Runs (2026-11-13, docker-desktop, namespace `cvat-ta-it-nkt`)

1. `run.sh up` on an empty cluster: pulled `apache/kvrocks:2.15.0`, `busybox:1.36.1`,
   `cvat/postgresql:15.2.0-debian-11-r0`, `grafana/grafana:10.1.5`, `redis:7.2.11` one at a
   time (`cvat/server:v2.82.0` and `cvat/clickhouse:23.12.2-debian-11-r0` were already
   local). Thirteen pods, five PVCs of class `hostpath` (2Gi backend data, 1Gi kvrocks,
   2Gi ClickHouse, 1Gi PostgreSQL, 1Gi Redis). Quota use: pods 13/30, requests 1470m/6 CPU
   and 3488Mi/12Gi, limits 24650m/40 CPU and 38208Mi/56Gi. Seeding failed on the first
   attempt (`auth.User` is swapped for `iam.User`; fixed), then `seed` and `check-event`
   passed: every account's groups and every membership role read back through the API, and
   a `debug:info` event sent by `ta-worker` through `POST /api/events` at
   `http://localhost:8490` appeared in `cvat.events` with its payload key
   `shape_type = rectangle`.
2. Proxy checks: `/team-analytics-api/x` 503 (reserved), `/team-analytics` 200 (UI),
   `/analytics/` 401 without credentials and 200 for `ta-admin`.
3. Namespace deleted directly with `kubectl delete ns` (as the sweeper would), then
   `run.sh up`: namespace recreated, stale port-forward stopped by PID and start time, all
   steps passed in 69 s.
4. `run.sh up` again on the running stack: passed (helm upgrade, reseed, new event found).
5. `run.sh down`: port-forward stopped, namespace and its PVs gone in 53 s. `run.sh down`
   again: succeeded with nothing to remove. Afterwards no namespace, no PV bound to it, port
   8490 free, no port-forward process, no cluster-scoped object named after the chart's
   components.
6. Fixes after review: the cluster-scoped kind list now takes the KIND column without
   `-o wide` (the earlier parse missed kinds that have categories, such as
   CustomResourceDefinition; the post-teardown listing above is independent of it), the
   private helm repository list is scoped to the dependency build, and the temporary render
   is removed on exit. Then `run.sh cycle` from an empty build cache (dependencies rebuilt
   from the lock, hashes matched): passed in 2 min 19 s; a second `cycle` and a `down` on
   nothing passed; namespace, PVs, port-forward and port 8490 gone afterwards. The user's
   helm repository list was unchanged (ingress-nginx, external-secrets, minio, lakefs,
   clearml).
