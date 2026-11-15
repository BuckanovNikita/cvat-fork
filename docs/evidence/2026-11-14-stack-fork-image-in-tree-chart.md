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
  directory as `~/.cache/cvat-fork/<fresh>/chart-1ae40b02e8ddd520/helm-chart`.
  The network was not traced; what shows the download is gone is the tree:
  `git grep -E 'codeload|TA_UPSTREAM|fetch-chart|fetch_upstream' -- verify/team-analytics-stack`
  finds nothing.
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

### The fetch, read and run without a stack

- Read: the proxy's `/api` location (`proxy.yaml`) passes straight to the backend, with no
  auth subrequest.
- Read in the fork server image (a one-off container, no network, one core):
  `cvat/apps/iam/views.py` `RulesView` has `permission_classes = [AllowAny]` and
  `authentication_classes = []`, and `iam/urls.py` routes `rules` to it. It returns
  `get_opa_bundle()[0]`, the same bytes `policy_bundle.sh from-image` writes.
- `run.sh check-policies` with no stack (nothing on the host port): curl cannot connect,
  "could not fetch .../api/auth/rules", exit 1. It fails closed.

### No local path in the captured output

Every output captured above (build, preflight, renders and their diff, doctored renders,
bundle checks): no match for the home directory or for `/home/<user>`.

## Part two: the live run, 2026-11-14 (UTC evening)

