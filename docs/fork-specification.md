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
| Organization issues/comments | `cvat/cvat/apps/engine/rules/issues.rego`, `cvat/cvat/apps/engine/rules/comments.rego` (patched in place inside the import) | Broader actions and listing for members of the resource organization who hold at least the `worker` global role |
| Build and deployment | `build-ui.sh`, `build-server.sh`, `Dockerfile.server` | Custom UI image, and the fork server image that delivers the patched policies (BUILD-1) |
| Verification | `verify/` | Frontend regression tests, the policy test and the policy bundle check, the Team Analytics seams, and the test stack on Kubernetes (`verify/team-analytics-stack/`) that runs the live checks |
| Mechanical formatting | `ruff.toml` | Formatting convention for the fork's own Python. It is not applied inside the import: `cvat/components/analytics/clickhouse/init.py` equals upstream's file |
| Team Analytics | `team-analytics/`, `build-team-analytics-service.sh`, the page and logging directories under `cvat/cvat-ui/src/`, wiring in eleven UI files (TA-1) | Work figures per annotator and project from CVAT's own events, read by a separate service |

The authoritative import path selection is `PATHS` in `mirror-cvat.sh`.
`tools/git-filter-repo` is vendored tooling, not a place for fork policy.
The filtered tree omits the Python backend. It carries four of its OPA policies:
the issue and comment policies, which the fork patches in place, and their
helpers `cvat/cvat/apps/iam/rules/utils.rego` and
`cvat/cvat/apps/organizations/rules/organizations.rego`, kept stock. The policy
test, `verify/policy_test.sh`, reads them from the import.

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

Each of the two policies in the import carries the same two additions to the
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

The patched files reach a server only inside the fork server image (BUILD-1);
nothing mounts them, and there is no second copy of them. Because the added
rule has no scope whitelist, any scope a later upstream release adds to either
policy is granted to members at or above the floor as soon as the policies are
merged with that release. The upgrade procedure has the review step.

## BUILD-1: Packaging and policy delivery

The fork ships three images, each built by a script in this repository from the
working tree. None of them is pulled from a registry; each must be present on
the node that runs it.

| Image | Built by | Content |
| --- | --- | --- |
| UI | `build-ui.sh` | Upstream `cvat/Dockerfile.ui` with the fork's UI changes |
| Fork server image | `build-server.sh`, `Dockerfile.server` | The stock release server image with the import's two patched policies copied over the stock ones ([ADR 0004](adr/0004-a-fork-server-image-that-adds-only-the-patched-policies.md)) |
| Team Analytics service | `build-team-analytics-service.sh`, `team-analytics/Dockerfile` | The stock release server image with the service code and SQL (TA-1) |

`build-ui.sh` compiles the frontend inside upstream `cvat/Dockerfile.ui`. Preserve
its selected Node image override through the named BuildKit context, disabled
source maps, and removal of stale local `cvat-ui/dist` output before building.
The script's `IMAGE` and `NODE_IMAGE` variables are supported overrides;
`SAVE=1` additionally exports a compressed image archive, while the default
only builds the image. Consult the script for current defaults.

The fork server image is the stock release image named by `BASE_IMAGE`, with
`issues.rego` and `comments.rego` from `cvat/cvat/apps/engine/rules/` copied
over the stock files at `/opt/cvat/cvat/apps/engine/rules/`, with the stock
files' owner and mode, and nothing else: no package, no Python change, no
configuration change. That directory of the import is the whole build context.
`build-server.sh` never pulls or pushes: the stock base must already be local,
and the build runs without network. `IMAGE`, `BASE_IMAGE` and `STOCK_TAG` (the
import tag, which must be local) are its supported overrides; it refuses an
`IMAGE` equal to `BASE_IMAGE`, so the stock tag is never overwritten. It builds
the image untagged and tags it `IMAGE` only after two checks with the server's
own bundle builder: the built image's bundle holds the import's two patched
policies, and the base image's bundle holds the four policy files the import
carries exactly as `STOCK_TAG` has them, so a base of another release is
refused. If either fails, no image is left under `IMAGE` (an earlier image under
that tag is removed as well) and nothing is saved. `SAVE=1` additionally
exports a compressed image archive, after the checks.

