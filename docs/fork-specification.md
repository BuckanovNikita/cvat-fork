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
