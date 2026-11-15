# Fork compatibility specification

This document describes the existing fork behavior to preserve when updating
CVAT. It does not propose new features. Use it with the
[upgrade procedure](upstream-upgrade.md) and the
[dated baseline](evidence/2026-11-13-fork-baseline.md). Paths below are relative
to the repository root.

## Ownership and scope

The repository is a full-source fork of `cvat-ai/cvat`
([ADR 0005](adr/0005-a-full-source-fork-joined-to-upstream-history.md)): its
root is upstream's root, joined to upstream's history by one merge commit, and
the fork's changes are ordinary commits on top. Upstream's tree is the base;
the fork adds its own paths beside it and edits a short list of upstream files.

| Area | Maintained source | Purpose |
| --- | --- | --- |
| Upstream base | Everything not listed below, as the merged release has it | CVAT itself; taken from upstream with `git merge <release tag>` |
| Task progress | Eight UI files (UI integration map) | Per-stage/state job counts, legend and progress segments |
| Organization issues/comments | `cvat/apps/engine/rules/issues.rego`, `cvat/apps/engine/rules/comments.rego` and their test configurations | Broader actions and listing for members of the resource organization who hold at least the `worker` global role (IAM-1) |
| Organization creation | `ORGANIZATIONS_MIN_ROLE_TO_CREATE` in `cvat/settings/base.py` | Only administrators create organizations (IAM-2) |
| Team Analytics | `cvat/apps/team_analytics/`, the page and logging directories under `cvat-ui/src/`, wiring in eleven UI files, two backend settings files, one entry point component file and one chart template (TA-1) | Work figures per annotator and project from CVAT's own events |
| Build and deployment | `build-ui.sh`, `Dockerfile.ui.dockerignore`, `build-server.sh`, `Dockerfile.server` | The UI image and the fork server image (BUILD-1) |
| Verification | `verify/` | Frontend regression tests, the policy tests and the policy bundle check, the Team Analytics seams and calculation tests, and the test stack on Kubernetes (`verify/team-analytics-stack/`) that runs the live checks |
| Check pipeline | `prek.toml`, `ruff.toml`, `tools/gate/` | The fork's checks on the fork's files ([upgrade procedure, section 4](upstream-upgrade.md#4-verify-the-integrated-changes)) |

Fork-owned paths at the root, none of which upstream has: `.scratch/`, `docs/`,
`tools/`, `verify/`, `AGENTS.md`, `CLAUDE.md`, `GLOSSARY.md`,
`INFRA_MIGRATION.md`, `README.fork.md`, `build-server.sh`, `build-ui.sh`,
`Dockerfile.server`, `Dockerfile.ui.dockerignore`, `prek.toml`, `ruff.toml` and
`skills-lock.json`. The gate's Python pin (`pyproject.toml`, `uv.lock`) lives in
`tools/gate/`, because the root names are upstream's. Upstream's `README.md`
is left as upstream wrote it; the fork's text is `README.fork.md`.

The fork's complete delta inside upstream's paths:

- Deleted: upstream's `.github/`, whole (workflows, Dependabot configuration,
  code owners, issue and pull request templates). They are written for
  upstream's repository and would act on this one.
- `.gitignore`: one block of the fork's entries appended after upstream's.
- `cvat-ui/src/`, edited: `actions/annotation-actions.ts`,
  `actions/tasks-actions.ts`, `components/annotation-page/annotation-page.tsx`,
  `components/annotation-page/attribute-annotation-workspace/attribute-annotation-sidebar/attribute-annotation-sidebar.tsx`,
  `components/annotation-page/canvas/views/canvas2d/canvas-wrapper.tsx`,
  `components/annotation-page/canvas/views/canvas2d/selection-context-menu.tsx`,
  `components/annotation-page/standard-workspace/controls-side-bar/tools-control.tsx`,
  `components/annotation-page/standard-workspace/objects-side-bar/labels-list.tsx`,
  `components/cvat-app.tsx`, `components/header/header.tsx`,
  `components/tasks-page/styles.scss`, `components/tasks-page/task-item.tsx`,
  `containers/annotation-page/standard-workspace/objects-side-bar/object-item.tsx`,
  `containers/tasks-page/task-item.tsx`, `reducers/index.ts`,
  `reducers/tasks-reducer.ts` and `utils/mousetrap-react.tsx`.
- `cvat-ui/src/`, added: `components/tasks-page/task-jobs-progress.tsx`,
  `utils/task-jobs-summary.ts`, and the directories
  `components/team-analytics-page/` and `utils/team-analytics-logging/`.
- `cvat/apps/engine/rules/`, edited: `issues.rego`, `comments.rego`,
  `tests/configs/issues.csv` and `tests/configs/comments.csv`.
- `cvat/apps/team_analytics/`, added: the Team Analytics app.
- `cvat/settings/base.py` and `cvat/urls.py`, edited by lines appended at the
  end of each file: in `base.py` the organization creation rule (IAM-2) and
  the Team Analytics wiring (TA-1).
- `backend_entrypoint.d/team_analytics.conf`, added.
- `helm-chart/templates/cvat_backend/worker_team_analytics/deployment.yml`,
  added. Upstream's `helm-chart/values.yaml` is not edited.

cvat-core, cvat-canvas and the other UI packages are not edited. The list is
exact for the release the fork is on; to see it, compare with that release tag
(`v2.82.0` today):

```bash
git diff --name-status v2.82.0.. -- . ':!docs' ':!.scratch' ':!verify' ':!tools'
git log --first-parent --oneline v2.82.0..
```

The first-parent line of `main` is the fork's own history; `git log` without
it also shows every upstream commit.

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

All paths in this table are under `cvat-ui/src/`.

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

Each of the two policies, `cvat/apps/engine/rules/issues.rego` and
`cvat/apps/engine/rules/comments.rego`, carries the same two additions to the
stock file, marked with a `# Local patch (role floor):` comment, and nothing else:

1. Allow actions when the authenticated organization ID equals the resource's
   organization ID, `organizations.is_member` is true and the caller has at
   least the `worker` global role (`utils.has_perm(utils.WORKER)`). This added
   rule has no scope whitelist. Current supported actions include issue
   creation on a job, comment creation on an issue, viewing, updating and
   deleting.
2. For a member with at least the `worker` global role, return an unrestricted
   base filter (`{}`), then pass it through upstream
   `utils.add_organization_filter`. Listing must remain constrained to the
   selected organization, rather than to job/task/project staff assignments.
   The stock member branch of the filter follows the added one unchanged, so a
   member below the floor gets the stock staff filter.

This applies to organization workers and supervisors as well as maintainers
and owners, including members who are neither assigned to the job nor owners
of the issue/comment. Both resource policies are necessary for issue discussions.

The floor is the `worker` global role; `user` and `admin` are above it. The
invariant: for a caller below the floor, which in practice is an account with
no global role, the patched policies decide exactly as the stock ones for every
action and for the list filter. That is not a refusal of everything: stock lets
such a caller view an issue or comment it is staff of and list its own items.

Preserve upstream context checks and existing privileges. The local extension
must not grant an ordinary nonmember access, grant a removed member access
through a stale assignment, cross organization boundaries, or expose an
organization resource in sandbox context. Sandbox behavior and upstream admin
exceptions remain upstream responsibilities. Check the global `user` and
`worker` privileges and no global role where covered by the policy tests.

Preserve the prefix Q-expression filter contract, the `org_filter_proof` marker,
and the distinction between explicitly selected sandbox and unspecified
organization context. These contracts have changed between upstream releases;
copying an old policy wholesale can silently restore an isolation bug.

The patch does not change task/job access, automatic annotation, or backend
business validation. An unassigned worker can have issue API permission yet
still be unable to open the job in the UI. Canvas verification therefore needs
a worker who can access the job.

Upstream's generated policy tests cover both policies. Their test
configurations (`cvat/apps/engine/rules/tests/configs/issues.csv` and
`comments.csv`) carry one added row per scope the patch opens to an
organization member with at least the `worker` role; no upstream row and no
generator is changed. The generated tests do not reach the patched list
filter; `verify/opa_issues_test.rego` is its test.

The patched files reach a server only inside the fork server image (BUILD-1);
nothing mounts them, and there is no second copy of them. Because the added
rule has no scope whitelist, any scope a later upstream release adds to either
policy is granted to members at or above the floor as soon as the policies are
merged with that release. The upgrade procedure has the review step.

## IAM-2: Only administrators create organizations

The owner of an organization reads its Team Analytics (TA-1), so whoever may
create an organization may make themself a reader of figures. The owner
decided on 2026-11-15 that only administrators create organizations.

The fork sets upstream's own setting `ORGANIZATIONS_MIN_ROLE_TO_CREATE` to
`admin` in the lines appended to `cvat/settings/base.py`, on every instance,
whether or not analytics is enabled. Upstream's environment variable
`CVAT_ORGANIZATIONS_MIN_ROLE_TO_CREATE` still overrides it. Upstream's
default (`cvat/apps/organizations/default_settings.py`) is `user`, and the
organizations app takes its default only when the Django settings have none,
so the fork's value wins over it. `cvat/apps/organizations/permissions.py`
passes the setting to the policy as `organizations_min_role_to_create`, and
`cvat/apps/organizations/rules/organizations.rego` allows the `create` scope
when `utils.has_perm` of that role holds. Administrators are allowed by the
same policy's admin rule.

This changes CVAT's behavior for every user of the fork, not only for Team
Analytics: an account with the `user` or `worker` global role, or none, can no
longer create an organization, and the server refuses the attempt with 403.
Joining an organization by invitation is unchanged. CVAT's UI is not changed:
the header's organization menu still offers "Create" to every user, and the
create organization page is still reachable, so a non-administrator's attempt
ends in the server's refusal.

The rule does not look back: an organization created before it keeps its
owner.

Upstream's generated tests of `organizations.rego` give the setting in their
input (`user`), so they test the policy and not the fork's value; the value is
checked on the stack (IAM-D).

## BUILD-1: Packaging and policy delivery

The fork ships two custom images, each built by a script in this repository
from the working tree. Neither is pulled from a registry; each must be present
on the node that runs it. Every other image is upstream's or a dependency's.

| Image | Built by | Content |
| --- | --- | --- |
| UI | `build-ui.sh`, `Dockerfile.ui.dockerignore` | Upstream `Dockerfile.ui` built from the repository root, with the fork's UI changes |
| Fork server image | `build-server.sh`, `Dockerfile.server` | The stock release server image with the fork's changed and added files under `cvat/` and `backend_entrypoint.d/` copied over it ([ADR 0004](adr/0004-a-fork-server-image-that-adds-only-the-patched-policies.md), [ADR 0006](adr/0006-team-analytics-inside-the-backend-with-reads-on-a-worker.md)) |

`build-ui.sh` compiles the frontend inside upstream `Dockerfile.ui`, with the
repository root as the build context. `Dockerfile.ui.dockerignore`, which
BuildKit reads in place of `.dockerignore` for that Dockerfile, cuts the
context down to what `Dockerfile.ui` copies: the root package manifest and
lock, `.yarnrc.yml` and the five UI packages, without `node_modules`. Preserve
the script's selected Node image override through the named BuildKit context,
disabled source maps, and removal of stale local `cvat-ui/dist` output before
building. The script's `IMAGE` (default `cvat/ui:v2.82.0-fork`) and `NODE_IMAGE`
variables are supported overrides; `SAVE=1` additionally exports a compressed image archive, while the
default only builds the image. Consult the script for current defaults. The UI
build needs the network by design (it installs from upstream's lock with
`--immutable`), and what it starts from is pinned by tag, not by digest: the
Node image in `build-ui.sh`, and in upstream's `Dockerfile.ui` the nginx base
and an unpinned `corepack` install. That is upstream's build, kept as it is.

The fork server image is the stock release image named by `BASE_IMAGE`, with
every tracked file under `cvat/` and `backend_entrypoint.d/` that the working
tree adds, changes or changes the type of against the release tag `STOCK_TAG`
copied over
`/opt/cvat/`, owned by root as the stock sources are: the two patched policies
and their test configurations, the Team Analytics app, its wiring in
`cvat/settings/base.py` and `cvat/urls.py`, and the worker's component file.
The copied Python is compiled in the image, as the stock image compiles its
own. No package is installed and nothing else changes. The build context holds
exactly those files at their paths. `build-server.sh` never pulls or pushes:
the stock base must already be local, and the build runs without network.
`IMAGE` (default `cvat/server:v2.82.0-fork`), `BASE_IMAGE` and `STOCK_TAG`
(the upstream release tag, which must be local) are its supported overrides.

The image stands in for upstream's own build of the fork's tree only while
those copied files are the fork's whole difference in what the server image is
made of. `build-server.sh` refuses, before it builds, when:

- `IMAGE` equals `BASE_IMAGE`, so the stock tag is never overwritten;
- `BASE_IMAGE` is not local, or `STOCK_TAG` is not a local tag;
- anything else the stock image is built from differs from `STOCK_TAG`:
  upstream's `Dockerfile`, `cvat/requirements`, `backend_entrypoint.sh`,
  `supervisord`, `utils`, `manage.py`, `rqscheduler.py`, `wait_for_deps.sh`,
  `components/analytics/clickhouse/init.py` or `cvat/nginx.conf`. A changed
  requirement is a package the stock image does not have, and such a tree
  needs upstream's own build;
- the fork deleted a file under `cvat/` or `backend_entrypoint.d/`, which a
  copy cannot do; a rename counts as a deletion and an addition, so a renamed
  file is refused too;
- a file under those two directories is not tracked: the image is made of
  tracked files, and the working tree would differ from it;
- nothing under those two directories differs from `STOCK_TAG`.

It builds the image untagged and tags it `IMAGE` only after three checks with
the server's own bundle builder, each in a one-off container without network:
the built image's bundle holds the tree's two patched policies; the built
image's bundle with analytics enabled also holds the Team Analytics policy, so
the app is installed and loads its rules; and the base image's bundle holds the
two policies and their two helpers exactly as `STOCK_TAG` has them, so a base
of another release is refused. If one fails, the script removes only what this
run built, tags nothing, saves nothing and exits non-zero; an earlier image
under `IMAGE` stays, and the failure names its ID and says that this run did
not check it. `SAVE=1` additionally exports a compressed image archive, after
the checks.

The chart has one backend image setting, so the server, every worker, the
Team Analytics worker and the initializer run the fork server image. The
custom UI suffix is never a backend tag. A change to Team Analytics code rolls
out the backend image.

The Team Analytics worker is a Deployment of the chart
(`helm-chart/templates/cvat_backend/worker_team_analytics/deployment.yml`),
modelled on upstream's worker templates and rendered only where
`analytics.enabled` is set. It runs the fork server image with the arguments
`run worker team_analytics`. Its values live under
`cvat.backend.worker.teamAnalytics` and have their defaults in the template
(`replicas` 1, `numProcs` 3, and empty `labels`, `annotations`, `resources`,
`affinity`, `tolerations`, `additionalEnv`, `additionalVolumes`,
`additionalVolumeMounts`), merged with or added to the matching
`cvat.backend` values as upstream's workers do; upstream's `values.yaml` is
not edited. `replicas: 0` given in those values is kept, so the worker can be
stopped through the values. Its liveness probe is upstream's worker probe for the
`team_analytics` queue. There is no separate analytics image, manifest, route
or Ingress.

The policies are patched in the tree (IAM-1). The server packages the bundle it
serves at `/api/auth/rules` from its installed rules directories, so the copy
must land in the directory the server builds that bundle from. Upstream moved
the installed sources from `/home/django` to `/opt/cvat` in 2.72.0; a copy to a
directory the server does not read raises no error in the build itself and
leaves the stock policies in force. The bundle check finds that, and
`build-server.sh` runs it before it tags the image:
`verify/policy_bundle.sh from-image IMAGE [analytics]` builds the bundle with
the server's own builder in a one-off container of the image, without network
(with `analytics`, configured as where analytics is enabled), and
`verify/policy_bundle.sh check` compares each of the two policies in a bundle
given on stdin, by itself and byte for byte, with the tree's file (with
`check <tag>`, with the file at that release tag; `check-analytics` also
compares the Team Analytics policy; `check-stock <tag>` compares the four
policy files). It first refuses a bundle with two file entries whose names are
one name once normalised (`rules//issues.rego` is `rules/issues.rego`), which
the server builds when a policy exists in two registered rules directories, an
entry anywhere that is neither a regular file nor a directory (a link to a
file or to a directory), and a name that leaves the bundle. The test stack
applies the same check to the bundle the running server serves
(`run.sh check-policies`) and also requires the patch marker in each policy;
its render check refuses a backend image other than the fork server image.