The chart has one backend image setting, so the server, every worker and the
initializer run the fork server image. The custom UI suffix is never a backend
tag, and the Team Analytics service keeps its own image on the stock base, so a
change to analytics code never rolls out the CVAT backend.

The policies are patched in place inside the import (IAM-1). The server packages
the bundle it serves at `/api/auth/rules` from its installed rules directory, so
the copy must land in the directory the server builds that bundle from. Upstream
moved the installed sources from `/home/django` to `/opt/cvat` in 2.72.0; a copy
to a directory the server does not read raises no error in the build itself and
leaves the stock policies in force. The bundle check finds that, and
`build-server.sh` runs it before it tags the image:
`verify/policy_bundle.sh from-image IMAGE` builds the bundle with the server's
own builder in a one-off container of the image, without network, and
`verify/policy_bundle.sh check` compares each of the two policies in a bundle
given on stdin, by itself and byte for byte, with the import's file (with
`check <tag>`, with the file at that import tag; `check-stock <tag>` compares
the four policy files). It first refuses a bundle with two entries of one name,
which the server builds when a policy exists in two registered rules
directories, and a compared policy that is not a regular file. The test stack
applies the same check to the bundle the running server serves
(`run.sh check-policies`) and also requires the patch marker in each policy;
its render check refuses a backend image other than the fork server image.

Rebuild the fork server image whenever a policy changes and on every upstream
upgrade, and run the backend on the rebuilt image: a running server caches the
bundle it built.

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
  failure path; a failed release is tried again. A replica that can no longer
  prove it holds the lease (its renewals failed or came back after the lease
  could have expired) stops its step before the next write, so nothing it
  computed is marked or becomes visible. A claim renewed after it expired is
  never live again. The wait for a hanging renewal at release is bounded
  (2 s). On SIGTERM the service
  finishes the step in progress and releases the lease before exiting. A
  replica killed mid-step releases nothing and holds up the others until its
  lease runs out: the lease is 120 s long and is renewed every 40 s while a
  step runs, so it runs out at most 120 s after the kill. The next replica
  takes over at its next try after that; a replica that finds the lease taken
  tries again every 5 s. Known limit: on SIGTERM the service waits at most
  25 s for the step in progress. A step still running then (a long day of
  history, or the daily check's cutover search, which may take up to its
  60 s limit) ends with the process without releasing the lease, which then
  holds the others up as a killed replica's does; a statement it had sent
  goes on in ClickHouse until it ends or reaches its limit. The signal neither
  releases the lease nor stops the statement: releasing it while the step's
  statement still runs in ClickHouse could let another replica write beside
  it, and stopping the statement would mean tracking and killing it by query
  id.
- One ClickHouse client without a session serves the HTTP threads and the
  refresh loop. The cutover search has one more client for each of its two
  limits, so two more in all: one for the search at start and one for the
  search in the daily check. Each gives up after hearing nothing from
  ClickHouse for a few seconds longer than its search's limit. A request body is read and dropped, or the
  connection is closed
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

  Each endpoint reads how far history is processed once per request, before it
  reads any figure, so a history step that finishes during a request can only
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
- Legacy rule: the cutover is the hour of the first shape-tagged operation
  event on the instance, reported by `status`. The service looks for it in
  the recorded events with one statement over the raw events: when it starts,
  before it answers; in the daily check; and in the step that first stores a
  shape-tagged hour while none is stored, before those hours become visible.
  Every hour found is stored in the totals database, and requests read the
  earliest stored hour, so the cutover moves to an earlier hour when an
  earlier shape-tagged event turns up and never to a later one. Until an hour
  is stored there is no cutover. A period that ends at or before it, or any period while there is none, is a
  legacy period (all shapes, the legacy notice, class change and hotkey use
  not recorded, saved boxes in place of Model). A period that begins at or
  after it is never legacy. A period that holds it is partly legacy: figures
  as usual, the shape switch stays, and the page names the cutover day. Trend
  buckets follow the same rule; the bucket that holds the cutover is not
  legacy. An empty period (no job work in the scope) shows only the empty
  state: no legacy notice and no partly-legacy notice.