Run from branch `ticket/08-stack` at the integration tip `2bd0d1b8` (with tickets 09, 10 and
11's checks in `up`), then at `1333fd89` after the fixes below. Images, all local and built
from `3dc1a7bc`: `cvat/ui:v2.82.0-team-analytics` (`310e9bbc6a47`),
`cvat/team-analytics:v2.82.0` (`42d4bb9ab97e`), `cvat/server:v2.82.0-fork-policies`
(`4b38c649ae96`). None was rebuilt. Logs are quoted with the user name in the namespace left
as it is; no log line below holds a local path.

### Before the start

- `verify/policy_bundle.sh from-image cvat/server:v2.82.0-fork-policies | run.sh check-bundle`:
  both policies `equal` and patched, "policy bundle check passed".
- `run.sh preflight`: the default cache had no build of the in-tree chart, so it ran
  `repo add` for the five repositories and downloaded the seven archives, checked them
  against `chart-deps.sha256`, rendered and checked the render: "preflight passed".
- `kubectl get ns cvat-ta-it-<user>`: NotFound. Nine namespaces existed, none of this tool's.

### First `up`, from the empty namespace (at `2bd0d1b8`)

It created the namespace, installed the release, applied the service, the proxy and the
Ingress, and waited for the workloads. Then, in order:

| Step | Result |
| --- | --- |
| backend pods | initializer `cvat/server:v2.82.0-fork-policies`; server: init `busybox:1.36.1`, both containers the fork image; worker-utils: init `busybox:1.36.1`, the fork image; worker-webhooks: the fork image. No other `cvat/server` image |
| `check_policies` | "checking the policy bundle served at http://localhost:8490/api/auth/rules"; `rules/issues.rego` and `rules/comments.rego` each "is the patched policy"; "policy bundle check passed" |
| `seed` | passed |
| `check_ingress` (ticket 11) | `PASS ingress: status through the Ingress ...: 200 with a session, 401 not_authenticated without` |
| `check_event` | the event found in ClickHouse for `ta-worker` with `shape_type` `rectangle` |
| `check_tracer` | figures from one scheduled refresh; page as `ta-maintainer` and `ta-worker` as expected |
| `check_task_progress` (ticket 10) | "task progress check passed" |
| `check_final` | **failed**, `TypeError: 'NoneType' object is not iterable` in `final_run.py` `check_ui_figures`, `ready` |

`check_issues` and `check_access_cases` were not reached; `up` exited 1.

Cause of the `check_final` failure (ticket 08's): the history of the synthetic volume was
still being processed when the figures were first read, and since ticket 14 a period that is
not fully processed carries null rows. `ready()` indexed those rows instead of waiting. Its
second wait (`volume figures`) tested `processed` only after reading a figure. Both now test
`processed` first. A rerun (`run.sh check-final`) then failed on a second stale expectation:
the by-project row was compared whole, and since ticket 23 each row also carries its
operation parts (`seed check failed: by project {... 'operations': {...}}`). The check now
matches the project and its working time. The next `run.sh check-final` passed ("final run
passed"). These are fixes to the stack's check script (tooling, stated checks).

The first `up` log held the home directory six times, all in that Python traceback, which
`show_path` cannot reach. The launcher now passes its whole stderr, and that of every tool it
runs, through `redact_paths` (repository root as `.`, the home directory by each of its names
as `~`). Stated check: `TA_HOST_PORT=1 run.sh check-event` (a refused connection, a
traceback through `stack_api.py`): with the filter switched off by `TA_STDERR_REDACTED=1`,
five lines hold the home directory; with it, none, and the traceback names
`./verify/team-analytics-stack/stack_api.py`.

The two checks `up` had not reached, by their own subcommands: `run.sh check-issues`
("issue matrix passed: 124 rows") and `run.sh check-access` (`PASS` for removed-member,
group-admin, personal-workspace, and header-credentials with Basic and Bearer).

### Second `up`, on the same stack (at `1333fd89`)

The namespace was reused (`unchanged`), the release upgraded, the port-forward restarted.
Every check passed in one run, in `up`'s order: "policy bundle check passed", seed,
`PASS ingress`, the event in ClickHouse, the tracer's scheduled refresh, "task progress check
passed", "final run passed" (project figures ready after 18 s, volume, trends, list, access
of every account to every endpoint, page, service stopped and restarted), "issue matrix
passed: 124 rows", the five access-case `PASS` lines, then
`up:http://localhost:8490 (accounts: see README.md, password $TA_SEED_PASSWORD)`, exit 0.
Its log holds no match for the home directory or for `/home/<user>`.

### State left

The stack stays up for the live parts of tickets 09, 10, 11, 25 and 26: namespace
`cvat-ta-it-<user>`, every pod Running (the initializer Completed), the port-forward
running, `http://localhost:8490`. `down` was not run.

## Not verified

- `down` leaving nothing behind: not run; the stack is kept for the next tickets' live work.
- A single `up` from an empty namespace passing every check: the fresh `up` stopped at
  `check_final` (fixed since); every check then passed on that stack, and a second `up` on it
  passed every check, but no `up` from an empty namespace has passed end to end.
- A served bundle with a stock policy was not provoked on the stack; the failing verdicts are
  those of `check-bundle` on the stock and mixed bundles in part one.
- `chart-deps.sha256` refusing a different archive was not provoked; that code is unchanged.

## Part two, the list it ran from

Steps 1 to 5 and 7 ran as above (step 1 by the orchestrator); step 6 is outstanding.

1. `IMAGE=cvat/ui:v2.82.0-team-analytics ./build-ui.sh` and
   `IMAGE=cvat/team-analytics:v2.82.0 ./build-team-analytics-service.sh` from the final head;
   `cvat/server:v2.82.0-fork-policies` is already local.
2. `verify/policy_bundle.sh from-image cvat/server:v2.82.0-fork-policies | verify/team-analytics-stack/run.sh check-bundle`:
   "policy bundle check passed" (catches a server image older than the import's policies
   before a stack start).
3. `verify/team-analytics-stack/run.sh preflight` on the final head: "preflight passed". The
   default cache holds no build of the in-tree chart, so this step downloads the seven
   dependency archives (network) and checks them against `chart-deps.sha256`.
4. `kubectl --context docker-desktop get ns cvat-ta-it-$USER` reports it absent; then
   `verify/team-analytics-stack/run.sh up 2>&1 | tee <log>`: exit 0, with "policy bundle
   check passed" right after the port-forward and every later check passing.
5. While it is up: `kubectl --context docker-desktop -n cvat-ta-it-$USER get pods -l tier=backend -o jsonpath='{..image}'`
   names no `cvat/server` image other than `cvat/server:v2.82.0-fork-policies` (the pods also
   carry `busybox:1.36.1` init containers). Only the server, utils and webhooks workers and
   the initializer have pods; the other six workers have zero replicas.
6. `verify/team-analytics-stack/run.sh down`: "nothing of ... remains"; afterwards no such
   namespace and no persistent volume bound to it.
7. `grep -c -i -F "$HOME" <log>` and the same for `/home/$(id -un)`: 0 each.
