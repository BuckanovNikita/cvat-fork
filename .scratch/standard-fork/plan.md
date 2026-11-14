# Standard fork, and Team Analytics inside the CVAT backend

Status: needs-triage

Draft of 2026-11-14 for the owner to review. Nothing here is implemented. It
proposes two changes that depend on each other:

1. Turn this overlay repository into a standard full-source fork of
   `cvat-ai/cvat`.
2. Move the Team Analytics service into the CVAT backend, so the browser talks
   only to CVAT's own API.

Vocabulary follows [`GLOSSARY.md`](../../GLOSSARY.md). What earlier sessions
decided or changed against the first plan is in
[`decisions-ledger.md`](decisions-ledger.md), with what happens to each item
under this plan.

Statements about upstream were read from a full checkout of upstream
`v2.82.0` (commit `02bd74f`); paths without a prefix are relative to that
tree. Statements marked *not run* were derived from configuration or source
and have not been executed.

## 1. Where we are

- The repository holds a filtered copy of upstream's frontend packages under
  `cvat/` (a squashed subtree pulled from a path-filtered mirror), two copied
  policy files under `opa/`, a separate analytics service under
  `team-analytics/`, and its own test tooling under `verify/`. The Python
  backend is not in the tree.
- **How the page gets its figures today:** the browser calls
  `/team-analytics-api/v1/{status,overview,trends,list,details}` with a plain
  same-origin `fetch` and the session cookie
  (`cvat/cvat-ui/src/components/team-analytics-page/service.ts`). A route
  beside CVAT sends that prefix to the separate service, which asks CVAT three
  questions over HTTP to decide who the caller is and then queries ClickHouse.
  CVAT's backend, its permission system and its API are not on that path. Only
  project names go through cvat-core.
- The fork's delta inside `cvat/` is 75 files: 57 new and 18 edited upstream
  files (17 under `cvat-ui/src/`, plus a formatting-only change to
  `components/analytics/clickhouse/init.py`). `git apply --check` of that delta
  onto full upstream `v2.82.0` passes, and the filtered tree is byte-identical
  to upstream for every shared path. The conversion is a replay, not a port.
- The patched issue and comment policies reach a server only through the two
  Compose overlays. The Kubernetes test stack mounts no policy file, so it runs
  the stock policies; nothing in this repository delivers IAM-1 on Kubernetes
  today.
- The stock-backend premise behind the current design was never an owner
  requirement (ledger O1 to O3). The owner asked for "possibly a dedicated
  backend endpoint"; an endpoint inside CVAT was not among the options
  considered in ADR 0001 because the backend was not in the tree.

## 2. Target

### 2.1 Repository

- History starts from upstream: an `upstream` remote, and `main` = an upstream
  release tag plus our commits. An upgrade is `git merge <next release tag>`.
- Our changes are replayed onto `v2.82.0` as a short series of logical commits
  (task progress; issue and comment policies; Team Analytics UI and logging;
  fork documents and tooling). The overlay history stays reachable under a
  `legacy/overlay` ref and is not rewritten.
