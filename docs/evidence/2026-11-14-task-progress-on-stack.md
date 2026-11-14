# Task progress checked on the test stack, 2026-11-14

Ticket 10 of the defect fixes (plan row 1.3c). The task-progress summary on the tasks list
was checked live only by the Compose launcher (`verify/run.sh`), which no longer runs. The
test stack now seeds the tasks and checks the tasks list in a browser:
`verify/team-analytics-stack/run.sh check-task-progress`, also called from `up` after
`check_tracer`.

Part one (2026-11-14) is what was checked without a running stack. In it no `up`, `cycle` or
`seed` ran, no namespace was created, no release installed, no image built or pulled, and no
browser was pointed at a server. Part two (2026-11-15), the live outcome, is at the end.

## What was added

- `task_progress.py seed`. It signs in as `ta-admin`, an account from `accounts.json`, and
  works in that account's personal workspace (`?org=`). First it reads the job stages and
  states from the server's OpenAPI schema and refuses to go on unless they are exactly the
  three stages and four states the check covers. Then it creates two new tasks:
  - "mixed stages": segment size 1 and 12 images, so 12 jobs, PATCHed to the 12 stage/state
    pairs;
  - "single job": one image and one annotation/new job.

  It reads every job back through `/api/jobs` and checks each task's `jobs.count`. Then it
  prints the task ids and their expected jobs as JSON.
- `task_progress_browser.cjs FILE` drives headless Chrome with the helpers from
  `browser_check.cjs`. It signs in as `ta-admin` through the login form, with no current
  organization set. Then it opens `/tasks?filter=` with a JSON-logic filter on the two task
  ids. On each card it checks:
  - the legend entries, in order, with their counts;
  - each segment's computed colour against the UI-2 table of the fork specification (written
    out in the script, not taken from the product's palette), its flex weight and its
    tooltip;
  - the total;
  - that there is no "not available" bucket and none of the upstream fallback labels;
  - a white card;
  - a contrast of at least 4.5:1 for every legend entry, with its colour composited onto the
    card. On the single job this is the case from
    `2026-11-13-task-legend-verification.md`.
- `check_task_progress` in `run.sh`. It refuses to run unless the frontend deployment's image
  is `TA_UI_IMAGE`. It logs that tag's local image ID and the image ID the frontend pod runs,
  then runs the seed into
  `$STATE_DIR/task-progress.json`, then runs the browser script. Any mismatch exits non-zero.
  It also has its own subcommand and a usage line in the header of `run.sh`.
- The README (Russian) gains a bullet for the check and the subcommand in its list.

Each run creates new tasks, so the check can be repeated on a reused stack. Personal-workspace
tasks of `ta-admin` touch no organization's figures. Their server events (task creation, data,
job updates) are not among the scopes the service counts: `send:working_time` and client
events in jobs (`team-analytics/service/sql/refresh/`).

## How the list of stages and states is known to be complete for v2.82.0

- `cvat/cvat-core/src/enums.ts`: `JobStage` has annotation, validation and acceptance;
  `JobState` has new, in progress, completed and rejected.
- The server's `cvat/apps/engine/models.py` (`/opt/cvat/cvat/apps/engine/` in the image) has
  the same members in `StageChoice` and `StateChoice`. Read in the stock image
  `cvat/server:v2.82.0` (`sha256:e4ff37f1b598…`) and in the fork server image
  `cvat/server:v2.82.0-fork-policies` (`sha256:4b38c649ae96…`), which the stack runs. Each
  was read by a one-off `--network none --cpus=1` container running `grep`.
- `JobWriteSerializer.update` in that image takes `stage` and `state` together in one PATCH.
  For every stage and state it sets only the derived `status`, so all 12 pairs can be set.
- The server's schema names the two enums `JobStage` and `OperationStatus`
  (`ENUM_NAME_OVERRIDES` in `cvat/settings/base.py`). `/api/schema/` has no permission
  classes and serves `application/vnd.oai.openapi+json` through `OpenApiJsonRenderer`. The
  image's generated `cvat/schema.yml` has `JobStage` (annotation, validation, acceptance) and
  `OperationStatus` (new, in progress, completed, rejected) in that order. The seed compares both enums with its own lists at run time. A stage or state added by a later
  upstream release fails the seed before the check runs.

## Checks with supplied boundaries

- `bash -n verify/team-analytics-stack/run.sh`: passes. `run.sh` with no argument prints the
  usage text with the new line.
