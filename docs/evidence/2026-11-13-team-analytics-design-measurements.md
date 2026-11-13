# Team Analytics design measurements — 2026-11-13

Evidence gathered while the Team Analytics design was being decided. It supports
[ADR 0001](../adr/0001-thin-analytics-service-with-stored-totals.md) and
[ADR 0003](../adr/0003-kubernetes-only-with-the-upstream-helm-chart.md). Nothing here
was run against a real CVAT installation: the ClickHouse figures come from synthetic
data, and the Helm chart was rendered, not installed.

## ClickHouse: can the figures be computed in SQL at production volume?

Files: [`2026-11-13-team-analytics-clickhouse-benchmark/`](2026-11-13-team-analytics-clickhouse-benchmark/)
(start with `NOTES.md`; queries are in `q/`, timings in `bench_report.txt`).

Setup: throwaway container, `clickhouse/clickhouse-server:23.11-alpine` (server 23.11.5.29),
6 CPUs and 10 GiB. The production `events` schema, 36,326,651 synthetic rows covering
2025-11-14 to 2026-11-13 (about 100,000 a day, 100 users, 40 projects), 2.44 GiB on disk.
Timings are second runs with a warm cache, taken from `system.query_log`.

| Calculation | 7 days | 30 days | 365 days |
| --- | --- | --- | --- |
| Working time per user and day | 0.01 s | 0.01 s | 0.12 s / 2 MiB |
| Counts per user, project and scope | 0.01 s | 0.02 s | 0.26 s / 12 MiB |
| Sessions (5-minute gap) | 0.05 s | 0.05 s | 0.48 s / 546 MiB |
| Time per operation, rectangle filter from payload | 0.05 s | 0.16 s | 1.94 s / 971 MiB |
| Navigation inside a drawing credited to the drawing | 0.07 s | 0.20 s | 2.29 s / 1.61 GiB |
| One alignment per object | 0.05 s | 0.13 s | 1.34 s / 1.35 GiB |
| Hotkey counters from payload | 0.03 s | 0.06 s | 0.56 s / 30 MiB |

Observed:

- Hourly stored totals: filling the year took 4.14 s and 2.81 GiB; refreshing the last
  48 hours took 0.11 s; reading 365 days took 0.02–0.03 s. A refresh that also reads the
  300 seconds before its window matched the direct queries with no differing group over
  the year. Without that look-back, a boundary at 10:00 gave 7 extra sessions and 953 s
  less session time.
- Concurrency under the 6-CPU cap: the 365-day time-per-operation query took 1.9 s alone,
  4.5 s with two copies and about 15.5 s with four.
- With default settings the 365-day queries that read `payload` inside a window failed
  with "Memory limit (total) exceeded". With `query_plan_execute_functions_after_sorting = 0`
  they ran as in the table, with identical results.
- `simpleJSONExtractString` returned an empty string on payload text with a space after
  the colon; `JSONExtractString` worked. The spacing was taken from this repository's
  fixture generator, not from a production row.
- `CREATE MATERIALIZED VIEW ... REFRESH EVERY` is a syntax error in 23.11.5.29 and the
  experimental setting is unknown, so this version cannot schedule a refresh itself.

Not measured: cold cache, unmerged production parts, events arriving more than 48 hours
late, real payload sizes, and ClickHouse 23.12.2, which the Helm chart runs.

The benchmark queries encode the measurer's reading of the rules at that moment. Two
agreed definitions differ and were not timed: a session counts for every project it
touched (the benchmark stores it under the project where it started), and an alignment
also ends when the person leaves the frame. The fixture expectations in `NOTES.md` are
the benchmark's own, not acceptance criteria.

## Helm: can the upstream chart be installed on the local cluster?

Files: [`2026-11-13-team-analytics-helm-check/`](2026-11-13-team-analytics-helm-check/)
(`values.local.yaml` is the minimal values file; the rendered manifests were not kept
because they contain the chart's default credentials).

Ran, with Helm v3.16.3 against the chart from upstream commit
`02bd74fde78e00f770b7dfc3c33761ad9ab00095` (v2.82.0): `helm dependency update` and
`helm template --kube-version v1.36.1`. Nothing was installed and no image was pulled.

- All seven subcharts resolved (`dep-update.log`). There is no upstream `Chart.lock`, so
  versions were resolved on the day: postgresql 12.1.15, clickhouse 4.1.16, redis 19.6.4,
  nuclio 0.22.13, vector 0.19.2, grafana 6.60.6, traefik 37.3.0.
- The minimal values rendered without errors: 11 steady pods and one initializer job
  (20 pods with chart defaults), five volume claims, all sizes overridable, no
  cluster-scoped object once `grafana.rbac.namespaced` is set.
- Images present in registries but not on this machine (`registry-check.txt`,
  `local-check.txt`): `cvat/server:v2.82.0`, `apache/kvrocks:2.15.0`,
  `cvat/clickhouse:23.12.2-debian-11-r0`, `cvat/postgresql:15.2.0-debian-11-r0`,
  `redis:7.2.11`, `grafana/grafana:10.1.5`, `busybox:1.36.1`. The values file names a
  frontend tag, `cvat/ui:test-local`, that has to be built.
- With ingress off, every Service is ClusterIP and the frontend image does not proxy
  `/api`, so one address for UI, API and an extra service needs a reverse proxy.
- Most containers declare no resource requests.
- The chart has no hook for extra objects of its own; additional manifests are separate.

Not determined: whether the local `hostpath` storage class binds a ReadWriteMany claim
(avoided by the ReadWriteOnce override), and any runtime behaviour.