- Fork-owned files keep paths upstream does not use. Three root names collide
  with upstream and need a home (decision D2): `README.md`, `.gitignore`, and
  `cvat/` (today the subtree prefix, upstream's Django project).
- `docker-compose.override.yml` is a name upstream's `.gitignore` reserves for
  local use and that Compose loads automatically beside `docker-compose.yml`.
  It cannot stay a tracked file at the root.

### 2.2 Backend: a Django app `cvat/apps/team_analytics/`

All of it is new, fork-owned code following upstream's own patterns.

| Part of today's service | In the backend | Upstream pattern followed |
| --- | --- | --- |
| stdlib HTTP server, entry point, SIGTERM handling, request-body handling | nothing of ours: a DRF `ViewSet` with five `GET` actions under `/api/team-analytics/` | `cvat/apps/events/views.py`, `cvat/apps/log_viewer/views.py` |
| `access.py`: three HTTP calls to CVAT, one-minute cache, 401/403/503 mapping | `permissions.py` (an `OpenPolicyAgentPermission` subclass) and `rules/team_analytics.rego`; the organization comes from `request.iam_context`, which CVAT's middleware fills from `?org=` | `cvat/apps/log_viewer/permissions.py`, `cvat/apps/events/rules/events.rego`, `organizations.has_perm(organizations.MAINTAINER)` |
| refresh loop in a thread of every replica | one `PERIODIC_RQ_JOBS` entry running a time-budgeted step on an RQ worker | `cvat/apps/access_tokens/cron.py` |
| lease table in ClickHouse, renewal thread, deadline proof | a non-blocking Redis lock taken inside the job, with a deadline check before each write | `cvat/apps/engine/utils.py` (`get_rq_lock_for_job`), `cvat/apps/dataset_manager/util.py` |
| `config.py` environment | Django settings: `settings.CLICKHOUSE["events"]` plus an app `default_settings.py`; the CVAT address and listen settings disappear | `cvat/apps/access_tokens/default_settings.py` |
| `sql.py` and the 54 SQL files | moved unchanged, minus the lock files | none upstream; `cvat/apps/events/export.py` shows the connection arguments |
| schema bootstrap at service start | idempotent bootstrap run by the job before its first step | idea of `components/analytics/clickhouse/init.py` |
| `Dockerfile`, `k8s/` manifests, build script, route under its own prefix | none: the fork's server image is used by every backend pod | — |

The access rule stays what the owner required (ledger O4): admins see any
organization or the whole instance; owners and maintainers see their
organization; everyone else is refused; organizations never see each other.
A sketch of the policy, to be proven by generated policy tests:

```rego
package team_analytics

import rego.v1
import data.utils
import data.organizations

default allow := false
allow if { utils.is_admin }
allow if {
    input.scope == utils.VIEW
    utils.is_organization
    organizations.has_perm(organizations.MAINTAINER)
}
```

The stored totals stay in their own ClickHouse database on the same server.
The app needs no Django models and no migrations.

### 2.3 UI

- `service.ts` keeps its single replaceable boundary but calls
  `getCore().server.request('/api/team-analytics/<endpoint>', { method: 'GET', params })`.
  That is cvat-core's shared axios instance: session cookie, CSRF header, the
  current organization as `?org=`, retry on 429 and error mapping come with it,
  with no edit to cvat-core (decision D5).
- The page stops sending the organization itself. Refusals are read from the
  HTTP status, and "select an organization" is decided from what the UI already
  knows before the call.
- Wiring edits in upstream UI files are replayed as they are in the conversion.
  Moving some of them behind upstream's plugin slots is a separate later step
  (section 4.2).

### 2.4 Event contract

ADR 0002 (new measurements inside existing event types) stays as built. With
the backend in the tree a real scope could be added, at the price of editing
`cvat/apps/events/serializers.py` and `cvat-core/src/enums.ts`, both upstream
files, and of reading two contracts in SQL for data already recorded. The ADR's
reason changes from "the server cannot be changed" to "it keeps two upstream
files untouched" (decision D7).

### 2.5 Images and deployment

- A fork server image replaces the stock one for the server, every worker and
  the initializer. Recommended default build: a thin image `FROM` the stock
  release with the fork's `cvat/` Python tree copied over it. It needs no
  network, as the service image does today, and is valid while the fork adds
  no Python dependency. The full upstream `Dockerfile` build belongs to the
  upgrade gate. *Not run.*
- The UI image is built as today, from the repository root instead of `cvat/`.
- The analytics job runs on a worker that has the ClickHouse environment. In
  the Helm chart every backend pod gets it when analytics is enabled; in
  upstream's Compose file only the server and the export worker do.

## 3. What becomes simpler

Each item names what is deleted and what replaces it.

1. **Upgrades.** `mirror-cvat.sh`, the vendored `tools/git-filter-repo`, the
   `.cvat-mirror.git` mirror, the subtree pull and "obtain the matching full
   source separately for the policies and the chart" are replaced by one merge
   of a release tag. The integration maps in `docs/fork-specification.md`
   become `git diff <tag>..main --stat`.
2. **Policies.** `opa/rules/*.rego`, the bind mounts and the three Compose
   files that exist to deliver and compare them go away; the two policies are
   edited where they live and ship inside the server image. The class of
   failure fixed on 2026-11-14 (a mount into a directory the server no longer
   reads, `docs/evidence/2026-11-14-opa-rules-mount-path.md`) cannot recur.
   Upstream's generated policy tests and its Rego linter apply to them.
3. **A whole process disappears.** The HTTP server, its entry point, SIGTERM
   handling, the request-body fix, TCP probes, the service image and its build
   script, five Kubernetes manifests, the Ingress that was never applied, the
   reverse-proxy route and the `/team-analytics-api` prefix (ledger S1 to S6).
4. **Access control stops being our own code.** `access.py`, its cache, the
   per-role membership paging, the malformed-answer handling and the stand-in
   CVAT server used by the tests are replaced by one policy file and upstream's
   permission class. A removed member loses access on the next request instead
   of within a minute. The access cases that were never checked against a live
   CVAT (ledger V4) become ordinary REST tests on upstream's existing role
   fixtures.
5. **The lease.** The ClickHouse lease, reworked twice in review, is replaced
   by a Redis lock and the scheduler CVAT already runs (ledger S7 to S9).
6. **Configuration.** The service's CVAT address, listen settings and the
   coupling to the Helm release name disappear; ClickHouse credentials come
   from CVAT's settings.
7. **Linting and type checking work.** ESLint never ran on this feature
   because the filtered import leaves out the root `eslint.config.mjs`; in a
   full tree `yarn run eslint`, `stylelint` and `type-check` run as upstream
   runs them, and the type check resolves the real workspace packages (ledger
   V7).
8. **The development server proxies `/api/` already**; the separate prefix
   needed its own proxy rule.
9. **The Helm chart is in the tree**, so the test stack stops downloading it
   into a cache (ledger T2). Its dependency lock stays fork-owned, because
   upstream ships none and ignores `helm-chart/Chart.lock`.
10. **`ruff.toml` and the formatting-only delta** in
    `components/analytics/clickhouse/init.py` are dropped; that file returns to
    upstream byte for byte and the app follows upstream's black and isort
    settings (line length 100).
11. **The tab-close loss of input counts becomes fixable**, since cvat-core is
    ours to edit. It is optional and costs a cvat-core touch point (decision
    D8).

## 4. Keeping our changes apart from upstream sources

### 4.1 Touch-point budget after the conversion

Every upstream file the fork edits, and why. New files in new directories are
not listed; they cannot conflict.

| Area | Upstream files edited | Why it cannot be a new file |
| --- | --- | --- |
| Backend wiring | `cvat/settings/base.py` (two appends: the app, the periodic job), `cvat/urls.py` (one append) | Conventional registration. A settings overlay avoids both edits at a cost (decision D4) |
| Policies | `cvat/apps/engine/rules/issues.rego`, `comments.rego` (the list filter), the two test configurations `rules/tests/configs/{issues,comments}.csv`, `tests/python/rest_api/test_issues.py` | The filter is one branch of an existing rule; upstream's tests encode the stock behaviour and must change with it. The added `allow` rule can live in a fork-owned file of the same package (*not run*; to be proven by `opa test`) |
| Team Analytics UI | 11 files under `cvat-ui/src/` (route and click listener, header link and rename, job tracking, shortcut hook, payload fields at six log sites, class change at four sites, detector record) | Guarded one-line calls at the place upstream logs the event |
| Task progress | 6 files under `cvat-ui/src/` (thunk, reducer, types, container, component, styles) | Stores its summary in the tasks slice of the Redux store |
| Root | `README.md` (a two-line banner, if wanted), `.gitignore` (a fork block, if needed) | Decision D2 |

Not edited: `cvat-core`, `cvat-canvas`, `cvat-data`, `cvat/schema.yml`, the
SDK, `backend_entrypoint.sh`, `Dockerfile`, `Dockerfile.ui`,
`docker-compose.yml`, `helm-chart/`.

How the backend stays out of upstream files:

- The endpoints are excluded from the published schema
  (`@extend_schema(exclude=True)`, as upstream does for private endpoints), so
  `cvat/schema.yml` and the generated SDK do not change (decision D6).
- The job reuses the existing `cleaning` queue, so no queue is added to
  settings, to the worker entry point or to the deployment.
- The ClickHouse schema is bootstrapped by the job, not by the entry point.

### 4.2 Later: fewer UI touch points

Upstream's UI has a plugin mechanism (`cvat-ui/plugins/`, compiled in through
`CLIENT_PLUGINS` or the default list in `cvat-ui/webpack.config.js`). In
`v2.82.0` a plugin can add a route, add a user-menu item, attach window and
canvas listeners, observe the store and wrap cvat-core methods. It cannot add
a top-level header link, see shortcut action names, or replace the task
progress block.