- Known limits of the stored cutover: the service looks for it in the
  recorded events when it starts and in the daily check, and stores every hour
  it finds; the earliest stored hour is the cutover. An earlier shape-tagged
  event that arrives late therefore moves the cutover only at the next daily
  check or start, and the periods in between read as legacy until then. A
  later event never moves it. A shape-tagged event with a wrongly early date
  moves the cutover to its hour, and deleting the stored value does not undo
  that: the next search finds the same event. The correction is to remove
  that event from the `events` table, then every row of the `cutover` table
  in the totals database, and then to restart the service or wait for the
  daily check, which finds the cutover again. Until then there is no cutover
  and every period reads as legacy. The search reads the recorded events in
  time order and stops at the first shape-tagged one. Once a cutover is stored
  it finds none, so it reads every recorded event before the stored cutover;
  while none is stored it reads up to the first tagged event, or all of them
  when there is none. Its cost therefore grows with the history before the
  cutover. What it cost at the volume of the design measurements, in each of
  these cases, is in `docs/evidence/2026-11-14-cutover-search-cost.md`. The
  search at start and in the daily check runs with limits that ClickHouse
  enforces on the statement: 23 s at start, 60 s in the daily check, and
  512 MiB of memory in both. ClickHouse stops a search that reaches one; that
  is the bound. The service's client gives up only after hearing nothing for
  a few seconds longer than the limit, so it does not give up first; a client
  that gives up does not stop the statement in ClickHouse. A search that fails or
  is stopped at start lets the service start without it; in the daily check
  the step ends without it. Either way the cutover is looked for again at the
  next daily check or start, so on an instance whose history before the
  cutover takes longer than the limit to read, the search keeps failing: the
  cutover is then found only by the refresh that first stores a shape-tagged
  hour while none is stored (that search has no time limit), and a late
  earlier event never moves it.
- New measurements travel inside existing client event types (ADR 0002):
  payload fields on draw, paste, propagate, drag, resize and delete, plus three
  `debug:info` records (`team_analytics:class_change`,
  `team_analytics:model_creation`, `team_analytics:input_summary`). The names
  are fixed in `utils/team-analytics-logging/contract.ts` and in the service
  SQL. Change them together. A batch with a scope the server does not accept is
  rejected whole, so no new scope may be introduced.
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
  such press and never credits the wrong key.
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
  with the group event but were stored by a service without the group-move
  rule hold a group drag as two alignments and a selection-box move as one;
  computing them again gives one per object moved. Under that old rule the
  grabbed object's drag also keeps its object reference, so a later drag of
  the same object continues its run: a group drag of two boxes followed by a
  drag of the grabbed box is stored as 2 alignments under the old rule and 3
  under the new one.
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
  processed without it. And after each refresh that moves the window on, every
  period reads as being processed until the history step that follows has
  computed the hour that left it. The default window of 48 hours does not
  behave so: the next ten-minute refresh counts a late record, and no hour of
  today lies before the window.
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
- Known limit of the split by operation: Other is working time minus the time
  of the four operations, and is never below zero. A row whose operation time
  exceeds its working time therefore has Other at zero, and its bar is drawn
  at the row's working time with the operation parts stretched to fill it,
  in the full view and in the overview's bars by annotator and by project.
  Each part's hover gives its own hours. The overview's "where working time
  goes" reads Other with the same floor over its whole scope. For such a row the parts shown add up to more than its working
  time, while the page's definitions say of working time that every breakdown
  of time adds up to it. The rule is the service's; the owner has not been
  asked about the wording beside it. Whether to change the definition's
  wording or how such a row is shown is an open decision for the owner.
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
  The stack run's group drag (ticket 27: a group drag made in the browser and
  read back from the events table) is what catches it;
