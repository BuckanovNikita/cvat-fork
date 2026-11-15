# Security review of the branch (ticket 28), 2026-11-15

Ticket: `.scratch/defect-fixes/issues/28-security-review-of-the-branch.md`. Part one is the
review's report, shortened only where it located the owner's personal e-mail address or the
machine (commit ids and dates of those commits, the home prefix, the account name). Part two is
what was done about each finding. Part three is what is outstanding.

## Part one: the review's report

Reviewer: a fresh agent that wrote none of the code. Reviewed commit `fe87ffaf`, detached in its
own worktree. It changed no tracked file, touched no cluster object and built no image. Run, all
without a cluster:

- a scan of every blob and commit message reachable from `6cedd049` (the push of 2026-11-14) and
  of the range `6cedd049..fe87ffaf`, blobs equal to a blob of an import tree left out, every
  binary blob opened, and a second pass for key material, encoded runs and Kubernetes secrets;
- a policy probe comparing the patched and stock issue and comment policies over 8,960 inputs
  each, in the local OPA image (no network, one CPU);
- a probe on the service's test harness (`verify/team_analytics_service.sh`, default ClickHouse
  image, one added test module on a copy of the service tree): a forged client event from an
  outsider;
- an idle-connection probe against the service's real HTTP server with a stub service (loopback);
- a replay of the earlier reviews' doctored renders and adversarial bundles, plus seven new
  renders, against `render_guard.py` and `policy_bundle.sh check` (the YAML turned into kubectl's
  object stream with PyYAML, with a saved resource list of the cluster);
- reads of upstream code in the local `cvat/server:v2.82.0` image, in one-off containers without
  network: the client events serializer, the events view and push handler, `events.rego` and
  `get_membership`.

The reviewer's probe scripts, inputs and logs stay outside the repository: they name the home
prefix and the namespace, and hold dumped blobs.

### Findings, most severe first

1. **Medium: any CVAT account can move the instance-wide cutover with one forged event, and anyone
   can inflate their own figures.** In `cutover_find.sql`, `cutover.py` (`look_for_cutover`, at
   start and in the daily check), `sql/read/cutover.sql` (the earliest stored hour wins) and
   `sql/refresh/*.sql`. Read in the stock server image: `events.rego` allows `send:events` to every
   caller; the client events serializer accepts only source `client`, forces user and
   organization fields from the request, and takes job, task and project ids, count, duration,
   payload and timestamp from the client; nothing more is checked before the events are logged.
   Run (2 tests OK): on the cutover fixture, an account with no organization sent one
   `draw:object` with `shape_type`, job id 999999, dated 1 January 2020. After the next daily
   check the cutover read 2020-01-01 for every caller, and organization A's October changed from
   `legacy: true, shapes: all, creation 2` to `legacy: false, shapes: bounding_boxes, creation 0`.
   History was not disturbed. An event dated 1960 did not move the cutover (not investigated).
   Read: a sender can also add working time, sessions, creations, alignments, Model creations,
   class changes and hotkey counts for themself, at any past hour and under any project or task
   id, inside each organization they belong to, but not under another person's name. The
   specification described a wrongly early event only as an accident. Should be: state the trust
   model; for the cutover, do not let one event decide it (a configured earliest date, or an
   administrator setting). Public through the push: yes.
2. **Low: the service's HTTP server keeps idle connections forever, one thread each.**
   `http_server.py` (`ThreadingHTTPServer`, no handler timeout, no thread cap). Run: 200
   connections that sent nothing or half a request header were all held, with 200 extra threads,
   after 20 s; a normal request was still answered. Reachable from any pod in the cluster
   (ClusterIP Service, no NetworkPolicy); through a proxy only within its timeouts. Effect:
   exhaustion of the replica (1 GiB limit). Should be: a socket timeout, a bounded worker pool, a
   NetworkPolicy. Public through the push: yes.