Rebuild the fork server image whenever a policy or the app changes and on
every upstream upgrade, and run the backend on the rebuilt image: a running
server caches the bundle it built.

## TA-1: Team Analytics

Team Analytics shows how annotation work is done: working time, sessions,
operations, creation methods, Model, saved boxes, keyboard and mouse use,
projects and trends. Admins and organization owners and maintainers see it at
`/team-analytics`, linked from the header. The terms are defined in
[`GLOSSARY.md`](../GLOSSARY.md), the decisions in
[ADR 0001](adr/0001-thin-analytics-service-with-stored-totals.md) (the figures:
stored hourly totals, every calculation in SQL files, the trailing-window
refresh, history a day at a time),
[ADR 0002](adr/0002-new-measurements-inside-existing-event-types.md),
[ADR 0003](adr/0003-kubernetes-only-with-the-upstream-helm-chart.md) and
[ADR 0006](adr/0006-team-analytics-inside-the-backend-with-reads-on-a-worker.md)
(where the code runs and who checks access), and the layout in
[`docs/design/team-analytics/`](design/team-analytics/design.md).

### The backend app

- The app is `cvat/apps/team_analytics/`. `core/` holds the calculation code
  (periods, row reads, the withholding rule, the SQL runner, the cutover,
  history, the refresh, the prioritised step, the five endpoints and their
  sections) and the engine that puts them together; it names neither Django
  nor a caller. `sql/` holds every statement, in files: the schema of the
  totals database, the refresh calculations, the reads and the control
  statements; Python binds parameters and shapes rows. `views.py`, `urls.py`,
  `permissions.py` and `rules/` are the endpoints and their access check,
  `reads.py` the read path of the API process, `jobs.py` the worker's two
  jobs, and `default_settings.py` the settings. The app has no Django models,
  no migrations and no signal handlers.
- It reads only CVAT's ClickHouse `events` table and writes its stored totals
  to its own database (`TEAM_ANALYTICS_DB`) on the same ClickHouse server. It
  adds no dependency to the stock server image.
- The app is installed and its refresh scheduled only where analytics is
  enabled (`CVAT_ANALYTICS`, read by upstream as `ANALYTICS_ENABLED`). The
  lines appended to `cvat/settings/base.py` add the queue `team_analytics` to
  `RQ_QUEUES` (on the in-memory Redis, default job timeout 10 minutes) on
  every instance, and, with analytics enabled, the app to `INSTALLED_APPS` and
  the job `team_analytics_refresh`
  (`cvat.apps.team_analytics.jobs.refresh_totals`, cron `* * * * *`) to
  `PERIODIC_RQ_JOBS`. The line appended to `cvat/urls.py` includes the app's
  routes under `api/` when the app is installed.
- The queue is defined everywhere because CVAT's `syncperiodicjobs`, which the
  entry point's `init` runs, looks only at the queues in `RQ_QUEUES`: for each
  of them it removes every stored periodic job that the configuration no longer
  names. On an instance where analytics was switched off, the next `init`
  therefore cancels the stored `team_analytics_refresh` schedule and deletes
  its job; without the queue defined, the schedule would stay and keep queueing
  a job no worker takes.
