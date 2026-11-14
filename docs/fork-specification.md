# Fork compatibility specification

This document describes the existing fork behavior to preserve when updating
CVAT. It does not propose new features. Use it with the
[upgrade procedure](upstream-upgrade.md) and the
[dated baseline](evidence/2026-11-13-fork-baseline.md). Paths below are relative
to the repository root.

## Ownership and scope

| Area | Maintained source | Purpose |
| --- | --- | --- |
| Upstream import | `mirror-cvat.sh`, `cvat/` | Filtered Git subtree containing frontend build inputs and deployment components |
| Task progress | Eight UI files listed below | Per-stage/state job counts, legend and progress segments |
| Organization issues/comments | `opa/rules/issues.rego`, `opa/rules/comments.rego` | Broader actions and listing for members of the resource organization |
| Build and deployment | `build-ui.sh`, `docker-compose.override.yml` | Custom UI image and server-side OPA mounts |
| Verification | `verify/` | Frontend regression tests, policy tests and legacy live verification harnesses |
| Mechanical formatting | `ruff.toml`, `cvat/components/analytics/clickhouse/init.py` | Formatting convention; no intended ClickHouse behavior change |
| Team Analytics | `team-analytics/`, `build-team-analytics-service.sh`, the page and logging directories under `cvat/cvat-ui/src/`, wiring in eleven UI files (TA-1) | Work figures per annotator and project from CVAT's own events, read by a separate service |

The authoritative import path selection is `PATHS` in `mirror-cvat.sh`.
`tools/git-filter-repo` is vendored tooling, not a place for fork policy.
The filtered tree omits the Python backend and its OPA rules. Those rules must
be obtained separately from the matching full upstream revision during upgrades.

## UI-1: Task job summaries

After a relevant task-list request succeeds, request jobs for the returned task
IDs through `cvat.jobs.get` with a JSON `task_id in [...]` filter and aggregate
mode enabled. This is one core API call for the page; the core may make multiple
HTTP requests to collect paginated results. An empty task list makes no jobs call.
The same task-loading path is used by project task lists.

Initialize an independent counter for each of the three stages and four states
for every requested task. Count returned jobs by `taskId`, `stage` and `state`;
ignore jobs for other tasks and jobs with a null task ID. The current code does
not filter by job type. `fetched` is the count of jobs included for that task.

Store summaries by task ID in `tasks.jobsSummary.data`, with a separate fetching
flag. Clear summaries when a new task-list request starts. Apply a summary
success or failure only if its captured task-fetch timestamp is still current;
an old response must not replace or clear a newer page's summary.

While no summary is available, retain the upstream task progress widget and its
`done`, `on review`, `annotating`, and total labels. A failed jobs request logs a
warning and restores that fallback without turning a successful task load into
a failure. Summaries refresh through task-list loading; the fork does not add
polling or refresh them on every individual task update.

## UI-2: Progress segments and legend

With a summary available, use the same nonzero buckets for both legend and bar.
Each stage/state label is `<stage> / <state>`; keep all combinations independent,
including combinations sharing a color. Order follows `JobStage`, then
`JobState`, with unavailable jobs last. Each segment's flex weight is its job
count, and its tooltip contains the count and label.

| Stage | new | in progress | completed | rejected |
| --- | --- | --- | --- | --- |
| annotation | `#c1c1c1` | `#faad14` | `#fafe01` | `#ff4136` |
| validation | `#b4dafd` | `#1890ff` | `#00478a` | `#ff4136` |
| acceptance | `#b3ff66` | `#b3ff66` | `#61c200` | `#ff4136` |

Use `max(0, totalJobs - fetched)` for the gray (`#c1c1c1`) `not available`
bucket. This indicates a count difference, often due to visibility restrictions;
it does not establish why jobs were missing. Always display the task's total.
When both total and fetched counts are zero, show the total with no segments.
The current implementation does not clamp fetched counts that exceed the task
total.

Legend text uses the normal Ant Design text color, not the segment palette;
the total uses secondary text. Preserve the full-width, 6px-high, rounded and
clipped flex bar in `styles.scss`. Segments have a 2px minimum width, so very
small buckets are not rendered in mathematically exact proportion. The final
text-color correction supersedes the earlier colored legend implementation.