- `task_progress.py` byte-compiles. Imported with a dummy `TA_BASE_URL`: the plan is 12
  distinct pairs, and the image shades for 12 and for 1 image are all within a byte (the
  shared `upload_images` of `stack_api.py` overflows above four images, so the seed has its
  own upload).
- `node --check task_progress_browser.cjs`: passes.
- The card reader and the card check ran in jsdom, against the markup of the real
  `TaskJobsProgress` component for both seeded tasks. This is a mocked boundary: no
  stylesheet, inline card background, and a stand-in default text colour. That markup was
  accepted. Six altered inputs were each refused with their own message: a missing card, a
  "not available" bucket, a wrong expected job count, the fallback labels, a coloured
  legend (1.80:1) and a wrong segment palette. The script was a throwaway outside the
  repository and was removed afterwards; it is not a test.
- `seed()` ran against a canned fake of the API, also a throwaway outside the repository.
  The fake replaced `Session` and the upload, and served the schema through the session's
  opener. Its first jobs poll returned no jobs. Every request had to name the personal
  workspace. The seed printed JSON for 12 jobs and for 1 job. It was refused when the schema
  had an extra state and when one job read back with the wrong state. This run found that
  the seed waited for `images // segment_size` jobs, which is 0 for the single-job task, so
  that task would always have failed live. It now waits for the ceiling of that division.
- The seed's requests were read against v2.82.0 in the fork server image:
  - `POST /api/tasks` with `labels` and `segment_size`;
  - `POST /api/tasks/{id}/data` as multipart `client_files[i]`, with `image_quality` and
    `sorting_method`;
  - `GET /api/jobs` filtered by `task_id`, and `PATCH /api/jobs/{id}` with
    `stage`/`state` (`JobWriteSerializer`);
  - `organization_id` and `jobs.count` in `TaskReadSerializer`;
  - task `filter` on `id` (`TaskViewSet.filter_fields`), with the `or` and `==` operators
    that `apps/engine/filters.py` accepts;
  - an empty `org=` sets `organization_specified` with no organization
    (`apps/iam/middleware.py`), that is the personal workspace. For an admin, sandbox tasks
    are then filtered to no organization (`add_organization_filter`).
- In the UI, `useResourceQuery` reads `filter` from the URL into the tasks query. The task
  card shows `#<id>: ` in `.cvat-item-task-id`. The frontend deployment is
  `<release>-frontend`, with one container whose image is `cvat.frontend.image:tag`.
- `node --test verify/task_progress.cjs`: 20 pass, 1 skipped (the optional browser check,
  without `BROWSER_BIN`), as before. The suite is unchanged.

## Unverified at the end of part one

Not seen until part two, which now covers each of them:

- the seed against a running server, including the schema read, the PATCHes and the
  read-back;
- the tasks list in Chrome with the fork UI image;
- the colours and the white card as the real stylesheet computes them;
- the call from `up`.

## Part two as planned in part one

On a stack brought up from an empty namespace, with `TA_UI_IMAGE` built from the branch
under test:

1. `run.sh up` (or `cycle`). The log must show `task progress: UI image …` with the local
   image ID and the frontend pod's running image ID, which must be the same. Then
   `server schema: stages [...], states [...]`. Then the mixed task with 12 jobs read back
   and the single task, then one line per task card, then `task progress check passed`. `up`
   must then finish with `check_final` passing. That shows the `ta-admin` session moved no
   figure the final run pins.
2. `run.sh check-task-progress` again on the same stack. It must pass with two new task ids.
3. A failure seen once: rerun `check-task-progress` with `TA_UI_IMAGE` set to a tag other
   than the deployed one. It must stop on "the frontend runs …" with a non-zero exit.
4. `TA_SCREENSHOT_DIR` set on one of those runs, to keep `task-progress-list.png` beside the
   log.
5. Record here the log lines, the task ids, the UI image ID and the lowest contrast per card.

## Part two: live outcome, 2026-11-15

The stack ran in namespace `cvat-ta-it-<user>` on `docker-desktop`, reached at
`http://localhost:8490`. Its images were built from `3dc1a7bc`: UI
`cvat/ui:v2.82.0-team-analytics` (`sha256:310e9bbc6a47…`), server
`cvat/server:v2.82.0-fork-policies` (`sha256:4b38c649ae96…`) and service `42d4bb9ab97e`.
Ticket 08 brought the stack up. Tickets 09 and 11 ran their own checks on it at the same
time. This ticket ran only `run.sh check-task-progress` and `run.sh status`, from branch
`ticket/10-task-progress` at `2bd0d1b8`, through the heavy lock. Logs are kept in the shared
notes directory outside the repository.