- With analytics off the endpoints do not exist (CVAT answers 404), the refresh
  is not scheduled, and the chart renders no worker; the queue is defined and
  stays empty. The header shows no Team Analytics link, and the page reads a
  404 as "not available".

### Endpoints

- `GET /api/team-analytics/{status,overview,trends,list,details}`, without a
  trailing slash. They are left out of the published schema, so
  `cvat/schema.yml` and the SDK do not describe them. Parameters and answer
  bodies are those of the calculation code's endpoints.
- Answers: 200 with the endpoint's JSON; 400 `{"error": "bad_request",
  "detail": ...}` for a parameter refused; 401 for a caller who is not signed
  in; 403 for a refusal; 403 `{"error": "organization_required"}` for an owner
  or maintainer with no organization selected; 404 for an unknown
  organization; 429 with `Retry-After` and no body when the answer is not
  ready; 503 `{"error": "unavailable"}` when the read failed. Every response
  of the view set carries `Cache-Control: no-store`, refusals included.

### Access

- Access is decided by CVAT's permission system on every request: the policy
  `rules/team_analytics.rego`, loaded with the other apps' rules
  (`load_app_iam_rules`), and the permission class `TeamAnalyticsPermission`
  on upstream's `OpenPolicyAgentPermission`, with one scope, `view`, for all
  five endpoints. Administrators (the `admin` group, from which CVAT derives
  the global privilege) are allowed anywhere. Inside an organization its
  owners and maintainers are allowed, whatever their global role. Everyone
  else is refused, in an organization and outside one.
- The organization comes from CVAT's own context (the `org` or `org_id`
  parameter or the `X-Organization` header; cvat-core attaches the current
  organization to every request). An unknown organization is CVAT's own 404,
  before the policy is asked. A member who was removed is refused on the next
  request: the app keeps no cache of who the caller is.
- Scope: inside an organization, organization scope. An administrator with no
  organization selected reads instance scope. CVAT itself reads "no
  organization" as the caller's personal workspace; the app maps it to
  instance scope itself (`scope_of` in `views.py`), the one place where the
  app's scope differs from CVAT's context. Team Analytics has no figures of a
  single personal workspace.
- A caller refused with no organization selected who is an active owner or
  maintainer of some organization gets the 403 body
  `{"error": "organization_required"}`, and the page asks them to select an
  organization. The policy only allows or refuses; the view tells this case
  apart.
- A 401, 403 or 404 from any endpoint puts the open page into the matching
  refusal; a 404 reads as "not available", as a 403 does.

### Reads

- The API process never queries ClickHouse for the feature and imports
  neither the calculation code nor the worker's jobs; a test on the sources
  holds that. It checks access, passes on only the query parameters the
  endpoint reads (a list per endpoint, `ENDPOINT_PARAMETERS` in `reads.py`;
  a test of the calculation suite holds the list to what the endpoints read),
  refuses with 400 a value longer than a valid value of that parameter can be
  (`MAX_LENGTH`; `ids`, up to 5,000 identifiers, may be 100,000 characters),
  and looks the answer up in CVAT's default cache (Redis). A parameter an
  endpoint does not read is dropped before the key is built, so it makes no
  second cache entry and no second job. The meaning of a parameter is checked
  by the worker; a parameter it refuses is answered as 400, and that answer is
  kept only for `TEAM_ANALYTICS_FAILURE_TTL_S`.
- The key names the request only: a SHA-256 over the endpoint, the
  organization (none for instance scope), whether the caller is an
  administrator (`status` differs by it), the kept parameters and the current
  UTC hour. There is one job and one cache entry per request key. Access is
  checked before the cache is read and the key names the scope, so an entry
  is never served across organizations. An entry expires after
  `TEAM_ANALYTICS_ANSWER_TTL_S`, and a new hour is a new key.
- The worker stores each answer with the generation of the totals it read
  before computing it. A request that arrives uses a stored answer as it is
  only while that generation is the current one; otherwise it is a miss.
- On a miss the read is queued on the `team_analytics` queue as one job per
  key: a job for the key that is waiting or running is left alone, unless it
  has been so for longer than a read may take (twice
  `TEAM_ANALYTICS_READ_JOB_TIMEOUT_S` plus 120 s: its time to live, its
  timeout, the minute rq gives a job that ignores its timeout before stopping
  it by force, and a minute for API processes whose clocks disagree). Such a
  job counts as abandoned, its worker gone, and the read is queued again. The read is not
  queued, and the request replies 429 at once, when the queue already holds
  `TEAM_ANALYTICS_READ_QUEUE_LIMIT` reads, or when another request has held the
  enqueueing lock for the same key for more than a second. Only reads count:
  queued copies of the refresh job count neither against the limit nor as a
  waiting read. Otherwise the request closes its database connection (the
  permission check is done; the wait holds a thread, not a Postgres
  connection), looks into the cache every 50 ms for up to
  `TEAM_ANALYTICS_READ_WAIT_S` (0 replies at once) and replies 429 with
  `Retry-After: TEAM_ANALYTICS_READ_RETRY_AFTER_S` if the answer has not
  arrived. A waiting request takes any answer computed on the generation it
  saw when it arrived or a later one, so a refresh step that writes during its
  wait does not send it back to the queue. A queued read that no worker
  process starts within `TEAM_ANALYTICS_READ_JOB_TIMEOUT_S` is dropped: its
  request has replied.
- When the cache or the queue fails in any way (cannot be reached, or holds
  something the view cannot use, such as a job record it cannot read), the
  endpoint answers 503 `{"error": "unavailable"}`, never an error of CVAT's
  own. Known limit: CVAT's own Redis connections have no
  socket timeout (upstream's settings), so a Redis that accepts connections
  and never answers holds a Team Analytics request as long as it holds any
  other CVAT request.
- cvat-core retries a 429 by itself after the `Retry-After` delay (its
  `axios-retry` configuration, with the library's default of three retries);
  the page shows its error panel only for a 429 that outlives those retries.
  With the default settings that is four waits of 5 s and three pauses of 3 s:
  29 s before the error panel. Each retry finds the one job and the one entry
  of its request, so an answer computed meanwhile is served to it.
- The generation of the totals is a counter kept in the cache
  (`advance_generation` in `reads.py`). When there is none, it starts at the
  current time in seconds, and then grows by one per advance, so a counter
  that was lost while answers stayed in the cache starts above every
  generation those answers carry. It only grows, and no two workers' clocks
  decide between two answers. The worker
  advances it once at the end of a refresh run that may have changed what
  readers see (below), not after every step, and once the first make-ready is
  done. Answers computed on an earlier generation are then no
  longer used as they are; each is computed again when it is next asked for.
- Consequence: an answer can be older than the totals by at most one refresh
  run. An answer computed while a run writes is stored with the generation
  read before computing, so it is computed again once that run advances the
  generation.
- Known limit: a refresh run that is killed outright (out of memory, a forced
  stop) advances no generation, so the answers in the cache can stay older
  than the totals it wrote until the next run that advances it, or until
  their TTL or the hour turns: up to a refresh interval or the answer TTL.

### The worker

- The worker is `run worker team_analytics` (registered with the entry point by
  `backend_entrypoint.d/team_analytics.conf`), run by the chart's Team
  Analytics Deployment (BUILD-1) with `numProcs` processes, 3 by default. A
  process runs one job at a time. The refresh holds at most one process, and
  for more than one step only while no read is waiting (below), so two remain
  for reads by default. Every query to ClickHouse the feature
  makes runs in one of its two jobs. Neither job lets an exception out, also
  when the cache fails: a failure is logged, and CVAT's handlers for failed
  jobs never see it.
- `read_answer` computes one answer through the engine and stores it under its
  key for `TEAM_ANALYTICS_ANSWER_TTL_S`. Each statement of a read runs with a
  time limit (`TEAM_ANALYTICS_READ_STATEMENT_S`) and a memory limit
  (`TEAM_ANALYTICS_READ_STATEMENT_MEMORY_BYTES`) that ClickHouse enforces; the
  job has the timeout `TEAM_ANALYTICS_READ_JOB_TIMEOUT_S`. A read that fails
  is stored as 503 for `TEAM_ANALYTICS_FAILURE_TTL_S`, so a burst of requests
  does not repeat it at once.
- Make-ready: before the first answer the totals database exists and the
  cutover has been looked for. The first job, read or refresh, that finds no
  ready mark (`team_analytics:ready` in the cache, without expiry) creates the
  schema and runs the cutover search under the refresh lock, within its limits
  at start (below). When the search ran, failed or not, the mark is set and
  the generation advanced. A read job that finds the lock taken stores
  nothing, and its request replies 429 and is sent again. When the cache is
  emptied, the search runs once more.
- Each job builds its engine with ClickHouse clients without a session. A
  statement with a limit is run by a client that waits for an answer 5 s
  longer than the limit, so the client does not give up before ClickHouse
  stops the statement; a client that gives up does not stop the statement in
  ClickHouse.

### The refresh

- `refresh_totals` runs every minute. The scheduler queues it every minute
  whether or not the last one was taken, so a run first removes the copies of
  itself that piled up in the queue while no worker ran: they are one run's
  work. It then creates whatever of the totals
  database and its tables is missing, makes ready, then takes steps while
  there is work. Its first step always runs. After each step the run ends when
  a read is waiting in the `team_analytics` queue (reads come before history),
  and it starts no new step once `TEAM_ANALYTICS_REFRESH_BUDGET_S` have
  passed. A step is, in this order of priority:
  1. the refresh of recent hours, when the last one is
     `TEAM_ANALYTICS_REFRESH_INTERVAL_S` old: it recomputes the trailing
     `TEAM_ANALYTICS_REFRESH_WINDOW_HOURS` and replaces their hours as a whole.
     It runs at the first run after the interval has passed, so the time
     between two refreshes of recent hours is between the interval and the
     interval plus a minute;
  2. one day of history (or of days marked for a recount), newest first; with
     a refresh window shorter than a day, today's hours that have left the
     window come first;
  3. the daily check, when the last one is a day old: it compares raw counts,
     marks changed days for a recount, and looks for an earlier cutover in the
     recorded events within its limits.
- Because the first step of a run is the refresh of recent hours whenever it
  is due, waiting reads never put that refresh off, and history advances by at
  least one step a minute while there is history to fill.
- A run advances the generation of the totals once, when it ends (Reads,
  above), if a step may have changed what readers see: a step did work, a step
  found on the way that it no longer held the lock, or a step failed after it
  had reached a write (it may have made hours visible before it failed). A
  step asks whether it holds the lock before each write and before nothing
  else, and the run notes that it asked. A run with nothing to do advances
  nothing, so answers stay cached between refreshes, and neither does a step
  that failed before any write: while ClickHouse cannot be reached every run
  fails at its first read, and the answers in the cache stay usable until
  their TTL or the hour turns. The rules of a run are in `core/run.py`.
- Every statement of a refresh, of a day of history and of the control reads
  runs under `TEAM_ANALYTICS_REFRESH_STATEMENT_S`, which ClickHouse enforces,
  unless it has a limit of its own (the cutover searches in the make-ready and
  the daily check). The limit is on time only; the memory of such a statement
  is bounded only by ClickHouse's own server limits. The job's own timeout
  stops the client, not the statement; this limit stops the statement.
- Each step takes the refresh lock for itself, so between two days of history
  a due refresh comes first, and a run that finds the lock taken leaves; the
  next minute's run tries again. Which day of history comes next, and whether
  the check is due, is read under the lock.
- The lock is a Redis key (`team_analytics:refresh`) with an expiry of 120 s,
  taken without waiting. While a step runs, a thread extends it every third of
  its length (40 s); it is released on every way out, and the release waits at
  most 2 s for an extension in progress. A step asks before each write whether
  it still holds the lock. What it can prove is a deadline taken before each
  extension is sent, and the lock counts as lost within the last tenth of it;
  a lock that was lost, or taken over, is never extended again. A step that
  can no longer prove the lock stops before its next write, so nothing it
  computed is marked or becomes visible. A worker process killed inside a step
  stops extending, and holds refreshes up until the key expires: at most 120 s
  after the kill. The first run after that takes over. The lock length is not
  a setting.
- Known limit of the lock: steps exclude each other by a lock whose holder
  proves it before each write, not by a transaction. A statement that started
  under the lock keeps running in ClickHouse if the lock is lost meanwhile,
  and a Redis that loses its data frees the lock under a live holder, so two
  steps can overlap. What bounds the harm is how hours become visible: a step
  writes its rows with one version and then marks its hours with it in
  `hour_versions`, and readers take, per hour, only the rows of the highest
  marked version. A step's version is larger than every version marked when
  it began (`latest_version.sql`) and is otherwise the worker's clock in
  milliseconds. So an overlapping older step can hide newer totals only if it
  marks its hours later with a larger version, which needs a worker whose
  clock is ahead of the other's.
- Known limit of the rows of a failed or lost attempt: rows written before a
  step stopped are never marked, so readers never see them. They are removed
  only by a later refresh of the same hours that finds those hours already
  marked when it starts (the superseded rows are dropped only then), so on
  hours that were never marked before they stay in the totals tables, unread,
  until such a refresh.
- If Redis loses its data, the refresh schedule is gone until the entry
  point's `init` runs `syncperiodicjobs` again, as for upstream's own periodic
  jobs. The ready mark and the generation are lost with it; the next job makes
  ready again.

### Settings

Every setting has its default in `default_settings.py` and is read from the
environment variable of the same name; a value set in the Django settings
wins. A numeric setting whose value is not a number, is not finite, or is
below the setting's minimum (the table's last column) is reported in the log
and its default taken, so a mistyped setting can neither keep CVAT from
starting nor break every request of the feature. The API process reads the read wait, the `Retry-After`, the queue limit
and the job timeout; the worker reads the rest. In the chart,
`cvat.backend.additionalEnv` reaches both the backend pods and the Team
Analytics worker, and `cvat.backend.worker.teamAnalytics.additionalEnv` the
worker only. The ClickHouse connection is CVAT's own (`CLICKHOUSE["events"]`:
host, port, account, and the database of the `events` table).

| Setting | Default | Meaning | Minimum |
| --- | --- | --- | --- |
| `TEAM_ANALYTICS_DB` | `team_analytics` | Database of the stored totals, on CVAT's ClickHouse server | text |
| `TEAM_ANALYTICS_TECHNICAL_ACCOUNTS` | empty | User names of technical accounts, separated by commas | text |
| `TEAM_ANALYTICS_REFRESH_INTERVAL_S` | `600` | Age of the last refresh of recent hours at which the next is due | 1 |
| `TEAM_ANALYTICS_REFRESH_WINDOW_HOURS` | `48` | Recent hours the refresh recomputes | 1 |
| `TEAM_ANALYTICS_LOOKBACK_S` | `300` | How far before the refresh window the computation reads events | 0 |
| `TEAM_ANALYTICS_REFRESH_BUDGET_S` | `45` | Seconds after which a refresh run starts no new step | 0 |
| `TEAM_ANALYTICS_REFRESH_STATEMENT_S` | `300` | Execution time ClickHouse allows one statement of a refresh, a day of history or a control read that has no limit of its own | 1 |
| `TEAM_ANALYTICS_READ_WAIT_S` | `5` | How long a request waits for an answer not in the cache; 0 replies at once | 0 |
| `TEAM_ANALYTICS_READ_RETRY_AFTER_S` | `3` | `Retry-After` of a 429 | 0 |
| `TEAM_ANALYTICS_READ_QUEUE_LIMIT` | `32` | Queued reads at which a request is not queued and replies 429 | 1 |
| `TEAM_ANALYTICS_READ_STATEMENT_S` | `20` | Execution time ClickHouse allows one statement of a read | 1 |
| `TEAM_ANALYTICS_READ_STATEMENT_MEMORY_BYTES` | `536870912` (512 MiB) | Memory ClickHouse allows one statement of a read | 1 |
| `TEAM_ANALYTICS_READ_JOB_TIMEOUT_S` | `90` | Timeout of a read job, and how long a queued read waits to be started; twice it plus 120 s marks a read job as abandoned | 1 |
| `TEAM_ANALYTICS_ANSWER_TTL_S` | `900` | How long an answer stays in the cache | 1 |
| `TEAM_ANALYTICS_FAILURE_TTL_S` | `5` | How long a failed read (503) or a parameter the worker refused (400) is remembered | 1 |

Fixed in the code, not settings: the lock's 120 s, the cutover search's limits
(23 s in the make-ready, 60 s in the daily check, 512 MiB in both), the 50 ms between
looks into the cache, the parameters each endpoint reads and the longest value
of each.

### When something is unavailable

The API process does no analytical work, so the failures below show on the
Team Analytics page and nowhere else in CVAT. The stack checks this on a
running CVAT (`run.sh check-isolation [worker-down|clickhouse-down|totals-dropped]`, see the
[stack's README](../verify/team-analytics-stack/README.md)).

- The worker stopped: reads are queued up to the queue limit, each request
  waits the read wait and replies 429, and once the queue is full requests
  reply 429 at once. The page shows its error panel after cvat-core's
  retries (29 s with the defaults). Queued reads expire after the job timeout. No refresh runs, so the
  freshness that `status` reports grows old; answers already in the cache are
  still served until the hour turns or they expire.
- ClickHouse unavailable: a read fails, is stored as 503 for the failure time,
  and the page shows its error panel. A refresh run fails at its first read,
  logs the failure and advances no generation, so answers already in the cache
  are still served until their TTL or the hour turns; the next minute's run
  tries again.
- The totals database missing: reads fail as above until the next refresh run,
  which creates the database and its tables again.
- Redis (the cache or the queue) unreachable: the endpoints answer 503 and the
  page shows its error panel. This Redis is CVAT's own, so unlike the cases
  above it is not a failure that only Team Analytics sees.

### Figures and their limits

- A read of a period that is not fully processed carries no figures, whoever
  asks: it keeps its envelope, says `processed: false`, and every other field
  is null. The envelope of each endpoint:
  - overview: `period`, `filters`, `processed`, and `operations` with only
    its legacy flags (`legacy`, `partly_legacy`, `cutover`, `shapes`); every
    other section is null whole, rows and all;
  - full-view list: `period`, `processed`, `by` and the legacy flags;
  - details table: `by`, `page_size`, `processed`, `technical_accounts` (how
    many accounts are configured as technical) and the legacy flags; it
    returns neither the period nor a filter echo, in any answer;
  - trends: each bucket says whether it is processed; in every line the point
    of a bucket that is not fully processed keeps `legacy` and
    `hotkey_recorded` and has null values. A comparison candidate's
    `working_time_ms` sums only the fully processed buckets and is null while
    none is; candidates are ranked by it, then by id, so time in a bucket not
    fully processed ranks nobody. Who is a candidate still comes from every
    computed hour of the twelve buckets, processed or not, so that the
    comparison can be offered while history is processed.

    Known limit of the candidates: the list tells who has work in buckets
    that are not processed yet, which every other read withholds. While no
    bucket is processed it names everyone with work in the twelve buckets;
    once one is, a `working_time_ms` of 0 (not null) marks exactly the
    candidates whose only work lies in buckets not yet processed. Both stay
    inside the caller's scope (the selected organization, or the whole
    instance for an admin with none selected), project and annotator filters
    applied, technical accounts left out. Listing candidates from every
    computed hour was the implementer's choice, not the owner's. Whether to
    keep it as it is, to send null in place of a counted 0, or to list only
    candidates with work in processed buckets is an open decision for the
    owner.

  Each endpoint reads how far history is processed once per read, before it
  reads any figure, so a history step that finishes during a read can only
  make the answer say `processed: false` where it could have said true, never
  mark figures read before the step as processed. The page shows that the
  period is being processed.
- Known limit of unprocessed periods: the legacy flags of an answer that is
  not fully processed (`legacy`, `partly_legacy` and `shapes`, and
  `hotkey_recorded` on a trend point) describe only the part already
  processed, and can change, even to the opposite, once processing completes.
  A caller must not read them as final while `processed` is false. The page
  hides the shape switch while the overview's `operations.legacy` is true, so
  the switch can appear or vanish when a period's processing completes.
- `status` depends on who asks. An administrator, with or without an
  organization selected, gets the whole history block: `complete`, `percent`,
  `ready_from`, `ready_from_day`, `first_day`, `days_ready`, `days_total`,
  `periods`, `earliest_month`, `complete_weeks`, `trends_ready`. Everyone else
  who may read gets `complete`, `percent`, `periods`, `earliest_month`,
  `complete_weeks` and `trends_ready`. Both get `refresh` (freshness) and
  `cutover`. Every one of these fields describes the whole instance, not the
  caller's organization: history is processed for the instance as a whole.
- Known limit of `status` for a caller outside the admin group: while history
  is processed, such a caller who polls status can work out the instance's
  exact first event day, and so the length of its history. The percentage is
  "days processed / days in the instance"; each time `earliest_month` changes
  the processed days begin on that month's first day, and each time
  `complete_weeks` changes (below twelve) on a Monday, so the processed day
  count is known exactly at those moments and the percentage then gives the
  total. The `processed` flags of the overview, the list and the details table
  for any `month`, and the trends' per-bucket flags, bound the same to the
  month or the week. After history is complete the window reopens briefly: an
  event dated before the instance's first day makes `complete` false again for
  a step or two, and for that time the same applies to the older history.
  Making the percentage coarser (rounded, or not tied to the instance's day
  counts) would blunt this; that is an open decision for the owner.
- The details table by project lists every project in the caller's scope with
  working time, operations or saved boxes, so a project whose only work is
  boxes saved by a technical account has a row (no working time, its saved
  boxes and its Model boxes). A technical account never appears in the table
  by annotator or in any other list of people, and under an annotator filter
  on its id its saved boxes neither list a project nor count for one.
- The page's project and annotator filters belong to the organization named
  by `org` in the page address. Filters of another organization, or of an
  address that names none while one is selected, are not applied. Requests to
  CVAT for project names and the details project search stay bounded: names
  go 100 ids per request, and the search sends one table page of ids.
- Known limit of the annotator search in the details table: the page sends
  the search text, trimmed, as `search`, and the API refuses a value longer
  than 200 characters with 400. The page's search input has no length limit
  of its own, so a longer search shows the table's failed state ("Details
  could not be loaded.") instead of a result. A project search is matched on the page and is
  not sent.
- Legacy rule: the cutover is the hour of the first shape-tagged operation
  event on the instance, reported by `status`. It is looked for in the
  recorded events with one statement over the raw events: in the make-ready
  before the first answer; in the daily check; and in the step that first
  stores a shape-tagged hour while none is stored, before those hours become
  visible. Every hour found is stored in the totals database, and reads use
  the earliest stored hour, so the cutover moves to an earlier hour when an
  earlier shape-tagged event turns up and never to a later one. Until an hour
  is stored there is no cutover. A period that ends at or before it, or any
  period while there is none, is a legacy period (all shapes, the legacy
  notice, class change and hotkey use not recorded, saved boxes in place of
  Model). A period that begins at or after it is never legacy. A period that
  holds it is partly legacy: figures as usual, the shape switch stays, and the
  page names the cutover day. Trend buckets follow the same rule; the bucket
  that holds the cutover is not legacy. An empty period (no job work in the
  scope) shows only the empty state: no legacy notice and no partly-legacy
  notice.
- Known limits of the stored cutover: it is looked for in the recorded events
  in the make-ready and in the daily check, and every hour found is stored;
  the earliest stored hour is the cutover. An earlier shape-tagged event that
  arrives late therefore moves the cutover only at the next daily check, and
  the periods in between read as legacy until then. A later event never moves
  it. A shape-tagged event with a wrongly early date moves the cutover to its
  hour, and deleting the stored value does not undo that: the next search
  finds the same event. The correction is to remove that event from the
  `events` table, then every row of the `cutover` table in the totals
  database, and then to wait for the daily check, which finds the cutover
  again. Until then there is no cutover and every period reads as legacy. The
  search reads the recorded events in time order and stops at the first
  shape-tagged one. Once a cutover is stored it finds none, so it reads every
  recorded event before the stored cutover; while none is stored it reads up
  to the first tagged event, or all of them when there is none. Its cost
  therefore grows with the history before the cutover. What it cost at the
  volume of the design measurements, in each of these cases, is in
  `docs/evidence/2026-11-14-cutover-search-cost.md`. The search in the
  make-ready and in the daily check runs with limits that ClickHouse enforces
  on the statement: 23 s in the make-ready, 60 s in the daily check, and
  512 MiB of memory in both. ClickHouse stops a search that reaches one; that
  is the bound. A search that fails or is stopped in the make-ready lets the
  make-ready finish without it; in the daily check the step ends without it.
  Either way the cutover is looked for again at the next daily check, so on an
  instance whose history before the cutover takes longer than the limit to
  read, the search keeps failing: the cutover is then found only by the
  refresh that first stores a shape-tagged hour while none is stored (that
  search has only the refresh statement limit, `TEAM_ANALYTICS_REFRESH_STATEMENT_S`),
  and a late earlier event never moves it. Once a
  cutover is stored on such an instance, every search in the daily check is
  stopped at its limit and spends up to 60 s of ClickHouse time, and of one
  worker process under the lock, for nothing, and a make-ready after the cache
  was emptied waits up to 23 s. The only sign is the error the worker logs
  each time. The events table records only when an event happened, not when
  it arrived, so the search cannot be narrowed to the records added since the
  last one.
- Trust model: every figure is reported by the browser of the person it
  describes. Team Analytics checks who may read figures, not whether the
  events behind them are true. An account that can send client events can add
  figures for itself: working time, sessions, operations, creations, Model
  creations, class changes and hotkey counts, at any past hour and under any
  project or task id, inside each organization it belongs to; it cannot write
  under another person's name. Any account, with no organization and no
  global role, can move the instance's cutover earlier with one shape-tagged
  event dated early: at the next daily check that hour is the cutover for
  every organization, and the periods after it read as not legacy. The
  correction is the one above (remove the event, then the stored value). How
  this is known: the calculation half was run on its test harness (a forged
  event from an account outside every organization moved the cutover and
  changed another organization's figures); the CVAT half was read, not run
  (stock CVAT allows every authenticated caller to send events, sets the user
  and organization of a client event from the request, and takes the job,
  task and project ids, counts, durations, payload and time from the client).
  Whether to bound the cutover search (for example by a configured earliest
  date, or by an administrator's setting) is open for the owner: the search is
  the owner's decision (ticket 17 of the defect fixes), and the question is
  filed as
  `.scratch/team-analytics/issues/19-any-account-can-move-the-cutover-and-add-its-own-figures.md`.
- Known limits of the app's reach into ClickHouse: it uses CVAT's own account
  (`CLICKHOUSE["events"]`, which the chart fills from `cvat-analytics-secret`),
  the account CVAT writes its events with, so it could write to or drop CVAT's
  `events` table, not only its own database. A dedicated account (read on the
  events database, write on the totals database) is a deployment decision; the
  app takes its account from `CLICKHOUSE["events"]` only. A read whose statement reaches
  its time or memory limit fails and answers 503, also a legitimate read on a
  large scope; the limits are settings. The statements of a refresh and of a
  day of history have a time limit (`TEAM_ANALYTICS_REFRESH_STATEMENT_S`) and
  no memory limit of the app's own: their memory is bounded only by
  ClickHouse's server limits.
- Who can read, and what remains: only administrators create organizations
  (IAM-2), so the readers besides administrators are the owners and
  maintainers of organizations an administrator created, each in their own
  organization. Two things remain. Organizations created before the rule keep
  their owners, since the setting does not look back. And an owner or
  maintainer still sees in `status` the instance-wide state that the limit of
  `status` for a caller outside the admin group (above) describes; what
  `status` shows such a caller was decided by the owner on 2026-11-14 and is
  unchanged. An instance that overrides
  `CVAT_ORGANIZATIONS_MIN_ROLE_TO_CREATE` with a lower role makes every
  account at that role a possible reader of its own organization's figures.
- Known limit of the read queue: there is no per-user limit on waiting
  requests or queued reads. The queue limit is shared by everyone, so one
  account that sends many different valid requests can make others get 429
  from Team Analytics. CVAT's own endpoints are not affected: a waiting
  request holds a thread of the API process and no database connection, as
  with the worker stopped (TA-G).
- Upstream's Compose files enable analytics on the server but start no Team
  Analytics worker. With a fork server image under Compose no worker takes
  the refresh job or a read, and every read answers 429. Compose is not
  supported ([ADR 0003](adr/0003-kubernetes-only-with-the-upstream-helm-chart.md)).
- New measurements travel inside existing client event types (ADR 0002):
  payload fields on draw, paste, propagate, drag, resize and delete, plus three
  `debug:info` records (`team_analytics:class_change`,
  `team_analytics:model_creation`, `team_analytics:input_summary`). The names
  are fixed in `utils/team-analytics-logging/contract.ts` and in the app's SQL
  (`cvat/apps/team_analytics/sql/`). Change them together. A batch with a
  scope the server does not accept is rejected whole, so no new scope may be
  introduced.
- A redo is no operation. Redoing created objects adds no creation and no
  creation method, and its time is Other; inside a job it still ends an
  alignment run.
- A group move (several selected objects dragged together, or the selection
  box moved) is one alignment for each object moved, sharing the gesture's
  time equally; a group of boxes and other shapes counts only its boxes under
  Bounding boxes, with the time split as for any mixed selection. It ends the
  alignment runs before it, and no later drag continues it. The UI logs it as
  one `drag:object` with `group` = `move` and the objects moved in its count;
  CVAT's own drag of the grabbed object is still logged, carries `group` =
  `grabbed` and is no operation.
- Effect of the group event on CVAT's own logging (for the owner to weigh
  against "CVAT's own event logging unchanged"): nothing CVAT logged is
  removed, reordered or delayed, and nothing fails for the annotator. A group
  drag adds the one group `drag:object` beside CVAT's own drag of the grabbed
  object. A move of the selection box, which CVAT did not log, now adds one
  `drag:object` where CVAT logged nothing. The logger merges consecutive
  frame-change records, and any other record ends that merging, as CVAT's own
  drags already do: frame steps either side of such a move become two
  `change:frame` rows where they were one. CVAT's own analytics read the added
  `drag:object` rows like any other drag. The server's working time is
  unchanged. The stock serializer accepts `count` on any scope.
- Known limit of the group event: the grabbed mark is set as soon as the group
  record is handed to the logger, whether or not the logger later refuses it.
  If the group record is refused after the mark is set, the grabbed object's
  drag is still no operation and the gesture's objects are lost from the
  figures. No real path to this is known: the stock logger refuses only a
  payload that is not an object. If the group logging throws instead, no mark
  is set and the grabbed drag counts as before. The two records keep their
  order (group record first).
- A frame-navigation hotkey counts one hotkey action for each frame change its
  own handler starts that shows another frame. A change counts as the key's
  when `changeFrameAsync` starts in the key's own turn: while its handler runs
  or in the microtasks after it, where the frame and annotation searches
  resolve. A press whose handler starts no change (nothing found, no further
  key frame, the first or last frame, navigation blocked, a repeat while the
  frame loads) counts nothing, and a change started later by anything else (a
  playback step, the frame number field, the slider, a search already
  running) is never credited to it. Known limit: a frame search waits for the
  server while cvat-core's frame meta is being fetched or saved (its hourly
  reload during a frame load, a save after frames were deleted or restored,
  or meta not yet loaded). A key pressed then starts its change after its
  turn, and that change counts nothing. This undercounts by at most one per
  such press and never credits the wrong key. The key's turn lasts a fixed
  100 microtasks after its handler, against about ten on the deepest chain
  known, so a few more awaits on the way (a cvat-core plugin wrapper, say)
  change nothing. A chain that takes more than 100 microtasks, or that waits
  for anything outside the microtask queue (the network, a timer), starts its
  change after the turn, and that press likewise counts nothing.
- Known limit of the stored totals: a changed counting rule (the redo rule,
  the group-move rule) does not recompute hours already stored. The trailing
  refresh window follows the new rule from the next refresh. An older day
  keeps the figures it was stored with until it is computed again, which
  happens only when its raw event count, or that of the day before or after
  it, changes. In hours stored before the redo rule a redo of created objects
  is a creation with its time, under the method of the creation it restored
  or as Drawn; a stored `redone` row is read as Drawn. Hours whose events came
  from a UI without the group event hold a group drag as one alignment of the
  grabbed object and a selection-box move as none; computing them again gives
  the same, since the events carry no group. Hours whose events came from a UI
  with the group event but were stored by a calculation without the
  group-move rule hold a group drag as two alignments and a selection-box move
  as one; computing them again gives one per object moved. Under that old
  rule the grabbed object's drag also keeps its object reference, so a later
  drag of the same object continues its run: a group drag of two boxes
  followed by a drag of the grabbed box is stored as 2 alignments under the
  old rule and 3 under the new one.
- Known limit of stored hotkey counts: the input summary carries only counts.
  Summaries recorded before the frame-navigation rule, or later by a browser
  still running an older UI bundle (until the page is reloaded), hold one
  count per invocation of a frame-navigation key, a held key on a slow frame
  included. They stay in the raw records as counted then, and no recount can
  correct them, since the raw records do not say which frames moved. A period
  that spans the deployment mixes both rules.
- Known limits of a refresh window shorter than a day
  (`TEAM_ANALYTICS_REFRESH_WINDOW_HOURS` below 24): today's hours before the
  window are computed by the history step once each has left the window. A
  record that reaches ClickHouse after its hour was computed (client records
  arrive in batches, often minutes late) is counted only when its day is
  computed as a whole, after midnight; until then the period reads as
  processed without it. And after each refresh that moves the window on, the
  hour that left it waits for the history step that follows. Until then every
  period and trend bucket that holds that hour reads as not processed yet, and
  status offers no month and counts no complete week, since both, like
  `ready_from` and `ready_from_day`, are counted from the moment after which
  everything is processed; the day count and percentage keep the days before
  today, and a period or bucket that ends before the waiting hour keeps its
  figures. For that hour a person sees no month offered on the page and the
  trends card saying that none are ready, while an earlier month or week, asked
  for directly (the overview, the trends), still answers as processed. The
  default window of 48 hours does not behave so: the next ten-minute refresh
  counts a late record, and no hour of today lies before the window.
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
- Known limit of what is counted as created: tags, and objects made with the
  interactive AI tools (interactors) or with OpenCV, are not creations
  (glossary, Creation). The UI logging adds no record for making them, so
  they add no creation, creation method or creation time, and the time spent
  making them is Other. A tag carried by a recorded paste or deletion of
  several objects is described with shape type `tag` and counts with it under
  All shapes, never under Bounding boxes.
- Known limit of 3D jobs: only sessions and working time are measured as
  designed (glossary, Job work). The 3D canvas is not instrumented and the
  logging records nothing outside a 2D job, so 3D work writes no class change,
  Model or input summary record and adds no hotkey or mouse count, and its
  events carry no shape fields. The stock 3D canvas still logs its own draw
  and paste events, and a deletion there is logged as in 2D; the SQL reads
  such untagged events as it reads records from before the cutover, so under
  All shapes they count as drawn or pasted creations and as deletions, with
  their time, and under Bounding boxes not at all. This last point is read
  from the SQL, not seen on a 3D job.
- Known limit of session length: the glossary bounds a session at a day; the
  calculation bounds it where a computation starts reading. A refresh reads
  the events from one day before the hours it computes (the refresh window,
  or one day of history), so a session that began earlier is cut there: it is
  stored from its first event after that point, and the work before it
  belongs to no session. Once a session's day is computed as history it
  therefore starts no earlier than midnight UTC of the day before the day it
  ends in, and can span up to two days when it ends late in its day. A cut
  session spans more than a day less the session gap. How many stored
  sessions reach that span is counted by the stack's
  `run.sh check-fixes sessions-at-limit`.
- The model creation record is written only once the create thunk reports
  created objects (it resolves to `[]` on failure).
- Known limit of the split by operation: Other is working time minus the time
  of the four operations, and is never below zero. A row whose operation time
  exceeds its working time therefore has Other at zero, and its bar is drawn
  at the row's working time with the operation parts stretched to fill it,
  in the full view and in the overview's bars by annotator and by project.
  Each part's hover gives its own hours. The overview's "where working time
  goes" reads Other with the same floor over its whole scope. For such a row
  the parts shown add up to more than its working time, while the page's
  definitions say of working time that every breakdown of time adds up to it.
  The rule is the calculation's; the owner has not been asked about the
  wording beside it. Whether to change the definition's wording or how such a
  row is shown is an open decision for the owner.
- Known cost of the overview's rows: its working time by annotator and by
  project each run the full view's whole row read, with every row's
  operations, creation methods and Model, and use only the top eight rows and
  their operation parts. That one shared read is what keeps an overview row's
  split equal to the same row in the full view. Each of its statements is held
  to the read limits above; what it costs on a large scope belongs in dated
  evidence.
- The page fits a narrow window inside CVAT's 1024 px minimum app width: cards
  stack, and wide tables scroll inside their cards.

### Team Analytics integration map

The feature's own code lives in new directories: `cvat/apps/team_analytics/`
(the backend app with its calculation code, SQL and policy),
`cvat-ui/src/components/team-analytics-page/` (page) and
`cvat-ui/src/utils/team-analytics-logging/` (UI logging). Its tests and stack
tooling are in `verify/team-analytics-*` and `verify/team_analytics_*`; the
policy's generated test configuration is in
`cvat/apps/team_analytics/rules/tests/`. Upstream files get wiring only. All
paths in this table are under `cvat-ui/src/`.

| File | Responsibility / upstream changes to inspect |
| --- | --- |
| `components/cvat-app.tsx` | `/team-analytics` route (lazy page with its own error boundary); one call `listenForInput(window)` in `componentDidMount`, which attaches the logging's own capture listeners for key presses and clicks (upstream's listener is unchanged) |
| `components/header/header.tsx` | Former "Analytics" link renamed "Grafana"; "Team Analytics" link shown by `canOpenTeamAnalytics` from the analytics plugin flag, `user.groups` and the current organization role |
| `components/annotation-page/annotation-page.tsx` | `trackInputJob(job)` where the job logger is set; on unmount `untrackInputJob().then(saveLogs)` |
| `utils/mousetrap-react.tsx` | `hotkeyUsed(action, event)` before every shortcut handler |
| `components/annotation-page/canvas/views/canvas2d/canvas-wrapper.tsx` | Shape fields on draw, canvas paste, drag and resize; `drawingStarted`/`drawingEnded` for the input method; `groupMoved(job, e.detail)` in the `canvas.groupmoved` handler before its first `await` (the grabbed object's drag then gets the group mark through the drag's shape fields) |
| `actions/annotation-actions.ts` | Shape fields on propagate, single and selection delete, and multi paste; in `changeFrameAsync`, `frameRequested()` at its start and `frameShown(hotkey, frame, toFrame)` just before `CHANGE_FRAME_SUCCESS` |
| `components/annotation-page/standard-workspace/objects-side-bar/labels-list.tsx` | Class change record for label hotkeys |
| `containers/annotation-page/standard-workspace/objects-side-bar/object-item.tsx` | Class change record for the sidebar label select |
| `components/annotation-page/canvas/views/canvas2d/selection-context-menu.tsx` | Class change record for the selection context menu (selector gained the job) |
| `components/annotation-page/attribute-annotation-workspace/attribute-annotation-sidebar/attribute-annotation-sidebar.tsx` | Class change record in attribute annotation mode (state gained the job) |
| `components/annotation-page/standard-workspace/controls-side-bar/tools-control.tsx` | Model creation record once the create thunk reports the detector's objects created (`createAnnotations` prop typed as returning the created ids) |

The backend's touch points outside the app:

| File | Responsibility / upstream changes to inspect |
| --- | --- |
| `cvat/settings/base.py` | Appended block: `ORGANIZATIONS_MIN_ROLE_TO_CREATE` set to `admin`, always (IAM-2); the `team_analytics` queue in `RQ_QUEUES` on `REDIS_INMEM_SETTINGS`, always; behind `ANALYTICS_ENABLED`, the app in `INSTALLED_APPS` and the refresh in `PERIODIC_RQ_JOBS` |
| `cvat/urls.py` | Appended include of the app's routes under `api/` when the app is installed |
| `backend_entrypoint.d/team_analytics.conf` | The `team_analytics` component, so that `run worker team_analytics` starts a worker for the queue |
| `helm-chart/templates/cvat_backend/worker_team_analytics/deployment.yml` | The worker's Deployment (BUILD-1) |

#### Upstream internals the fork depends on

The app depends on upstream internals that are not documented extension
points ([ADR 0006](adr/0006-team-analytics-inside-the-backend-with-reads-on-a-worker.md)).
For each, what breaks if upstream changes it and how it would show:

- `OpenPolicyAgentPermission` in `cvat/apps/iam/permissions.py`
  (`create_base_perm`, `get_scopes`/`_get_scopes`, `url`, `get_resource`) and
  `PolicyEnforcer`, which calls a view's `iam_permission_class`: a changed
  signature fails every Team Analytics request, or the import of the app at
  start; the stack's access checks fail.
- `load_app_iam_rules`: without it the policy is not in the bundle and every
  request is refused; `build-server.sh`'s analytics bundle check fails before
  the image is tagged.
- `PERIODIC_RQ_JOBS`, `RQ_QUEUES` and `REDIS_INMEM_SETTINGS` in
  `cvat/settings/base.py`, and `syncperiodicjobs`, which the entry point's
  `init` runs: a renamed setting fails the settings import at start; a changed
  job format or sync leaves the refresh unscheduled, and `status` shows the
  freshness growing old. If `syncperiodicjobs` stops removing the stored jobs
  of a configured queue that the configuration no longer names, an instance
  where analytics was switched off keeps its refresh schedule; the stack's
  `check-analytics-off` shows it.
- The organization middleware and `request.iam_context` (`organization`,
  `privilege`), with `IAM_ADMIN_ROLE` and the `Membership` model's roles and
  `is_active`: a change gives a wrong scope, a missing `organization_required`,
  or a 500; the stack's access cases fail.
- The entry point's component files (`backend_entrypoint.d/*.conf`, merged by
  `backend_entrypoint.sh`, and `run worker <component>` with `NUMPROCS`): a
  change in their format stops the worker from starting; its pod fails and the
  page shows its error panel.
- The chart's helper templates the worker template uses (`cvat.labels`,
  `cvat.selectorLabels`, `cvat.backend.serviceAccountName`,
  `cvat.sharedBackendEnv`, `cvat.backend.worker.livenessProbe` and
  `cvat.backend.worker.livenessProbe.workers`, `cvat.backend.initContainers`)
  and the `cvat.backend` and `analytics.enabled` values: a renamed helper fails
  the render; a changed value layout renders a worker without the backend's
  environment. The stack's render and preflight show the first; the second
  shows as a worker whose reads fail.
- `rq`, `django_rq` and Django's default cache on Redis, shared by the API
  process and the worker: the view uses the queue's connection lock,
  `fetch_job`, `count` and `enqueue` with `job_timeout` and `ttl`, and both
  sides use `caches["default"]`. A default cache that is not shared would leave
  every read at 429.
- `core.server.request` in cvat-core (`serverRequest`, returning the Axios
  response), `core.config.backendAPI` and `ServerError` with the HTTP status as
  its code: a change breaks the page's one boundary (`service.ts`), and every
  request shows the error panel.
- cvat-core's retry of a 429 (`axios-config.ts`, `axios-retry` with the
  `Retry-After` delay): without it every miss shows the error panel at once
  instead of the figures after a retry.
- cvat-core's error text (`generateError` in `cvat-core/src/server-proxy.ts`
  writes an unknown JSON body as `**<field>**: <value>` lines of the error's
  message): the page recognises `organization_required` from that text. If the
  format changes, an owner or maintainer with no organization selected sees
  "not available" instead of the request to select one; the page suite's
  stand-in for cvat-core does not follow such a change.
- `ORGANIZATIONS_MIN_ROLE_TO_CREATE` (IAM-2): its name, its environment
  variable, the organizations app's way of taking its default only when the
  Django settings have none, and its use in `organizations.rego`. A rename or
  a change in how the default is applied lets every `user` create
  organizations again, with no error; the stack's `check-org-creation` shows
  it.
- Upstream's generated policy test runner
  (`cvat/apps/iam/rules/tests/generate_tests.py`) and the conventions of its
  generators, which the app's generator follows as the events app's does: a
  change fails the generation, or the tests generated for the app.

Upstream behavior this feature depends on although the fork does not modify
it:

- the `events` table schema created by `components/analytics/clickhouse/init.py`;
- the server's allowed client scopes in `cvat/apps/events` and its
  `send:working_time` calculation;
- Vector's allowlist of top-level fields (`payload` passes whole);
- cvat-core's logger (`job.logger.log`, the plugin wrapper around it, and
  `logger.save`), and the UI's 90 s periodic log save;
- the server event names for saved annotations (`create:shapes` and the like,
  with the shape type in `obj_name`);
- `createAnnotationsAsync` in `actions/annotation-actions.ts` resolving to the
  created client ids, and to `[]` when creation failed;
- `/api/server/plugins` (`ANALYTICS`), the `admin` group in `user.groups`, and
  the UI's current organization role (`organizations.currentRole`), from which
  the header decides whether to offer the link;
- the project list filter on `id` that the page uses for project names;
- CVAT's `#root` minimum width and header layout;
- the shortcut action names in the UI keymaps, which the page shows with the
  viewer's own keys;
- the canvas's order for a group move (`cvat-canvas`, `canvasView.ts`): it
  dispatches `canvas.groupmoved` and then, when the gesture began on an
  object, that object's `canvas.dragshape`, synchronously in one task, and the
  wrapper's group-moved handler calls `groupMoved` before its first `await`.
  The grabbed mark lasts only to the end of that task. If upstream reorders the
  two or defers the drag, the grabbed drag loses its mark and counts again (a
  group of three becomes four alignments); if it logs a drag per member, every
  member but one counts again. Either happens with every suite green: both
  suites hand-order the calls, and the handler declares its own detail type,
  so a renamed field is no type error either.
  The stack's gestures (`run.sh check-fixes gestures`) catch a change in the
  group record itself: a selection moved by its header label and a pasted
  selection dragged are read back from the events table, one group record
  each. They do not catch a reordered or deferred grabbed drag: on the stack
  (2026-11-15) neither gesture produced CVAT's own drag of a grabbed member.
  Right after a region selection a press on a member clears the selection,
  and a press inside a selected pair hits the selection box, so the grabbed
  path was not reached in a browser;
- frame changes: the shown frame changes only through `changeFrameAsync`, and
  nothing between a navigation shortcut's handler and the start of
  `changeFrameAsync` waits for a later task (the top bar's frame search and
  `searchAnnotationsAsync`'s annotation search answer in microtasks once the
  frame meta is loaded). A new path that shows a frame leaves the module's
  last shown frame stale, so the next key may be counted for a frame it did
  not move or not counted for one it did; a handler that comes to wait for a
  later task makes its key count nothing. Neither fails a suite, since the
  harness drives the top bar over supplied searches. The stack's held-key
  step (`run.sh check-fixes gestures`: a navigation key held while the frame
  data requests are held back, its count compared with the frames shown)
  was meant to catch a stale last shown frame. On the stack (2026-11-15)
  the frame change did not wait for the frame's data, so every key-down
  moved a frame, and a count of every key-down would have matched as well;
  only the press at the last frame, which must count nothing, told the rule
  from its absence. It does not reach a handler that waits either. CVAT's merged `change:frame` records
  count fewer steps than were shown (a record already sent keeps its count),
  so they are not a measure of frames moved.

A new upstream event type, scope, call site or shortcut action needs a
decision on whether it is an operation. A rename breaks the figures silently.

### Team Analytics acceptance scenarios

| ID | Expected observable outcome | Existing evidence mechanism |
| --- | --- | --- |
| TA-A | The real server accepts every record the UI logging adds, and each reaches the events table with its fields | Seam 2 (`node --test verify/team_analytics_logging.cjs`) for the serialized batch; `verify/team-analytics-stack/run.sh check-final` for a real browser, server and ClickHouse |
| TA-B | Stock event logging and working time are unchanged by the new logging; the closing input summary leaves with the closing save | Seam 2; `check-final` (client scopes, `client_id`, `send:working_time`, all event POSTs answered 201) |
| TA-C | For given events the app returns the agreed figures for sessions, working time, operations, creation methods, Model, saved boxes, keyboard and mouse, projects, trends, history and late events | Seam 1 (`verify/team_analytics_backend.sh`, the calculation tests against a real ClickHouse); `check-final` for real UI work and loaded volume |
| TA-D | Each role gets exactly what the access rules allow, on every endpoint, with real accounts; a removed member is refused on the next request; no cached answer is served across organizations | Upstream's generated policy tests for `rules/team_analytics.rego`; `check-tracer`, `check-final` and `check-access` against the real CVAT; `check-cross-org` for cached answers |
| TA-E | The page renders every state, filters, full views, comparison, long names and large numbers | Seam 3 (`node --test verify/team_analytics_page.cjs`); `check-final` in a browser |
| TA-F | With a hundred annotators and forty long-named projects the overview keeps its length and nothing overflows; on a narrow window cards stack and wide tables scroll sideways | `check-final` in headless Chrome (seam 3 has no layout) |
| TA-G | With the Team Analytics worker stopped, with ClickHouse stopped and with the totals database missing, the page shows its error panel, and signing in, the task list and opening and saving a job still work | `check-isolation [worker-down\|clickhouse-down\|totals-dropped]`; `check-worker` (part of `up`) for the worker itself |
| TA-H | The fork server image adds no dependency to the stock server image and carries the app; the UI image serves the page; with analytics off the server starts, no worker is rendered, no refresh is scheduled and the endpoints answer 404 | `build-server.sh` (its refusals and its analytics bundle check), `build-ui.sh`; the stack run uses both images; `check-analytics-off`, and the analytics-off render check inside `preflight` |
| TA-I | While others load uncached Team Analytics views, CVAT's own endpoints answer as fast as without them, and the views return figures within cvat-core's retries (29 s with the defaults) | `check-load` |

Seams 1 to 3 run real code with the boundaries supplied: the calculation tests
run the working tree's app in the stock server image against a throwaway ClickHouse and
a throwaway Redis (`verify/team-analytics-backend/`, run by
`verify/team_analytics_backend.sh`), and include the read path's rules with the
cache and the queue supplied and the check that the API side imports nothing
that connects to ClickHouse. The calculation suite calls the engine the way
the worker's job does, but does not run the job, the view or the queue
themselves; those are covered by the stack's checks. The logging suite supplies the cvat-core
transport; the page suite supplies the API's responses and also runs the real
boundary against a stand-in for cvat-core's request function. They do not
prove delivery through Vector, the real server's scope list, CVAT's permission
system on a running server, or layout. The stack run proves those for the
scenarios it drives: the detector record is produced by the real UI with only
the model list and the model's answer supplied in the browser, the current week
of the volume goes through the events API (older weeks are inserted directly,
since the API cannot date records back), and `run.sh check-access` runs a
removed member, an administrator by group, a personal workspace and header
credentials against the real CVAT. `run.sh check-fixes` drives each defect fix
along the path that failed. The stack does not cover a deployed model function.
The stack's own subcommands and what each judges are in its
[README](../verify/team-analytics-stack/README.md). The independent review of
the access rules is recorded with the dated evidence.

## Acceptance scenarios

| ID | Expected observable outcome | Existing evidence mechanism |
| --- | --- | --- |
| UI-A | Every stage/state retains its own count and exact segment color; legend text stays default-colored | `verify/task_progress.cjs`; browser for final appearance |
| UI-B | Multiple tasks remain isolated; unrelated/null task IDs are ignored; missing jobs form only the gray difference bucket | Same regression suite |
| UI-C | Empty page makes no jobs request; zero total and zero fetched jobs render no segments | Same regression suite |
| UI-D | Paginated job collection covers the page, and stale success/failure cannot overwrite a new query | Mocked thunk/reducer tests; live API for actual pagination |
| UI-E | Failed summary fetch preserves task display and the upstream progress fallback | Mocked failure tests; browser for complete task-item fallback |
| IAM-A | Unassigned organization members with at least the `worker` global role can act on issues/comments and list the organization's resources; below the floor the result is stock's | `verify/opa_issues_test.rego` through `verify/policy_test.sh`; upstream's generated policy tests with the added configuration rows; the stack's issue and comment matrix (`run.sh check-issues`) |
| IAM-B | Nonmembers, removed members, other organizations and sandbox/context mismatches do not gain access from the patch | Same policy suites; the stack's matrix for a nonmember, another organization's member, each organization's members on the other's issue, the personal workspace and an account with no global role. A removed member is covered by the policy suites only |
| IAM-C | Sandbox behavior and upstream filter shape remain compatible with the target release | Stock-versus-patched policy suite with the release's helpers; upstream's generated suite on the merged tree |
| IAM-D | Only administrators create organizations: an account with the `user` or `worker` role, and an organization's owner or maintainer, is refused with 403 and nothing is created; an administrator creates one | The stack's `run.sh check-org-creation` (part of `up`) against the real API |
| BUILD-A | Built image serves the changed UI without stale bundles/source maps; the backend runs the fork server image, which differs from the stock release only in the copied fork files | Image inspection and browser verification; `build-server.sh`'s refusals and bundle checks, and the dated comparison of the fork and stock images (`docs/evidence/2026-11-14-fork-server-image.md`, made when the image carried only the two policies) for the content; the stack's render check for the backend image name only |
| BUILD-B | Both served policy files equal the tree's, each by itself, and real requests exhibit the patched behavior | `verify/policy_bundle.sh` on the image, `run.sh check-policies` on the served bundle, and `run.sh check-issues`; not marker presence alone |

The frontend suite executes real TypeScript, Redux and server-rendered React
with mocked boundaries. Its optional `BROWSER_BIN` check renders the real summary
component with Ant Design styles and the task-card stylesheet in Chrome/Chromium,
checking that annotation/new text has readable contrast above its default gray bar.
It does not exercise the full `getTasksAsync` dispatch path, task-item/container
wiring, complete page layout or a live server. Policy tests evaluate synthetic
inputs using upstream helper rules; they do not prove bundle delivery or
Django/API integration.

The live checks run on the test stack (`verify/team-analytics-stack/`), each
judging its own outcome. The issue and comment matrix runs every row through
the real API with real accounts, one of them with no global role, against the
fork server image; the stock column is checked against the policy engine only
(`run.sh check-issue-policies stock`, run by every `up`), not against a running
stock server. The removed Compose launcher (`verify/opa_issues.sh`) ran the
matrix against a live stock server and then a patched one; the stack runs only
the fork server image, so the stock column's live run is gone: the stock
decisions are shown by the policy engine with inputs `issue_matrix.py` builds
as the server would send them, and not by a real stock server. The
task progress check creates a job in every stage and state and checks the
legend, segments, colours and total in a browser on the stack's UI image.

Upstream's own Django and REST suites are not part of the fork's checks. Its
REST test for issues (`tests/python/rest_api/test_issues.py`) encodes the
stock issue policy and disagrees with IAM-1.

### The test stack on a shared machine and in a public repository

The stack's namespace is `cvat-ta-it-<TA_RUN_ID>`, and `TA_RUN_ID` defaults to
the machine user. Every checkout of the same user therefore shares one stack:
one namespace, one state directory and one port-forward, and the ownership
label is the same for all of them. An `up` from a second checkout upgrades the
first one's release and its `down` deletes it. Give each concurrent run its own
`TA_RUN_ID` (and its own reserved host port). `down` refuses a namespace
without the label and stops only its own port-forward.

Before anything is applied, the launcher's render check (`render_guard.py`,
listed in the stack's README) judges every object. These ways of reaching
another project on the shared cluster through storage or routes are judged by
allowlist, against what the genuine render contains: pod volume sources,
claims naming a volume, any Ingress (the stack has none; its address is the
proxy behind a port-forward), hand-written Endpoints or EndpointSlices, and
Secret types. With analytics on it also requires the Team Analytics worker,
and with analytics off refuses it. Not judged: a
claim, or a claim template, that binds an existing volume without naming it
(a label selector, a data source, or an empty storage class); the genuine
render has none. The checks for
reaching the host still refuse by list. It judges the `helm template` render,
not what the installation creates.

The cluster's sweeper drops a namespace at its age limit or when it was created
before the cluster's last restart. The launcher recreates a namespace older
than `TA_MAX_REUSE_HOURS`, and one created before the restart time the
sweeper's last tick recorded (`infra-janitor/last-run`, `restart_at`). That
time can lag a restart by one tick, and k8s-infra does not yet count the
sweeper's restart detection as proven; without a readable time only the age
rule applies.

The repository is public. What it shows about the stack, none of it a secret
of a running system: the default of the disposable seed password
(`stack.env`); upstream's default database and cache passwords in the chart's
`helm-chart/values.yaml`; and, in evidence dated before 2026-11-15, the
stack's former default namespace and Ingress host, which carry the machine
user's name; and a machine
path outside the home directory in `INFRA_MIGRATION.md`, the platform's own
notice text. Older evidence is not rewritten. The seed password
reaches the backend pod through the seed script's standard input, not a
command line. One more of upstream's chart defaults matters for a real
deployment, not for the stack (read in the chart's values and in CVAT's
analytics policy, not tried): with analytics enabled, the chart's Grafana
gives every visitor the Admin role without a sign-in. The stack reaches it
only through the loopback port-forward, after CVAT's own analytics access
check, but any pod in the cluster can reach its Service directly. The check
pipeline's output is not redacted: a failing hook prints absolute paths, so
its output must not be pasted into evidence.

Upstream's Kubernetes test mode flushes databases in whatever namespace the
current kube context names; it is not run against a shared cluster.

## Changes that do not need reimplementation

The fork carries no ClickHouse change: `components/analytics/clickhouse/init.py`
is upstream's, and `build-server.sh` refuses to build when it differs from the
release. Earlier submodule, patch-series, filtered-import and custom-Dockerfile
workflows have been replaced by the merge of upstream releases and upstream's
own Dockerfile build of the UI. The old HTML head fix is absent from the current
baseline diff, and upstream Google Fonts links are retained. Reapply current
behavior, not every historical commit.

Live verification runs only on the Kubernetes test stack; the earlier Compose
overlay, its launchers and the copied policies are gone. Upstream's Compose
files arrive with the tree and are left as they are; they do not start the
Team Analytics worker.
[`INFRA_MIGRATION.md`](../INFRA_MIGRATION.md) records that outcome and what is
still needed before the notice can be deleted.