3. **Low: the service runs with more privilege than it needs.** `deployment.yaml`, `sql.py`. Read:
   it takes the whole chart Secret `cvat-analytics-secret`, the bundled ClickHouse's own user, so
   it could write to and drop CVAT's `events` table (grants not inspected); read statements have
   no time or memory limit (only the cutover search has); the pod sets `runAsNonRoot` and user
   1000 but not `allowPrivilegeEscalation: false`, dropped capabilities, a seccomp profile or a
   read-only root filesystem. Should be: a dedicated ClickHouse user, a statement limit on reads,
   the usual container restrictions. Public through the push: yes.
4. **Low: the render guard accepts several namespaced objects that reach other projects on the
   shared cluster.** `render_guard.py`. Run: accepted when added to the genuine render: an Ingress
   of class `nginx` for another project's host, and one for the wildcard host with a
   `server-snippet` annotation; a PersistentVolumeClaim naming an existing volume; a Pod with an
   NFS volume or an inline CSI volume; a selector-less Service with an Endpoints object to an
   arbitrary address; a service account token Secret (listed for completeness). The genuine
   render contains none of these. Should be: refuse an Ingress whose hosts are not the stack's
   own, and those volume types and fields. Public through the push: the guard did not exist in
   this form at `6cedd049`.
5. **Low: image builds and one vendored tool are not pinned the way the fork server image is.**
   Read: `build-team-analytics-service.sh` builds without `--pull=false`, `--network=none` and
   the local-base check of `build-server.sh`; `build-ui.sh` is networked by design and pins Node
   by tag, upstream's `Dockerfile.ui` installs `corepack` unpinned and takes nginx by tag;
   `tools/git-filter-repo` (4,976 lines, run by `mirror-cvat.sh`) has no recorded upstream
   version or hash. Should be: the same local-only build for the service image; record the tool's
   release and hash. Public through the push: yes.
6. **Low: identifying details of the owner and the machine are public in history.** No usable
   secret. The personal e-mail address is in 15 published commits' author and committer fields
   and in four published patch files; the home prefix (which contains the local user name) is in
   five files of the published tree and in two compiled files in published history. Withdrawing
   them needs a rewrite and a forced push of `main`. The branch adds no new kind.

### Earlier findings with a security side, at `fe87ffaf`

| Earlier finding | State | How seen |
| --- | --- | --- |
| Delivery 1: render guard misses forms | Closed for every listed form | Replayed; the genuine render, an empty namespace and an untagged-pull-policy control accepted as intended; a duplicate-key probe accepted only because PyYAML keeps the last key (kubectl refuses duplicate keys; not rechecked) |
| Delivery 2: server image built with stock policies | Closed | Read: `build-server.sh` checks both bundles before tagging |
| Delivery 3: bundle check edge cases | Closed | Ran: links, hard links, doubled slash, `.` and `..`, names outside the root and absolute names refused |
| Delivery 6: stack sharing by run id | Partly open | Read: `TA_RUN_ID` still defaults to the machine user, so two checkouts of one user share one stack. Operational |
| Delivery 9: identifying details and secrets | Partly open | Read: the seed password goes through standard input; the namespace with the user name stays in tracked evidence |
| Last fixes 1: bundle link and two names | Closed | Ran, as for delivery 3 |
| Last fixes 4: host reach in the guard | Closed for the listed forms; new gaps in finding 4 | Replayed |

### Statement A: what the push of 2026-11-14 published

Scope: every commit and blob reachable from `6cedd049` (191 commits, 2,374 blobs), less the
blobs identical to a blob of the import tags' trees or of the earlier subtree squash: 841 blobs
scanned, all 191 commit messages, and the metadata of the two public tag commits.

- Commit metadata: author and committer of all 191 commits are the owner's real name; 176 use
  the GitHub no-reply address (which carries the GitHub account name); **15 use a personal e-mail
  address** at a public mail provider. Time zone +0300 throughout; no signatures. Trailers name
  Claude models with Anthropic's no-reply address and link claude.ai sessions in 167 messages
  (five session ids); whether a link reveals anything without the owner's account was not
  checked. Messages hold no path, address, host name or secret. The two public tag commits are
  upstream's (`cvat-bot[bot]`, committer GitHub).
