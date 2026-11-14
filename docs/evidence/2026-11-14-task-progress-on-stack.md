# Task progress checked on the test stack, 2026-11-14

Ticket 10 of the defect fixes (plan row 1.3c). The task-progress summary on the tasks list
was checked live only by the Compose launcher (`verify/run.sh`), which no longer runs. The
test stack now seeds the tasks and checks the tasks list in a browser:
`verify/team-analytics-stack/run.sh check-task-progress`, also called from `up` after
`check_tracer`.

This file holds part one: what was checked without a running stack. No `up`, `cycle` or
`seed` ran. No namespace was created, no release installed, no image built or pulled, and no
browser was pointed at a server. Part two, the live run, is listed at the end and has not run.

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
  is `TA_UI_IMAGE`, logs that image's local ID, runs the seed into
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
  seed compares both enums with its own lists at run time. A stage or state added by a later
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
  legend (1.80:1) and a wrong segment palette. The script lives outside the repository and
  is not a test.
- The seed's requests were read against v2.82.0 in the fork server image:
  - `POST /api/tasks` with `labels` and `segment_size`;
  - `POST /api/tasks/{id}/data` as multipart `client_files[i]`, with `image_quality` and
    `sorting_method`;
  - `GET /api/jobs` filtered by `task_id`, and `PATCH /api/jobs/{id}` with
    `stage`/`state` (`JobWriteSerializer`);
  - `organization_id` and `jobs.count` in `TaskReadSerializer`;
  - task `filter` on `id` (`TaskViewSet.filter_fields`);
  - for an admin, sandbox tasks are filtered to no organization (`add_organization_filter`).
- In the UI, `useResourceQuery` reads `filter` from the URL into the tasks query. The task
  card shows `#<id>: ` in `.cvat-item-task-id`. The frontend deployment is
  `<release>-frontend`, with one container whose image is `cvat.frontend.image:tag`.
- `node --test verify/task_progress.cjs`: 20 pass, 1 skipped (the optional browser check,
  without `BROWSER_BIN`), as before. The suite is unchanged.

## Unverified until part two

None of these has been seen:

- the seed against a running server, including the schema read, the PATCHes and the
  read-back;
- the tasks list in Chrome with the fork UI image;
- the colours and the white card as the real stylesheet computes them;
- the call from `up`.

## Part two (live, not run)

On a stack brought up from an empty namespace, with `TA_UI_IMAGE` built from the branch
under test:

1. `run.sh up` (or `cycle`). The log must show `task progress: UI image …` with the image ID,
   then `server schema: stages [...], states [...]`. Then the mixed task with 12 jobs read
   back and the single task, then one line per task card, then `task progress check passed`.
   `up` must go on to `check_final`.
2. `run.sh check-task-progress` again on the same stack. It must pass with two new task ids.
3. A failure seen once: rerun `check-task-progress` with `TA_UI_IMAGE` set to a tag other
   than the deployed one. It must stop on "the frontend runs …" with a non-zero exit.
4. `TA_SCREENSHOT_DIR` set on one of those runs, to keep `task-progress-list.png` beside the
   log.
5. Record here the log lines, the task ids, the UI image ID and the lowest contrast per card.