### UI integration map

All paths in this table are under `cvat/cvat-ui/src/`.

| File | Responsibility / upstream changes to inspect |
| --- | --- |
| `actions/tasks-actions.ts` | Summary thunk, filter/aggregate API contract, task-load dispatch, stale-response guard |
| `reducers/index.ts` | `TaskJobsSummary` and `TasksState` types |
| `reducers/tasks-reducer.ts` | Summary lifecycle and reset on a new task query |
| `utils/task-jobs-summary.ts` | Aggregation and palette; reconcile any new stage/state enum values |
| `containers/tasks-page/task-item.tsx` | Select a task's summary from Redux |
| `components/tasks-page/task-item.tsx` | Choose summary widget or upstream fallback |
| `components/tasks-page/task-jobs-progress.tsx` | Shared buckets, text, tooltips and proportional segments |
| `components/tasks-page/styles.scss` | Progress bar layout |

Upstream `cvat-core` job enums, pagination, visibility and job-type semantics are
dependencies of this feature even though the fork does not modify them. A newly
introduced enum value needs explicit handling in counters and colors.

## IAM-1: Organization issue and comment permissions

Each copied policy has two intentional additions to the matching upstream rule:

1. Allow actions when the authenticated organization ID equals the resource's
   organization ID and `organizations.is_member` is true. This added rule has
   no scope whitelist. Current supported actions include issue creation on a
   job, comment creation on an issue, viewing, updating and deleting.
2. For a member, return an unrestricted base filter (`{}`), then pass it through
   upstream `utils.add_organization_filter`. Listing must remain constrained to
   the selected organization, rather than to job/task/project staff assignments.

This applies to organization workers and supervisors as well as maintainers
and owners, including members who are neither assigned to the job nor owners
of the issue/comment. Both resource policies are necessary for issue discussions.

Preserve upstream context checks and existing privileges. The local extension
must not grant an ordinary nonmember access, grant a removed member access
through a stale assignment, cross organization boundaries, or expose an
organization resource in sandbox context. Sandbox behavior and upstream admin
exceptions remain upstream responsibilities. Check both global `user` and
`worker` privileges where covered by the policy tests.

Preserve the prefix Q-expression filter contract, the `org_filter_proof` marker,
and the distinction between explicitly selected sandbox and unspecified
organization context. These contracts have changed between upstream releases;
copying an old policy wholesale can silently restore an isolation bug.

The patch does not change task/job access, automatic annotation, or backend
business validation. An unassigned worker can have issue API permission yet
still be unable to open the job in the UI. Canvas verification therefore needs
a worker who can access the job.

## BUILD-1: Packaging and policy delivery

`build-ui.sh` compiles the frontend inside upstream `cvat/Dockerfile.ui`. Preserve
its selected Node image override through the named BuildKit context, disabled
source maps, and removal of stale local `cvat-ui/dist` output before building.
The script's `IMAGE` and `NODE_IMAGE` variables are supported overrides;
`SAVE=1` additionally exports a compressed image archive, while the default
only builds the image. Consult the script for current defaults.

The custom image tag belongs only to `cvat_ui`. Backend services and workers
use the matching stock upstream release through `CVAT_VERSION`; never use the
custom UI suffix as the backend version. Align the build script, deployment
override and frontend verification override when changing the default image.

The deployment overlay mounts both copied policies read-only into
`cvat_server`, under `/home/django/cvat/apps/engine/rules/`. The server packages
and serves `/api/auth/rules`; mounting files only into `cvat_opa` is insufficient.
Restart/recreate the intended server after rule changes to invalidate its
cached bundle, then verify OPA has loaded the changed bundle.

The deployment overlay expects `opa/` beside the deployment's base Compose
file. Compose resolves relative mounts from the first Compose file, so simply
combining `cvat/docker-compose.yml` with the root override from this checkout
does not satisfy that layout. The OPA verification overlay uses an absolute
`OPA_RULES` path for this reason.

## TA-1: Team Analytics