| Tier | What moves | Upstream UI files still edited |
| --- | --- | --- |
| Today | — | 17 |
| A: no change in behaviour | route, click listener, job tracking on open, drawing-start listener move into a thin plugin entry; task styles into the widget's own file | 15, plus one line in `webpack.config.js` unless every build sets the variable |
| B: needs decisions on behaviour | closing summary saved by the plugin itself, class change and detector record through cvat-core hooks, task summary out of the Redux store, header link into the user menu | 4 or 5 |
| C: payload fields by correlation | shape fields attached by matching canvas events to log calls | 2 or 3 |

Recommendation: do not mix this with the conversion. Consider tier A
afterwards, once a browser run settles the two open risks (a hard load of
`/team-analytics` before the plugin registers its route; module state shared
between the plugin entry and the main bundle). Do not do tier C: it trades
merge conflicts, which are visible, for miscounted figures, which are not.

## 5. Tests and linting

### 5.1 Upstream checks that apply to our code

| Our code | Upstream check | Command, scoped to our paths | Needs |
| --- | --- | --- | --- |
| Django app | black, isort, pylint, bandit | `black --check --diff <app>`; `isort --check --diff --resolve-all-configs <app>`; `pylint -j0 <app>`; `bandit -a file --ini .bandit --recursive <app>` | the tools only |
| Django app | schema and migration checks | `python manage.py spectacular` compared with `cvat/schema.yml`; `makemigrations --check` | the server image built from the tree |
| Django app | Django tests | `manage.py test --settings cvat.settings.testing cvat.apps.team_analytics` | that image, OPA on `localhost:8181`, ClickHouse on `localhost:8123` |
| Django app, policies | REST tests | `pytest tests/python/rest_api/test_team_analytics.py` (plus `test_issues.py`) | a full stack |
| Policy files | generated policy tests, Regal | `python cvat/apps/iam/rules/tests/generate_tests.py && opa test cvat/apps/*/rules`; `regal lint cvat/apps/*/rules` | the `opa` and `regal` binaries |
| UI page, logging, task progress, wiring | ESLint, stylelint, type check | `yarn run eslint <paths>`; `yarn run stylelint '<dir>/**/*.scss'`; `yarn run type-check` | `yarn install --immutable` |
| Browser behaviour | Cypress | `cd tests && BASE_URL=<url> npx cypress run --spec '<spec>'` | a running stack and the UI image |
| Images | hadolint | on any Dockerfile we add | the tool only |