- frame changes: the shown frame changes only through `changeFrameAsync`, and
  nothing between a navigation shortcut's handler and the start of
  `changeFrameAsync` waits for a later task (the top bar's frame search and
  `searchAnnotationsAsync`'s annotation search answer in microtasks once the
  frame meta is loaded). A new path that shows a frame leaves the module's
  last shown frame stale, so the next key may be counted for a frame it did
  not move or not counted for one it did; a handler that comes to wait for a
  later task makes its key count nothing. Neither fails a suite, since the
  harness drives the top bar over supplied searches. The stack run's
  held-key step (ticket 27: a navigation key held on a slow frame, its count
  compared with CVAT's `change:frame` events) is what catches it.

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
| IAM-A | Unassigned organization members with at least the `worker` global role can act on issues/comments and list the organization's resources; below the floor the result is stock's | `verify/opa_issues_test.rego` through `verify/policy_test.sh`; the stack's issue and comment matrix (`run.sh check-issues`) |
| IAM-B | Nonmembers, removed members, other organizations and sandbox/context mismatches do not gain access from the patch | Same policy suite; the stack's matrix for a nonmember, another organization's member, each organization's members on the other's issue, the personal workspace and an account with no global role. A removed member is covered by the policy suite only |
| IAM-C | Sandbox behavior and upstream filter shape remain compatible with the target release | Stock-versus-patched policy suite with target helpers |
| BUILD-A | Built image serves the changed UI without stale bundles/source maps; the backend runs the fork server image, which differs from the stock release only in the two policies | Image inspection and browser verification; `build-server.sh`'s two bundle checks and the dated comparison of the fork and stock images (`docs/evidence/2026-11-14-fork-server-image.md`) for the content; the stack's render check for the backend image name only |
| BUILD-B | Both served policy files equal the import's, each by itself, and real requests exhibit the patched behavior | `verify/policy_bundle.sh` on the image, `run.sh check-policies` on the served bundle, and `run.sh check-issues`; not marker presence alone |

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

### The test stack on a shared machine and in a public repository

The stack's namespace is `cvat-ta-it-<TA_RUN_ID>`, and `TA_RUN_ID` defaults to
the machine user. Every checkout of the same user therefore shares one stack:
one namespace, one state directory and one port-forward, and the ownership
label is the same for all of them. An `up` from a second checkout upgrades the
first one's release and its `down` deletes it. Give each concurrent run its own
`TA_RUN_ID` (and its own reserved host port). `down` refuses a namespace
without the label and stops only its own port-forward.

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
`values.yaml`; and, in evidence dated before 2026-11-15, the default namespace
and Ingress host, which carry the machine user's name; and a machine path
outside the home directory in `INFRA_MIGRATION.md`, the platform's own notice
text. Older evidence is not rewritten. The seed password
reaches the backend pod through the seed script's standard input, not a
command line. The check pipeline's output is not redacted: a failing hook
prints absolute paths, so its output must not be pasted into evidence.

## Changes that do not need reimplementation

The remaining ClickHouse delta is formatting only. Preserve upstream semantics
when resolving it; formatting is not a product requirement. Earlier submodule,
patch-series and custom-Dockerfile workflows have been replaced by the subtree
and upstream Dockerfile build of the UI. The old HTML head fix is absent from the current
baseline diff, and upstream Google Fonts links are retained. Reapply current
behavior, not every historical commit.

Live verification runs only on the Kubernetes test stack; the earlier Compose
overlay, its launchers and the copied policies are gone.
[`INFRA_MIGRATION.md`](../INFRA_MIGRATION.md) records that outcome and what is
still needed before the notice can be deleted.