Team Analytics shows how annotation work is done: working time, sessions,
operations, creation methods, Model, saved boxes, keyboard and mouse use,
projects and trends. Admins and organization owners and maintainers see it at
`/team-analytics`, linked from the header. The terms are defined in
[`GLOSSARY.md`](../GLOSSARY.md), the decisions in
[ADR 0001](adr/0001-thin-analytics-service-with-stored-totals.md),
[ADR 0002](adr/0002-new-measurements-inside-existing-event-types.md) and
[ADR 0003](adr/0003-kubernetes-only-with-the-upstream-helm-chart.md), and the
layout in [`docs/design/team-analytics/`](design/team-analytics/design.md).

Behavior to preserve:

- The service (`team-analytics/service/`) reads only CVAT's ClickHouse `events`
  table and writes its stored totals to its own database. Its SQL lives in
  files; Python binds parameters and shapes rows. It runs from the stock
  `cvat/server` image with no added dependency (`team-analytics/Dockerfile`).
  Its Kubernetes manifests and environment are in `team-analytics/k8s/`.
  One refresh or history step runs at a time across replicas, under a lease in
  ClickHouse. The lease is renewed while a step runs and released on every
  failure path; a failed release is tried again. On SIGTERM the service
  finishes the step in progress and releases the lease before exiting. A
  replica killed mid-step would block the others until the lease expires.
- One ClickHouse client without a session serves the HTTP threads and the
  refresh loop. A request body is read and dropped, or the connection is closed
  after the answer, so a body is never answered as a request.
- Its routes are under `/team-analytics-api/v1/`. Every request is checked
  against CVAT with the caller's own cookie or token: `/api/users/self`,
  `/api/organizations`, `/api/memberships`. Admins (the `admin` group) see any
  organization, or the whole instance without one. Organization owners and
  maintainers see their organization. Everyone else is refused. A maintainer
  with no organization selected is asked to select one; the service asks CVAT
  for the caller's memberships once per reading role, so paging cannot hide
  one. A CVAT answer without the expected shape is a 503 refusal and is never
  cached. A 401 or 403 from any endpoint puts the open page into that refusal.
- The page's project and annotator filters belong to the organization named
  by `org` in the page address. Filters of another organization, or of an
  address that names none while one is selected, are not applied. Requests to
  CVAT for project names and the details project search stay bounded: names
  go 100 ids per request, and the search sends one table page of ids.
- Legacy rule: the cutover is the hour of the first shape-tagged operation on
  the instance, read from the stored totals and reported by `status`. A
  period that ends at or before it, or any period while there is none, is a
  legacy period (all shapes, the legacy notice, class change and hotkey use
  not recorded, saved boxes in place of Model). A period that begins at or
  after it is never legacy. A period that holds it is partly legacy: figures
  as usual, the shape switch stays, and the page names the cutover day. Trend
  buckets follow the same rule; the bucket that holds the cutover is not
  legacy. An empty period shows the empty state.
- New measurements travel inside existing client event types (ADR 0002):
  payload fields on draw, paste, propagate, drag, resize and delete, plus three
  `debug:info` records (`team_analytics:class_change`,
  `team_analytics:model_creation`, `team_analytics:input_summary`). The names
  are fixed in `utils/team-analytics-logging/contract.ts` and in the service
  SQL. Change them together. A batch with a scope the server does not accept is
  rejected whole, so no new scope may be introduced.
- The logging module never throws into the annotation view. After three
  failures it switches itself off for the page's life. It records nothing
  outside an open 2D job.
- The input summary written as a job closes must leave with the closing log
  save: `untrackInputJob()` settles once the record is logged, and the view
  saves after it.
- Known limitation: hotkey and mouse counts since the last summary are lost
  when the tab is closed or reloaded without leaving the job. cvat-core's only
  page-exit path (`saveCriticalEvents`) sends a fixed bandwidth record with
  `keepalive`; `logger.log` goes through the async plugin wrapper and
  `logger.save` sends without `keepalive`, so the UI cannot deliver a summary
  on `pagehide` without changing cvat-core. Upstream loses its own queued
  events on tab close too. A summary is never written on a timer alone.
- The model creation record is written only once the create thunk reports
  created objects (it resolves to `[]` on failure).
- The page fits a narrow window inside CVAT's 1024 px minimum app width: cards
  stack, and wide tables scroll inside their cards.
- With the service unreachable, the page shows its error panel. Nothing else
  in CVAT depends on the service.