All commands are *not run*; they were derived from `.github/workflows/` and
the lint configurations.

### 5.2 Where our existing checks go

| Today | Tomorrow | What is lost |
| --- | --- | --- |
| Service tests (25 modules, real ClickHouse, a stand-in CVAT) | Calculations, refresh and history: Django tests in the app against ClickHouse. Access: generated policy tests plus REST tests with real roles. Lease, shutdown and HTTP-server tests are deleted with the code they test | The stand-in CVAT and the standalone-process tests, no longer needed |
| Page tests (22 files), logging tests (6), task-progress test on a `node --test` harness | Stay fork-owned and move out of `verify/` beside upstream's `tests/`. **Upstream has no unit-test harness for any frontend package** (no jest or vitest, no test files, Cypress only), so they have no upstream home | Nothing |
| `verify/opa_issues_test.rego` | Its matrix moves into the two test configurations, which have to change anyway | The stock-versus-patched comparison |
| `verify/opa_issues.sh`, `verify/run.sh` and their Compose files | Retired: REST tests for the policies, a Cypress spec for task progress | — |
| `verify/team-analytics-stack/` | Stays as the fork's Kubernetes launcher, without the service, its proxy route and the chart download; it carries the upstream suites | — |

New Cypress specs cover what only a browser shows: the header link by role,
the page states, task progress on a real task list. Upstream has no analytics
or events spec to copy; its organization pipeline spec is the model for roles.

