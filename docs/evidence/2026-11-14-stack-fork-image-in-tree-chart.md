# Test stack on the fork server image and the in-tree chart, 2026-11-14

Ticket 08 of the defect fixes (plan rows 1.3a and the bundle check of 1.3b; ADR 0003
amendments, ADR 0004). `verify/team-analytics-stack/run.sh` now takes the chart from the
import, runs the backend on the fork server image and checks the policy bundle the running
server serves.

This file holds part one: what was checked without installing anything into the cluster.
No `up`, `cycle` or `seed` ran, no namespace was created, no image was built or pulled.
Part two (a fresh `up` from an empty namespace, `down`, the captured logs) is listed at the
end and has not run.

## What changed

- The download of the upstream source archive is gone, with its settings
  (`TA_UPSTREAM_COMMIT`, `TA_UPSTREAM_ARCHIVE_URL`) and its cache (`upstream-<commit>` and
  `build-<commit>-<lock>` under `TA_CACHE_DIR`). `build_chart` copies `cvat/helm-chart` and
  `cvat/components/analytics` (the target of the chart's `analytics` link) into
  `TA_CACHE_DIR/chart-<hash>`, adds the stack's `Chart.lock` and runs `helm dependency build`
  there, then checks the archives against `chart-deps.sha256` as before. `<hash>` covers the
  two trees as they are in the working tree and the lock, so any change builds afresh. The
  copy exists because `helm dependency build` writes `Chart.lock` and `charts/` into the
  chart directory; the import stays untouched. `TA_CACHE_DIR` stays as the working
  directory for that build, Helm's repository index cache and the port-forward state.
- `TA_SERVER_IMAGE` (default `cvat/server:v2.82.0-fork-policies`) is set as
  `cvat.backend.image` and `cvat.backend.tag`; `values.yaml` sets the backend pull policy
  to `Never`.
- New functions, each called from `up`: `check_server_image` (first step of `up`, before
  the chart build), `check_backend_image` (after the render guard), `check_policies` (right
  after the port-forward, before the seed). `preflight` is everything `up` does before its
  first change to the cluster or the image store.
- New subcommands: `preflight`, `render`, `check-render FILE`, `check-policies`,
  `check-bundle` (a bundle on stdin). `fetch-chart` is renamed `build-chart`, since it no
  longer downloads a chart.
- `cvat/server:v2.82.0` stays in `TA_APPROVED_PULLS`: the stack no longer runs it, but it
  is the local base of the fork server image and of the service image (whose build scripts
  never pull) and the service suite runs it. `check_backend_image` refuses a render that
  names it, so it cannot reach the release although it is approved and local.

## Checks with supplied boundaries

All Helm commands ran through the heavy lock, lane A. The cluster was only read
(`kubectl api-resources` in the render guard, `kubectl get ns` before and after).

### The chart comes from the import

- The pre-change cache held the upstream archive's `helm-chart/` and
  `components/analytics/` of commit `02bd74f`. `diff -r` (links not followed) against
  `cvat/helm-chart` and `cvat/components/analytics` of this branch: no difference. The
  import is the same chart, so the render comparison below isolates this ticket's changes.
- `build-chart` with `TA_CACHE_DIR` set to a fresh directory under the home directory, so
  no earlier build or archive could stand in: exit 0. Its output shows `repo add` for the
  five repositories, "Saving 7 charts", one "Downloading" line per dependency, and the build
  directory as `~/.cache/cvat-fork/<fresh>/chart-1ae40b02e8ddd520/helm-chart`. No
  `codeload` request is made; nothing in the launcher names it any more.
- In that build: `sha256sum -c chart-deps.sha256` reports `OK` for all seven archives; its
  `Chart.lock` equals the stack's; the chart directory, without `charts/` and `Chart.lock`,
  equals `cvat/helm-chart` (`diff -r`, links not followed) and the copied analytics component
  equals `cvat/components/analytics`; `analytics` still links to `../components/analytics/`.
- `git status` after the build: only the launcher files this ticket edits; nothing under
  `cvat/`.

### The render

The genuine render needs a local UI image to pass the guard; the default
`cvat/ui:v2.82.0-team-analytics` is not built on this machine. Both renders used
`TA_UI_IMAGE=cvat/ui:v2.82.0-team-analytics-review-fixes-2-2c900d3`, a local tag, and the
default release and namespace.

- Previous render: the pre-change launcher's arguments against the pre-change cached chart,
  rendered twice. The two renders differ in two lines by themselves: Grafana's generated
  `admin-password` and the `checksum/secret` annotation computed from it.
- New render: `run.sh render`. Against the previous render it differs in those two lines and
  in 11 containers, each by exactly two lines, `image: cvat/server:v2.82.0` to
  `image: cvat/server:v2.82.0-fork-policies` and `imagePullPolicy: IfNotPresent` to
  `Never`. The 11 are the server deployment's two backend containers, the eight worker
  deployments (all eight are rendered, six with zero replicas) and the initializer job.
  Nothing else differs.
- `run.sh preflight` (the same build, the same UI tag): exit 0, "preflight passed". The set
  of namespaces and the set of local image IDs were the same before and after.

### The render guard, on doctored renders

One fault per copy of the genuine render, each given to `run.sh check-render`:

| Copy | Fault | Result |
| --- | --- | --- |
| genuine | none | "render accepted", exit 0 |
| cluster role | a `ClusterRole` document appended | "cluster-wide kind in render: ClusterRole", refused, exit 1 |
| unapproved image | one `busybox:1.36.1` replaced by `example.invalid/unapproved:1` | "image neither local nor approved", refused, exit 1 |
| forced pull | one `imagePullPolicy: Never` replaced by `Always` | "render forces image pulls", refused, exit 1 |
| one stock backend | one fork server image replaced by `cvat/server:v2.82.0` (local and approved) | "server image other than the fork server image in render", refused, exit 1 |
| all stock backend | all 11 replaced | the same, plus "the fork server image ... is not in the render", refused, exit 1 |

### The launcher refuses to start without the fork server image

`TA_SERVER_IMAGE=cvat/server:v0.0.0-absent run.sh preflight`, with a `TA_CACHE_DIR` that did
not exist: exit 1, "fork server image cvat/server:v0.0.0-absent is not local
(IMAGE=... ./build-server.sh); it is never pulled". The cache directory was still absent
afterwards and the namespace count unchanged, so it stopped before the chart build. `up`
calls the same `preflight` first, so it stops at the same point; `up` itself was not run.

### The bundle check, without a cluster

`check-bundle` runs the code `check_policies` runs on the fetched bundle. Bundles came from
`verify/policy_bundle.sh from-image` (the server's own bundle builder in a one-off container,
no network, one core), one image at a time:

| Bundle | `policy_bundle.sh check` part | Marker part | Result |
| --- | --- | --- | --- |
| `cvat/server:v2.82.0-fork-policies` | both `equal` | both "the patched policy" | passed, exit 0 |
| `cvat/server:v2.82.0` | both `DIFFERS` | both "not the patched policy" | failed, exit 1 |
| fork bundle with the stock `issues.rego` | `issues` differs, `comments` equal | `issues` not patched, `comments` patched | failed, exit 1 |
| fork bundle with the stock `comments.rego` | `issues` equal, `comments` differs | `issues` patched, `comments` not patched | failed, exit 1 |

The first try of the mixed bundles found a fault in the check: it read each policy with
`tar -xzOf bundle rules/<name>`, which misses a member stored as `./rules/<name>` (the
repacked bundles are stored that way) and so reported both policies unpatched. The check now
unpacks the bundle and reads the files, as `policy_bundle.sh` does; the rows above are after
that change.

### No local path in the captured output

Every output captured above (build, preflight, renders and their diff, doctored renders,
bundle checks): no match for the home directory or for `/home/<user>`.

## Not verified

- No release was installed: the backend pods' actual images, the served bundle at
  `/api/auth/rules` through the proxy (whether it answers without credentials, as the
  chart's OPA polls it, is read from the chart, not seen), every existing check of `up`, and
  `down` are part two.
- `chart-deps.sha256` refusing a different archive was not provoked; that code is unchanged.

## Part two, not run yet

Needs the orchestrator's word (a UI image build and a stack `up`), both heavy lanes free.

1. `IMAGE=cvat/ui:v2.82.0-team-analytics ./build-ui.sh` and
   `IMAGE=cvat/team-analytics:v2.82.0 ./build-team-analytics-service.sh` from this branch;
   `cvat/server:v2.82.0-fork-policies` is already local.
2. `kubectl --context docker-desktop get ns cvat-ta-it-$USER` must report it absent, then
   `verify/team-analytics-stack/run.sh up 2>&1 | tee <log>`: exit 0, with "policy bundle
   check passed" after the port-forward and every later check passing.
3. While it is up: every backend pod (`tier=backend`) runs
   `cvat/server:v2.82.0-fork-policies` (`kubectl get pods -o jsonpath` of the container
   images).
4. `verify/team-analytics-stack/run.sh down`: "nothing of ... remains"; afterwards no such
   namespace and no persistent volume bound to it.
5. `grep -c -i -F "$HOME" <log>` and the same for `/home/$(id -un)`: 0 each.