### Team Analytics integration map

The feature's own code lives in new directories: `team-analytics/` (service,
SQL, manifests), `cvat/cvat-ui/src/components/team-analytics-page/` (page)
and `cvat/cvat-ui/src/utils/team-analytics-logging/` (UI logging). Its tests
and stack tooling are in `verify/team-analytics-*` and
`verify/team_analytics_*`. Upstream files get wiring only. All paths in this
table are under `cvat/cvat-ui/src/`.

| File | Responsibility / upstream changes to inspect |
| --- | --- |
| `components/cvat-app.tsx` | `/team-analytics` route (lazy page with its own error boundary); window capture listener calling `inputEvent` for key presses and clicks |
| `components/header/header.tsx` | Former "Analytics" link renamed "Grafana"; "Team Analytics" link shown by `canOpenTeamAnalytics` from the analytics plugin flag, `user.groups` and the current organization role |
| `components/annotation-page/annotation-page.tsx` | `trackInputJob(job)` where the job logger is set; on unmount `untrackInputJob().then(saveLogs)` |
| `utils/mousetrap-react.tsx` | `hotkeyUsed(action, event)` before every shortcut handler |
| `components/annotation-page/canvas/views/canvas2d/canvas-wrapper.tsx` | Shape fields on draw, canvas paste, drag and resize; `drawingStarted`/`drawingEnded` for the input method |
| `actions/annotation-actions.ts` | Shape fields on propagate, single and selection delete, and multi paste |
| `components/annotation-page/standard-workspace/objects-side-bar/labels-list.tsx` | Class change record for label hotkeys |
| `containers/annotation-page/standard-workspace/objects-side-bar/object-item.tsx` | Class change record for the sidebar label select |
| `components/annotation-page/canvas/views/canvas2d/selection-context-menu.tsx` | Class change record for the selection context menu (selector gained the job) |
| `components/annotation-page/attribute-annotation-workspace/attribute-annotation-sidebar/attribute-annotation-sidebar.tsx` | Class change record in attribute annotation mode (state gained the job) |
| `components/annotation-page/standard-workspace/controls-side-bar/tools-control.tsx` | Model creation record once the create thunk reports the detector's objects created (`createAnnotations` prop typed as returning the created ids) |

Upstream behavior this feature depends on although the fork does not modify
it:

- the `events` table schema created by `cvat/components/analytics/clickhouse/init.py`;
- the server's allowed client scopes in `apps/events` and its
  `send:working_time` calculation;
- Vector's allowlist of top-level fields (`payload` passes whole);
- cvat-core's logger (`job.logger.log`, the plugin wrapper around it, and
  `logger.save`), and the UI's 90 s periodic log save;
- the server event names for saved annotations (`create:shapes` and the like,
  with the shape type in `obj_name`);
- `createAnnotationsAsync` in `actions/annotation-actions.ts` resolving to the
  created client ids, and to `[]` when creation failed;
- `/api/server/plugins` (`ANALYTICS`), `MembershipRole`, and the memberships
  policy that lists a user's own memberships, with its `role` filter;
- the project list filter on `id` that the page uses for project names;
- CVAT's `#root` minimum width and header layout;
- the shortcut action names in the UI keymaps, which the page shows with the
  viewer's own keys.

A new upstream event type, scope, call site or shortcut action needs a
decision on whether it is an operation. A rename breaks the figures silently.

### Team Analytics acceptance scenarios