### 5.3 Kubernetes

The owner requires Kubernetes only (ledger O6), and `INFRA_MIGRATION.md`
removes the Compose launchers. Upstream's own position:

- **REST, SDK and CLI tests** have a Kubernetes mode (`pytest --platform=kube`).
  It is destructive and unscoped: it flushes Postgres, Redis and ClickHouse and
  calls `kubectl` with no namespace or context. It needs a dedicated throwaway
  release and a kubeconfig whose current namespace is that release. It cannot
  share a release with the stack's seeded checks.
- **Django tests** expect OPA on `localhost:8181` fed by a server built from
  the tree under test, and ClickHouse on `localhost:8123`. Upstream runs them
  with Compose. Here they need a pod of the fork image with those two beside
  it.
- **Policy tests and all linters** need no stack.
- **Cypress** needs only a base URL and the superuser; nothing in the specs is
  specific to Compose.

How the Django tests are run on the cluster is the one piece of test
infrastructure this plan has to design (phase 3).

### 5.4 Gates

Fork gate, run before a fork change is merged, scoped to what changed:

- no stack: the linters of 5.1 on changed paths, generated policy tests, the
  fork's node suites;
- image build: schema and migration checks;
- stack: the app's Django tests, the REST tests for Team Analytics (and for
  issues when a policy changed), our Cypress specs.

Upgrade gate, run after merging an upstream release, unscoped:

- every job of upstream's `linters.yml` as written, all policy tests, the node
  suites;
- both images, schema and migration checks;
- the full Django suite, the full REST, SDK and CLI suite on Kubernetes, our
  Cypress specs plus the upstream groups that cover files we edit, then the
  stack run.

Upstream's whole-repository linters (black, isort, pylint, bandit, remark,
typos) run on `.` and will sweep fork-only directories and documents. Each
needs a decision: bring our files into line, or exclude them in an
upstream-owned configuration file, which is another touch point (decision
D9).

The repository has no hook pipeline today. The fork gate's commands should
live in one hook configuration (prek) so that instructions name only the
invocation.

## 6. What becomes costlier

- **A custom server image for every backend process.** Today only the UI image
  is ours. If production follows, a server image crosses the air gap in place
  of two mounted policy files.
- **Failure isolation has to be designed, not assumed.** The owner's standing
  requirement is that a failure of the feature must not break core functions
  (ledger O5). A separate process gave that for free. Inside the backend: the
  app has no models, migrations or signal handlers, its `apps.py` imports
  nothing heavy, the job's failures stay in the worker, and "the server starts
  and annotation works with ClickHouse down, with the totals database missing,
  and with analytics switched off (`CVAT_ANALYTICS` unset)" becomes an
  acceptance test. With analytics off there is no ClickHouse to read, so the
  job must not be scheduled and the endpoints must refuse cleanly; upstream
  appends a periodic job behind a flag in `cvat/settings/base.py`, which is the
  pattern to follow.
- **Analytical reads occupy CVAT's API workers.** An overview runs about
  thirteen queries, about two seconds in the measurement (ledger S12). The
  server runs few uvicorn processes. This needs a measurement before the
  sidecar is removed.
- **Coupling to upstream internals.** The permission base class, the periodic
  job list, the organization middleware and `core.server.request` are not
  documented extension points. Most changes to them fail at merge or at test
  time, which is acceptable; they are dependencies to list in the fork
  specification.