- **The machine's home prefix (contains the local user name):** 14 occurrences in 8 paths. In the
  published tree: `INFRA_MIGRATION.md` and four run logs under
  `docs/evidence/2026-11-14-team-analytics-final-run/` (`run-up1.log`, `run-up2.log`,
  `run-up-review-fixes.log`, `run-up-review-fixes-2.log`). In history only: `run-cycle.log` and
  two compiled Python files once under `team-analytics/service/team_analytics/__pycache__/`
  (their strings hold the absolute source path, a local path in history). Ticket 01 redacted the
  tree after the push, not history.
- **The local user name inside the stack's namespace and Ingress host:** 51 occurrences in 11
  paths: `docs/evidence/2026-11-13-team-analytics-test-stack.md`,
  `docs/evidence/2026-11-14-team-analytics-final-run.md` (several versions) and the six run logs.
- **The personal e-mail address and real name** in the `git format-patch` headers of
  `patches/0001-…`, `patches/0002-…` and both `patches/0003-…` files (6 address occurrences),
  removed from the tree before the push, in history.
- A machine path outside the home prefix (the cluster's old volume directory) and platform host
  names under `k8s.docker.internal` in `INFRA_MIGRATION.md`; generic to Docker Desktop.
- No host name of this machine, private IP address, private key, certificate, Kubernetes Secret,
  kubeconfig key data, API token, authorization header or cookie value other than test fixtures.
  Passwords: only test and disposable-stack defaults and upstream's chart defaults.
- Binary blobs outside the import: the two compiled files above, and eight PNG screenshots under
  `docs/evidence/2026-11-14-team-analytics-final-run/` with no text or EXIF chunk, showing page
  content with synthetic accounts and figures only.

Usable secret: none.

### Statement B: what a push of `6cedd049..fe87ffaf` would add

309 commits, 656 new blobs outside the import, all messages. All commits use the GitHub no-reply
address; no personal address. No home prefix in any new blob. The local user name inside the
namespace in four new, redacted versions of the run logs; at `fe87ffaf` it is in seven tracked
files (the two evidence files and five run logs). Platform host names under
`k8s.docker.internal` in the stack's README, `run.sh`, `stack.env`, ticket 11 and its evidence.
No e-mail address, key, Secret, token or cookie value; no binary blob. Dependency manifests added:
`verify/package.json` and its lock (from the public npm registry with integrity hashes, no install
script), `pyproject.toml` with `uv.lock` (ruff from PyPI), `prek.toml` (local hooks only). No new
kind of identifying detail and no secret.

### What held

The role floor of both policies (ran, 8,960 inputs each: decisions differ from stock only for
members of the resource's organization with a non-null organization role and the global role
`user` or `worker`); who the service believes (CVAT, asked with the caller's own credentials; no
forwarded header trusted; failures never cached); request values bound as typed parameters; no
credentials or query values logged; the page renders names as React text; the fork server image
build; the launcher's guard, bundle check, loopback port-forward and seed password handling.

### What the review did not check

Any live stack; the guard through kubectl's own parser; an image build; why a 1960-dated event
did not move the cutover; the ClickHouse account's actual grants; the service's full suite; the
stack's Grafana; any advisory lookup. A second pass over the commits after `fe87ffaf` is owed.

## Part two: what was done about each finding

| Finding | Outcome | Where |
| --- | --- | --- |
| 1, cutover and self-reported figures | Recorded, waits for the owner | Trust model in `docs/fork-specification.md` (TA-1, beside the cutover's limits); `.scratch/team-analytics/issues/19-any-account-can-move-the-cutover-and-add-its-own-figures.md` (needs-triage) |
| 2, idle connections | Fixed: closed after 120 s | `fix(team-analytics): close idle connections to the service after 120 s` |
| 2, worker pool and NetworkPolicy | Recorded | Specification, the service's known limits |
| 3, container restrictions | Fixed in the manifest, not yet shown on a pod | `fix(team-analytics): run the service container without escalation or capabilities` |
| 3, ClickHouse account and read limits | Recorded | Specification, known limits of the service's reach into ClickHouse |
| 4, render guard | Fixed: allowlists | `fix(stack): judge volumes, claims, Ingress hosts and endpoints by allowlist` |
| 5, service image build and vendored tool | Fixed and recorded | `fix(build): build the service image without pull or network, from a local base` |
| 5, what the UI build pins by tag | Recorded | Specification, the images |
| 6 and the earlier open findings | Recorded | Below |

**Finding 1 (recorded).** No code change: every remedy (a configured earliest date, an
administrator setting, plausibility checks) overrides the owner's decision in ticket 17 of the
defect fixes that the cutover is found by search and can move earlier. The specification now says
that every figure is reported by the browser of the person it describes, that an account that can
send events can add figures for itself, that any account can move the cutover earlier with one
shape-tagged event, and that the correction is the documented one; it says that the service's
half was run (on the test harness, by the reviewer) and the CVAT half was read. **This is the
finding that waits for the owner** (issue 19 above, with the review's options as open questions).

**Finding 2 (fixed).** The HTTP handler now has a socket timeout of 120 s (`IDLE_S` in
`http_server.py`, stated with its reason there and in the specification): a connection that sends
nothing for that long, with no request, half a request, or after a kept-alive answer, is closed
and its thread ends. The value is longer than the time the proxies that reuse connections keep an
idle one by default (ingress-nginx 60 s, Traefik 90 s), so a reused connection is never closed
under a proxy; the stack's nginx proxy has no upstream `keepalive` and opens one connection per
request (read in `proxy.yaml`). Unverified: the two defaults are the controllers' documented
defaults as known to the implementer, not read from this repository or from the cluster's
ingress-nginx configuration. Test first, through the server's boundary (`tests/test_http.py`,
`IdleConnectionTest`, with a 1 s limit given to `make_server`): before the fix the silent,
half-sent and idle kept-alive connections were still open after 5 s (recv timed out) and the
module failed; after it, the module's five tests OK on the default ClickHouse image. A client that sends a byte now and then keeps its connection; the worker pool
and the NetworkPolicy stay out (below).

**Finding 2, the rest (recorded).** A bounded worker pool needs a worker count nobody has chosen.
A NetworkPolicy that admits only the ingress controller or proxy needs the deployment's ingress
controller, which the fork does not know, and the local cluster may not enforce one.

**Finding 3 (fixed in the manifest).** `team-analytics/k8s/deployment.yaml` sets, on the service
container, `allowPrivilegeEscalation: false`, `capabilities.drop: ["ALL"]` and
`seccompProfile.type: RuntimeDefault`. No read-only root filesystem: not shown to work. Checked:
the manifest parses and the render guard accepts the service render built with `run.sh`'s
substitutions. Not shown: a pod starting under it (part three).

**Finding 3, the rest (recorded).** The ClickHouse account is the chart's own; a dedicated account
with read on the events database and write on the totals database is a deployment decision.
Statement limits on reads could fail a legitimate read at scale; only the cutover search has
limits, which the owner decided.

**Finding 4 (fixed).** The checks the review named are allowlists now, built from what the genuine
render (the chart render, the service, the proxy and the Ingress) contains:

- pod volume sources: only `configMap`, `emptyDir`, `persistentVolumeClaim` and `projected`, and
  inside `projected` only `configMap`;
- a `volumeName` anywhere is refused (a claim, a claim template, an ephemeral template);
- an Ingress may name only the stack's own host (`TA_INGRESS_HOST`, passed by `run.sh` as
  `--ingress-host`), in its rules and its TLS entries; a rule without a host, a default backend
  and any annotation are refused (the genuine Ingress has none; an annotation such as
  ingress-nginx's `server-alias` adds a host, a snippet adds controller configuration);
- Endpoints and EndpointSlice: refused, because the genuine render contains neither (the cluster
  writes them for a Service with a selector);
- Secret types: only those of the genuine render (unset, `Opaque`, `generic`), which refuses the
  service account token Secret.

The Secret type allowlist goes beyond the checks the brief named; it was added so that all seven
of the review's renders are refused. Not changed: the host checks and the role binding checks
still refuse by list, and the class of an Ingress for the stack's own host is not judged.

Checked without a cluster, as the review did: the YAML turned into kubectl's object stream with
PyYAML and judged with the resource list an earlier review saved. The genuine chart render is the
file the last-fixes review saved; the allowlist was taken from it and is checked against it. No
commit since then changes the chart (`cvat/helm-chart`), the stack's `values.yaml`, `Chart.lock`
or chart hashes, or how `run.sh` renders the chart (read in `git log`); a live render can still
differ, so the live `check-render` in part three is what shows it. That render and the service,
proxy and Ingress renders (made with `run.sh`'s substitutions and `stack.env`'s defaults) are
accepted. Of 57 doctored renders (18 from the last-fixes review, 19 from the delivery review, the
review's 7, and 13 added here), 52 are refused, every one of the review's seven among them. Five
are accepted. Four are controls meant to pass: the delivery review's genuine render, the
last-fixes review's empty namespace and untagged pull policy, and an Ingress for the stack's own
host. The fifth, the last-fixes review's duplicate-key render (an image key given twice, the
listed image last), is a doctored render this replay cannot judge: PyYAML keeps the last key. That
kubectl refuses duplicate keys was not rechecked here or by the review; a live `check-render` of
that file is part three. The 13 added ones: a secret, an ephemeral and an iSCSI volume, a
projected token, a volume that is not an object, a claim template naming a volume, an
EndpointSlice, an Ingress with no host, with a default backend and with a foreign TLS host, and an
Ingress for the stack's own host with a `server-alias` and with a `server-snippet` annotation. The stack's README and the specification
say what the guard judges by allowlist and what still by list.

**Finding 5 (fixed and recorded).** `build-team-analytics-service.sh` refuses a base image that is
not local and an `IMAGE` equal to the base, and builds with `--pull=false`, `--network=none` and
`--provenance=false`, as `build-server.sh` does. Ran: with a base that is not local it refused and
built nothing; one build under `cvat/team-analytics:v2.82.0-sec-check`, through the heavy lock,
succeeded without network. Compared with the image under `cvat/team-analytics:v2.82.0`: the same
entrypoint, command, user, working directory, environment and exposed port; the same 18 base
layers; of the 92 files under `/opt/team-analytics`, only `team_analytics/http_server.py` differs
(this branch's change); the two copy layers differ in digest. The check tag was removed.
`tools/git-filter-repo`: SHA-256
`67447413e273fc76809289111748870b6f6072f08b17efe94863a92d810b7d94`, its `--version` prints
`a40bce548d2c`, both recorded in the specification; the commit that added it is deliberately
not named.
Its upstream release is not identified; no outside request was made to find it.

**Finding 5, the rest (recorded).** `build-ui.sh` pins the Node image by tag, and upstream's
`Dockerfile.ui` takes its nginx base by tag and installs `corepack` unpinned. That is upstream's
build; the specification says it is pinned by tag, not by digest.

**Finding 6 and the earlier findings still partly open (recorded).** Stack sharing by run id and
the account name inside the namespace in tracked evidence stay. Withdrawing anything already
public needs a rewrite and a forced push of `main`, which is the owner's call; the unpushed
history carries the same details, so a redaction at the tip would withdraw nothing.

## Part three: outstanding

- The owner's decision on finding 1 (issue 19).
- ~~With a live stack: merge, rebuild, `up`, live `check-render`, the pod under the
  restrictions, `down`.~~ Done; see part four.
- ~~The reviewer's second pass over the commits after `fe87ffaf`, these fixes included, before any
  criterion of ticket 28 is ticked.~~ Done; see part five.
- ~~The whole service suite on both ClickHouse images (run by the orchestrator from the first
  step's head; nothing under `team-analytics/service/`, the ClickHouse component or
  `verify/team_analytics_service.sh` changed after it, the merge included).~~ Done; see part
  five.

## Part four: the live run, 2026-11-15

Run from branch `fix/security-review` after merging the integration branch at `236b3878` (the
final run's tip); the merge brought in no change to the service. Times are UTC. The stack's
namespace is written `cvat-ta-it-<user>`. Logs are kept outside the repository.

### Images

| Image | ID |
| --- | --- |
| `cvat/team-analytics:v2.82.0` | `sha256:91db1f1194d7`, rebuilt from the merged tree with the local-only `build-team-analytics-service.sh` (no pull, no network); the pod ran this ID |
| `cvat/server:v2.82.0-fork-policies` | `sha256:4b38c649ae96`, the final run's, unchanged |
| `cvat/ui:v2.82.0-team-analytics` | `sha256:a7229efd9174`, the final run's, unchanged |

The service image built before, `sha256:3bf1631cd7da`, lost its tag to the rebuild and was
left in place.

### Live outcomes

- **Before.** `run.sh status` showed no namespace and no port-forward, `check-ingress-gone`
  passed, nothing listened on 8490. After the merge the guard replay (part two) gave the same
  result: the four genuine renders accepted, 52 of 57 doctored renders refused.
- **`run.sh preflight`** passed: the server image, the issue matrix against both policy sides,
  the chart build and the render checks with the changed guard.
- **`run.sh up` from an empty namespace** (03:57 to 04:11) passed from start to finish on the
  first attempt. The guard accepted the chart render, the service (with the container
  restrictions), the proxy and the Ingress before each was applied; the tracer, task progress,
  the final run with the volume, the page in a browser, the service stopped and started again,
  the issue matrix and the four access cases all passed.
- **Live `check-render`.** The chart render from `run.sh render`: accepted. The last-fixes
  review's duplicate-key render, through kubectl's own parser: accepted. kubectl
  (client 1.36.1) does not refuse duplicate keys: it keeps the last one, as PyYAML does, so its
  object stream names the listed image `redis:7.2.11` and the guard judges exactly what kubectl
  would apply. The review's assumption that kubectl refuses duplicate keys does not hold here;
  no gap follows from it. (`check-render` adds the backend check, so it refuses the service,
  proxy and Ingress renders by themselves for lacking the fork server image; `up` judges those
  without it, and accepted them.)
- **The service pod under the restrictions.** The cluster held, for the container,
  `{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]},"seccompProfile":{"type":"RuntimeDefault"}}`,
  and for the pod `runAsUser` and `runAsGroup` 1000 with `runAsNonRoot`. Inside the running
  container: uid 1000, `CapPrm`, `CapEff` and `CapBnd` all zero, `NoNewPrivs: 1`, `Seccomp: 2`
  (filtering). The pod in place at the end (started 04:08, after the final run's service stop
  and start) was Ready with 0 restarts and answered every page and access check that `up` runs
  after that point. The first pod of the run restarted twice in its first seconds: its log ends
  in `OperationalError … cvat-clickhouse:8123 … Failed to establish a new connection`, the
  service starting before the chart's ClickHouse accepted connections. That is the start order
  the launcher has always had (the service is applied while the chart's workloads come up), not
  the restrictions.
- **`run.sh down`** (04:18, exit 0) stopped the port-forward and deleted the namespace with its
  five claims, and said nothing remains. `check-ingress-gone` passed. Looked at afterwards: no
  namespace `cvat-ta-it-<user>` and none with the stack's label, no Ingress and no volume of
  it, nothing listening on 8490, no port-forward process, no state directory. The check image
  tag of part two is gone; no container of this run is left.

### What stays unverified

A read-only root filesystem (not tried). The guard's refusals were seen only on doctored
renders judged offline; live, only acceptances were seen. The worker pool, the NetworkPolicy,
the ClickHouse account and the limits on reads remain as recorded.

## Part five: the reviewer's second pass and the whole suite, 2026-11-15

The same reviewer, under the same rules, reviewed the integration tip `02e5423d`: the 22
commits after `fe87ffaf`, which hold the rest of the final run, the answers of part two and
the answers to the review of the final run's tooling
(`docs/evidence/2026-11-15-integrated-branch-review.md`). It changed no tracked file, used no
cluster and built no image.

### What it ran

- The idle probe again on the real server, with the limit shortened to 3 s: 50 silent and 50
  half-sent connections were all closed and their threads ended.
- Every doctored render of all the reviews that it had, and 14 new ones, against the changed
  guard (PyYAML in place of kubectl, as before).
- The two refusals of the service image build (a base that is not local; an image name equal
  to the base). Neither built anything.
- The scan of blobs, commit messages and secrets over the new range and the tip.
- One advisory query to the public OSV database with the 70 package names and versions of
  `verify/package-lock.json` and ruff's, and nothing else.

### The six findings of part one

1. Cutover and self-reported figures: recorded accurately in the fork specification, in
   issue 19 of the Team Analytics tracker and in this file, and not softer than the finding.
   Waits for the owner.
2. Idle connections: fixed as claimed. A client that sends a byte now and then keeps its
   connection, since the limit applies to each read: 20 connections that sent one header
   byte every 1.5 s were all still open after 12 s. The specification says so.
3. Privilege: fixed in the manifest; the live pod of part four was read, not rerun. The
   ClickHouse account and the limits on reads are recorded.
4. Render guard: fixed for every form the review named. The stack's own Ingress is
   accepted; a foreign host, a wildcard, an annotation, a host in other letter case, NFS,
   inline CSI, Endpoints, a claim naming a volume and a token Secret are refused. The
   review's assumption that kubectl refuses duplicate keys was wrong (part four).
5. Builds: fixed as claimed. As with `build-server.sh`, `--pull=false` protects only on the
   default builder; another builder was not tried.
6. Public history: recorded, with an accurate reason.

### New in the second pass

7. **Low, recorded: a claim can still bind an existing volume without naming it.** The guard
   accepted three renders added to the genuine one: a PersistentVolumeClaim with an empty
   storage class and a label selector, the same in a StatefulSet's claim templates, and an
   empty storage class alone. On a shared cluster such a claim can bind another project's
   free volume. Only a changed chart or stack manifest could bring one: the genuine render
   has none, and the guard is not in what was pushed. It stands, for this reason: it was
   found in the second pass, after the guard's change had been shown on a live `up`, and a
   further change to the guard would need that showing again; the rule set before the
   second pass was that a new low finding is recorded. The fork specification and the
   stack's README now name these forms as not judged, so that neither says more than the
   guard checks. A later change to the guard should refuse a claim or claim template with a
   selector, a data source or a storage class other than unset.
8. **Note, not a defect of the fork: the chart's Grafana is anonymous Admin.** Read in the
   import's chart and in CVAT's analytics policy in the local server image; not tried on a
   stack. With analytics enabled, upstream's chart deploys Grafana with anonymous access in the Admin role and the
   sign-in form off. Through the stack it is reachable only on the loopback port-forward and
   only after the proxy has asked CVAT, which grants it to accounts with analytics access.
   Any pod in the cluster can reach its Service directly. There is no default password to
   guess. It matters for a real deployment that keeps the chart's analytics defaults; the
   fork specification now says so beside upstream's other defaults.

### The rest of the second pass

- The launcher changes of the final run put no credential on a host command line or in a
  log, and what they write into the cluster stays inside the disposable namespace.
- This file was compared with the review's report: faithful in kinds, counts, file names,
  runs and the list of what was not checked; no home prefix, no account name, no e-mail
  address other than the two no-reply ones.
- What a push of the tip would add, restated for `6cedd049..02e5423d` (331 commits, 722
  blobs outside the import, all scanned, with all messages): no binary blob, no home prefix,
  no e-mail address, no host name of the machine, no private address, no key, certificate,
  Secret, token or cookie value apart from test fixtures, and passwords only of the
  disposable stack and the tests. The account name inside the namespace is in the same
  seven tracked files as before. A push would add no new kind of identifying detail and no
  secret.
- Advisories, as of 2026-11-15: OSV lists none for the 70 package versions of
  `verify/package-lock.json` or for ruff 0.17.3. A version known to be vulnerable, sent as a
  control, came back with advisories.
- Not checked in the second pass: any live run; 13 doctored renders that only the
  implementer had; a real build of the service image; a builder other than the default;
  whether a claim with a selector would in fact bind another project's volume on this
  cluster.

### The whole service suite with these fixes

Run by the orchestrator from a snapshot of the service tree at `21ed4fdc`. Nothing under
`team-analytics/service/`, `cvat/components/analytics/clickhouse/` or
`verify/team_analytics_service.sh` differs between that commit and `02e5423d`
(`git diff --stat`, empty). Last lines of the two logs:
`cvat/clickhouse:23.12.2-debian-11-r0`: `Ran 321 tests in 2586.225s`, `OK`, `exit=0`;
`clickhouse/clickhouse-server:23.11-alpine`: `Ran 321 tests in 2471.951s`, `OK`, `exit=0`.