### The call from `up`: another ticket's run

Ticket 08's second `up` on this stack ran every check in order and exited 0. It is ticket
08's run, not this ticket's; its evidence is
`2026-11-14-stack-fork-image-in-tree-chart.md`. Its log shows this check between
`check_tracer` and `check_final`:

```
[ta-stack] task progress: UI image cvat/ui:v2.82.0-team-analytics (local sha256:310e9bbc6a4726e29ae9bc9d76b132af4987abf5570a600b96aa8585a2596178; running docker-pullable://cvat/ui@sha256:310e9bbc6a4726e29ae9bc9d76b132af4987abf5570a600b96aa8585a2596178)
  server schema: stages ['annotation', 'validation', 'acceptance'], states ['new', 'in progress', 'completed', 'rejected']
  task 14: 12 jobs, one in each stage/state, read back
  task 15: 1 job, annotation/new, read back
  task 14: 12 buckets as specified, total 12; legend rgba(0, 0, 0, 0.88), lowest contrast 16.56:1
  task 15: 1 buckets as specified, total 1; legend rgba(0, 0, 0, 0.88), lowest contrast 16.56:1
  ta-admin: the tasks list shows the progress of tasks 14,15 as specified
[ta-stack] task progress check passed
[ta-stack] final run: synthetic volume in ta-org-v (history fills while the browser works)
...
[ta-stack] final run passed
```

The same log goes on through the issue matrix and the access cases and ends `exit 0`. So
`check_final`, which runs after this check, passed with the `ta-admin` tasks and browser
session already in place.

### This ticket's runs

1. `run.sh check-task-progress`, with `TA_SCREENSHOT_DIR` set: exit 0, two new tasks.

   ```
   [ta-stack] task progress: UI image cvat/ui:v2.82.0-team-analytics (local sha256:310e9bbc6a4726e29ae9bc9d76b132af4987abf5570a600b96aa8585a2596178; running docker-pullable://cvat/ui@sha256:310e9bbc6a4726e29ae9bc9d76b132af4987abf5570a600b96aa8585a2596178)
     server schema: stages ['annotation', 'validation', 'acceptance'], states ['new', 'in progress', 'completed', 'rejected']
     task 22: 12 jobs, one in each stage/state, read back
     task 23: 1 job, annotation/new, read back
     task 22: 12 buckets as specified, total 12; legend rgba(0, 0, 0, 0.88), lowest contrast 16.56:1
     task 23: 1 buckets as specified, total 1; legend rgba(0, 0, 0, 0.88), lowest contrast 16.56:1
     ta-admin: the tasks list shows the progress of tasks 22,23 as specified
   [ta-stack] task progress check passed
   ```

   The local image ID of the tag and the image ID the frontend pod runs are the same. The
   lowest legend contrast is 16.56:1 on both cards. That is the value the 2026-11-13
   fixture check computed for the fixed legend; here the stylesheet is the served one.
2. `TA_UI_IMAGE=cvat/ui:v2.82.0-progress-colors-readable-text-001eb38 run.sh
   check-task-progress`, a local tag that is not the deployed one: exit 1, before any task
   was created.

   ```
   [ta-stack] error: the frontend runs 'cvat/ui:v2.82.0-team-analytics', not the UI image under test cvat/ui:v2.82.0-progress-colors-readable-text-001eb38
   ```

### What the screenshot shows beyond the checks

`task-progress-list.png` of run 1 (kept with the logs, not committed) shows both cards in
the filtered list, signed in as `ta-admin`. The single-job card reads
`• 1 annotation / new • 1 total` above a full-width gray bar.

On the 12-job card, the legend wraps onto seven lines. Its last line (`• 1 acceptance /
rejected • 12 total`) extends below the card's lower edge, and the bar is not visible in the
card. The check reads the segments' computed styles, not whether they are on screen, so it
passes. This is the UI's layout with twelve nonzero buckets on a 1400-pixel-wide window. It
is recorded here and not asserted, and nothing was changed for it in this ticket.

### What stays unverified

- A "not available" bucket on a live page (a viewer who sees only some of a task's jobs).
  Neither the Compose launcher nor the stack covers it. The node suite covers it with the API
  mocked.
- `up` from an empty namespace with this check, run by this ticket itself. The call from
  `up` was seen in ticket 08's run on a stack that already existed.