- **Repository size and upstream's CI files.** Full history is fetched once.
  Upstream's workflows arrive with the tree and need a decision (D10).
- **Every 4xx or 5xx from our endpoints writes a `send:exception` row** into
  the events table. The refresh SQL reads none of them; they add rows to
  Grafana's exception panels.

## 7. Phases

Each phase ends with evidence that can be checked, and the earlier phase's
checks are rerun only where its inputs changed.

**Phase 0: decisions and records.** The owner answers section 8. New ADRs
record the two reversals (section 9). No code.

**Phase 1: convert the repository, behaviour unchanged.**
- New history from upstream `v2.82.0`; replay the delta; move the two policies
  into `cvat/apps/engine/rules/` with their test configurations and REST
  expectations; move fork files; delete the mirror tooling, `opa/` and the
  formatting-only delta.
- The analytics service stays a separate process in this phase, so the
  existing stack run still judges the result.
- Evidence: the new tree equals the old `cvat/` tree for every shared path
  (a tree comparison, expected empty); the UI image builds from the root;
  the three node suites pass; ESLint, stylelint and the type check run for the
  first time, with their findings fixed in a separate commit; generated policy
  tests pass; the stack run passes with the fork server image carrying the
  policies and no bind mount.

**Phase 2: the backend app, as thin vertical slices.**
- Tracer: app skeleton, policy, permission class, the `status` endpoint and
  working time in `overview`, the periodic job with its Redis lock and schema
  bootstrap. Django tests against ClickHouse; generated policy tests; one REST
  test per role.
- Then the remaining endpoints and SQL, ported with their tests, one figure
  group at a time.
- Then the page switches to `/api/team-analytics/` and the sidecar, its image,
  manifests, proxy route and tests are deleted.
- Evidence: every calculation test of the old suite has a counterpart that
  passes; the access matrix passes with real accounts, including the cases
  never checked live; a measurement of overview latency and of API
  responsiveness during a refresh; the isolation test of section 6.

**Phase 3: gates and test infrastructure.** The Kubernetes path for Django
tests and for the REST suite; Cypress specs; the hook configuration; the
decisions of D9 applied. Retire `verify/opa_issues.sh`, `verify/run.sh` and
their Compose files (this is also what `INFRA_MIGRATION.md` asks for).

**Phase 4: documents.** Fork specification, upgrade procedure and README
rewritten for the new layout; a dated evidence file for the final run.

**Optional, after phase 4:** UI tier A (section 4.2); delivering the last input
summary on tab close (decision D8).

Phases 1 and 2 are sequential. Within phase 2 the figure groups can be built in
parallel once the tracer has merged. Phase 3 can start when the tracer exists.

## 8. Decisions for the owner

Each has a recommendation. None blocks writing the specification; D1, D3 and
D4 block phase 1 or 2.

