# 10: Task progress checked on the stack

**What to build:** The task-progress summary on the tasks list is checked on the Kubernetes stack. Its live check existed only as a Compose launcher, which no longer runs. See "Stack and removals" in the spec (`../spec.md`).

**Blocked by:** 08 (The stack runs on the fork server image and the in-tree chart).

**Status:** ready-for-agent

- [ ] The stack seeds tasks that cover every job stage and state, as the Compose seed did.
- [ ] The browser check of the tasks list runs against the stack with the fork's UI image and passes.
- [x] What the Compose launcher prepared and checked is listed in this ticket beside what the stack now does; nothing it covered is dropped.
- [ ] The check is part of the launcher's run and is judged pass or fail.
- [ ] The result is kept in a dated evidence file.

## Compose launcher beside the stack

The Compose side is read from `verify/run.sh`, `verify/docker-compose.verify.yml`,
`verify/mkimg.py`, `verify/seed.py` and the browser test of `verify/task_progress.cjs`. The
stack side is `verify/team-analytics-stack/run.sh check-task-progress` (`check_task_progress`,
`task_progress.py`, `task_progress_browser.cjs`).

| Compose launcher | Stack |
| --- | --- |
| Compose project `cvat-verify` on the imported `docker-compose.yml`, with its own container names | Namespace `cvat-ta-it-<run id>` with the chart from the import (`up`, ticket 08) |
| Stock server image of the Compose file | Fork server image `TA_SERVER_IMAGE` |
| UI image `cvat/ui:v2.82.0-progress-colors` | `TA_UI_IMAGE` (`build-ui.sh` from the checkout under test). `check_task_progress` refuses to run unless the frontend deployment runs it |
| Traefik published on host ports 8181 (and 8191) | `kubectl port-forward` to the proxy on `TA_HOST_PORT` (8490, reserved), from `stack.env` |
| Wait until `/api/server/about` stops answering 502 | `wait_ready`, and `start_port_forward` waiting for `/api/server/about` |
| Superuser `admin` / `verify-pass-123` made with `createsuperuser` | `ta-admin` from `accounts.json`, made by `seed_users.py` with `TA_SEED_PASSWORD` and read back by `stack_api.py seed` |
| `mkimg.py`: six 64x64 PNGs in a temporary directory, removed afterwards | 13 PNGs of 8x8 made in memory by `task_progress.py`; no temporary directory |
| `seed.py` signs in with a token | Session and CSRF sign-in, as the UI does (`stack_api.Session`) |
| Task "mixed stages": segment size 1, six images, label `object`, `image_quality` 70, `sorting_method` lexicographical | The same settings, with 12 images (12 jobs) |
| Waits for the data request to finish or fail (and goes on if it failed) | Waits until the expected number of jobs exists; fails after 4 minutes |
| Six jobs PATCHed: annotation/new, annotation/in progress, annotation/completed, validation/in progress, acceptance/completed, validation/rejected. These cover every stage and every state, not every pair | All 12 stage/state pairs, which include those six. The set is checked against the server's schema (`JobStage`, `OperationStatus`) before seeding. Every job is read back and compared |
| Task "single job": segment size 6, one image, one annotation/new job | The same (segment size 6, one image), read back as annotation/new |
| Personal workspace of the superuser | Personal workspace of `ta-admin`, an administrator by group. Checked: each task's `organization_id` is null |
| Printed the tasks URL and credentials for a person to look at; no automatic check of the deployed page | The tasks list is opened in headless Chrome as `ta-admin`, filtered to the two task ids, and judged by the checks below |
| `task_progress.cjs` browser test (with `BROWSER_BIN`), on a local fixture of the component with the compiled stylesheet: text `• 1 annotation / new`, card background `rgb(255, 255, 255)`, bar `rgb(193, 193, 193)`, legend contrast at least 4.5:1 | The same four checks on the served page, on the single-job card. On the mixed card: each of the 12 legend entries with its count, each segment's computed colour from the UI-2 table, its flex weight and tooltip, the total, no "not available" bucket, no upstream fallback labels, and contrast at least 4.5:1 for every entry. `task_progress.cjs` itself stays and is unchanged |
| `run.sh down`: `docker compose down -v` | `run.sh down` deletes the namespace |

Nothing the Compose launcher prepared or checked is left out. Neither side covers a
"not available" bucket on a live page (a viewer who sees only part of a task's jobs). The
node suite covers it with the API mocked.

## Comments

- 2026-11-14, part one. Added: the seed `verify/team-analytics-stack/task_progress.py`, the
  browser check `verify/team-analytics-stack/task_progress_browser.cjs`, and
  `check_task_progress` in `run.sh`. That function has its own subcommand
  `check-task-progress` and is called from `up` after `check_tracer`. The README bullet is
  added too. No stack was running, so criteria 1, 2, 4 and 5 are not shown. The function is
  wired into `up` and exits non-zero on any mismatch, but neither has run against a stack.
  The offline checks are in `docs/evidence/2026-11-14-task-progress-on-stack.md`. Where the
  list of stages and states comes from: `StageChoice`/`StateChoice` in the v2.82.0 server
  images match `cvat-core`'s enums, and the seed checks the schema at run time. Same file.
- 2026-11-14, part two, outstanding. It needs a running stack with `TA_UI_IMAGE` built from
  the branch under test.
  1. `run.sh up` (or `cycle`). The log must show, in this order: `task progress: UI image
     <tag> (local sha256:…; running …)`, where the two IDs agree; `server schema: stages ['annotation', 'validation', 'acceptance'],
     states ['new', 'in progress', 'completed', 'rejected']`; `task N: 12 jobs, one in each
     stage/state, read back`; `task M: 1 job, annotation/new, read back`;
     `task N: 12 buckets as specified, total 12; …` and `task M: 1 buckets as specified,
     total 1; …`, each with a lowest contrast of at least 4.5:1; `task progress check
     passed`. Then `up` must finish with `check_final` passing, which shows that the
     `ta-admin` session moved no figure the final run pins. This shows criteria 1, 2 and 4.
  2. `run.sh check-task-progress` on the same stack. It must pass with two new task ids.
  3. `TA_UI_IMAGE=<another local tag> run.sh check-task-progress`. It must stop with "the
     frontend runs …" and a non-zero exit (the fail side of criterion 4).
  4. One of those runs with `TA_SCREENSHOT_DIR` set, to keep `task-progress-list.png`.
  5. Write the log lines, the task ids, the UI image ID and the lowest contrast per card into
     the evidence file's part two (criterion 5). Then ticket 12 may remove the Compose files.