| ID | Expected observable outcome | Existing evidence mechanism |
| --- | --- | --- |
| TA-A | The real server accepts every record the UI logging adds, and each reaches the events table with its fields | Seam 2 (`node --test verify/team_analytics_logging.cjs`) for the serialized batch; `verify/team-analytics-stack/run.sh check-final` for a real browser, server and ClickHouse |
| TA-B | Stock event logging and working time are unchanged by the new logging; the closing input summary leaves with the closing save | Seam 2; `check-final` (client scopes, `client_id`, `send:working_time`, all event POSTs answered 201) |
| TA-C | For given events the service returns the agreed figures for sessions, working time, operations, creation methods, Model, saved boxes, keyboard and mouse, projects, trends, history and late events | Seam 1 (`verify/team_analytics_service.sh`, real ClickHouse); `check-final` for real UI work and loaded volume |
| TA-D | Each role gets exactly what the access rules allow, on every endpoint, with real accounts | Seam 1 with supplied CVAT answers; `check-tracer` and `check-final` against the real CVAT |
| TA-E | The page renders every state, filters, full views, comparison, long names and large numbers | Seam 3 (`node --test verify/team_analytics_page.cjs`); `check-final` in a browser |
| TA-F | With a hundred annotators and forty long-named projects the overview keeps its length and nothing overflows; on a narrow window cards stack and wide tables scroll sideways | `check-final` in headless Chrome (seam 3 has no layout) |
| TA-G | With the service stopped the page shows its error panel and annotation still draws and saves | `check-final` |
| TA-H | The service image adds no dependency to the stock server image; the UI image serves the page | `build-team-analytics-service.sh`, `build-ui.sh`; the stack run uses both images |

Seams 1 to 3 run real code with the boundaries supplied: CVAT's answers to the
service, the cvat-core transport for the logging, and the service's responses
for the page. They do not prove delivery through Vector, the real server's
scope list, or layout. The stack run proves those for the scenarios it drives.
It does not cover the detector with a deployed model (its record is sent
through the API in the shape the UI module produces), a removed member, or
CVAT being unreachable (seam 1 only). The independent review of the access
rules is recorded with the dated evidence.

## Acceptance scenarios

| ID | Expected observable outcome | Existing evidence mechanism |
| --- | --- | --- |
| UI-A | Every stage/state retains its own count and exact segment color; legend text stays default-colored | `verify/task_progress.cjs`; browser for final appearance |
| UI-B | Multiple tasks remain isolated; unrelated/null task IDs are ignored; missing jobs form only the gray difference bucket | Same regression suite |
| UI-C | Empty page makes no jobs request; zero total and zero fetched jobs render no segments | Same regression suite |
| UI-D | Paginated job collection covers the page, and stale success/failure cannot overwrite a new query | Mocked thunk/reducer tests; live API for actual pagination |
| UI-E | Failed summary fetch preserves task display and the upstream progress fallback | Mocked failure tests; browser for complete task-item fallback |
| IAM-A | Unassigned organization members can act on issues/comments and list the organization's resources | `verify/opa_issues_test.rego`; live API matrix |
| IAM-B | Nonmembers, removed members, other organizations and sandbox/context mismatches do not gain access from the patch | Same policy suite; live negative cases |
| IAM-C | Sandbox behavior and upstream filter shape remain compatible with the target release | Stock-versus-patched policy suite with target helpers |
| BUILD-A | Built image serves the changed UI without stale bundles/source maps; backend uses stock release | Image inspection and browser verification |
| BUILD-B | Both served rule files match the intended overlay and real requests exhibit the patched behavior | Bundle inspection plus live API, not marker presence alone |

The frontend suite executes real TypeScript, Redux and server-rendered React
with mocked boundaries. Its optional `BROWSER_BIN` check renders the real summary
component with Ant Design styles and the task-card stylesheet in Chrome/Chromium,
checking that annotation/new text has readable contrast above its default gray bar.
It does not exercise the full `getTasksAsync` dispatch path, task-item/container
wiring, complete page layout or a live server. Policy tests evaluate synthetic
inputs using upstream helper rules; they do not prove bundle delivery or
Django/API integration.

The current live OPA checker prints observations rather than asserting every
expected HTTP outcome. Its bundle marker check can pass when only one rule has
the marker. Inspect the actual results and both rule contents. The frontend
seed covers a subset of the stage/state matrix. These harnesses alone do not
establish every acceptance scenario.

## Changes that do not need reimplementation

The remaining ClickHouse delta is formatting only. Preserve upstream semantics
when resolving it; formatting is not a product requirement. Earlier submodule,
patch-series and custom-Dockerfile workflows have been replaced by the subtree
and upstream Dockerfile build. The old HTML head fix is absent from the current
baseline diff, and upstream Google Fonts links are retained. Reapply current
behavior, not every historical commit.

Infrastructure migration is a separate pending task governed by
[`INFRA_MIGRATION.md`](../INFRA_MIGRATION.md). The existing Compose verification
files describe the current implementation, not completion of that migration.