| # | Decision | Options | Recommendation |
| --- | --- | --- | --- |
| D1 | How the repository becomes a fork | (a) keep this repository: add the `upstream` remote, make a new `main` rooted on the upstream tag, keep the overlay history under `legacy/overlay`; (b) create a fresh GitHub fork of `cvat-ai/cvat` and archive this one | (a). It keeps the address, the tracker and the documents. A GitHub fork relation only matters for pull requests to upstream. Replacing `main` is a forced update of a published branch and needs explicit approval. Whether the current remote is registered as a GitHub fork was not checked |
| D2 | Colliding root names | `README.md`: leave upstream's and keep ours as a fork document, with or without a two-line banner in upstream's file. `.gitignore`: a fork block at the end, or `.git/info/exclude` for local artefacts | Banner plus `README.fork.md` in Russian. A fork block in `.gitignore` only if something still needs ignoring after the mirror is gone |
| D3 | Production and Compose | The deployment override with mounted policies is replaced by a fork server image. Either production takes that image across the air gap, or a Compose overlay with mounts is kept for it | Take the image: one delivery mechanism, no silent mount failure. Production was put out of scope earlier (ledger O7), so this needs the owner's word |
| D4 | Backend wiring | (a) conventional: three appended hunks in `base.py` and `urls.py`; (b) a fork-owned settings module layered on `cvat.settings.production`, the route upstream documents for LDAP: no upstream edit | (a). With (b) the app is invisible under every stock settings module, so upstream's unit-test run, REST harness and schema check do not see it without fork twins of three settings modules, and a process left on stock settings silently drops the periodic job |
| D5 | How the page calls the API | (a) `core.server.request`: no cvat-core edit, same auth and organization handling, no precedent inside the UI (upstream uses it from Cypress only); (b) a `cvat.teamAnalytics.*` API in cvat-core: six upstream files | (a). (b) is right only for a feature meant to be offered upstream |
| D6 | Publish the endpoints in the schema and SDK | exclude, or publish and regenerate `cvat/schema.yml` and the SDK on every change | Exclude. REST tests call the endpoints over HTTP directly |
| D7 | Event contract | keep `debug:info` records and payload fields, or add real scopes | Keep. Recorded data depends on it and it avoids two upstream edits |
| D8 | Input counts lost on tab close | accept as today, or change cvat-core's page-exit path | Accept for now; revisit after phase 4 |
| D9 | Whole-repository linters and fork documents | conform our files, or exclude fork directories in upstream's configurations | Conform Python and policy files. Exclude `.scratch/` and `docs/` from remark and typos in one place, accepted as two touch points |
| D10 | Upstream's CI workflows | leave the files untouched and keep Actions off for the fork, or adapt them | Leave untouched. The fork gate runs locally through the hook pipeline; adapting upstream workflows is a recurring merge point |
| D11 | Items the first implementation left to the owner | status shows instance-wide history dates to a maintainer (ledger A4); the cutover finder is one query over all earlier events (ledger Q9); part-hour time zones (ledger Q11) | Decide while the endpoints are ported. The first becomes a one-line organization clause |

## 9. Recorded decisions this plan reverses

Per `docs/agents/domain.md`, contradictions with ADRs are stated, not silently
overridden.

- **ADR 0001** (a thin analytics service): reversed as to where the code runs.
  Kept: stored hourly totals, calculations in SQL files, the trailing-window
  refresh, day-by-day history. New ADR: analytics endpoints inside the CVAT
  backend, with the considered option the first one lacked.
- **ADR 0002** (new measurements inside existing event types): kept; its
  rationale is amended (section 2.4).
- **ADR 0003** (Kubernetes only, upstream Helm chart): kept. Its consequences
  about obtaining the chart outside the filtered tree, and the service and
  proxy manifests, fall away.
- **The first specification**, "the backend stays the stock image" and "out of
  scope: any change to the stock backend": reversed. The owner never set
  either (ledger O1).
- **`docs/fork-specification.md` BUILD-1** (stock backend, mounted policies,
  custom tag only for the UI): replaced.
- **`INFRA_MIGRATION.md`**: "mirrored upstream content under `cvat/` stays
  untouched" loses its meaning; its required outcome (no maintained Compose
  launcher, verification in our own namespace) is delivered by phase 3.

## 10. Not verified

- No conversion, build, stack or test run was made for this draft. The only
  executed checks are the patch replay (`git apply --check`), the tree
  identity of the filtered import, and the policy mount fix of 2026-11-14.
- Every command in section 5 is derived, not run. In particular: whether the
  two test-configuration edits are sufficient for the generated policy tests,
  bandit's reaction to our SQL-building code, and typed ESLint on files not
  yet imported.
- That a second file of the same package can carry the added `allow` rule.
- The thin server image (section 2.5).
- Redis lock behaviour across a Redis restart, and the exact API of the lock
  helpers.
- How concurrent synchronous views behave in upstream's uvicorn setup.
- ClickHouse grants: that CVAT's account may create a second database is
  inferred from the stock account creating the first.
- The UI plugin route on a hard page load, and shared module state between a
  plugin entry and the main bundle (section 4.2).
- How often upstream changes the files we edit; the reference checkout has no
  history.
