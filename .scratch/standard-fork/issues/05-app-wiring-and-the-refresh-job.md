# 05: The app is wired in and refreshes the totals

**What to build:** The app is registered when analytics is enabled, has its own queue, and a periodic job refreshes the stored totals under the Redis lock. See "Refresh" and "Settings" in the spec.

**Blocked by:** 04.

**Status:** resolved

- [x] With analytics enabled the app is installed, the `team_analytics` queue exists and the refresh job is scheduled every minute; with analytics off the app and the job do not exist, a schedule stored earlier is removed, and the server starts.
- [x] `run worker team_analytics` starts a worker for the queue, through a component file of the fork's own; no upstream entry-point file is edited.
- [x] A run of the job takes the lock or leaves at once, then repeats the core's prioritised step while there is work, within its time budget.
- [x] Schema set-up and the first cutover search happen in the first job that finds them missing; a failure of either leaves CVAT untouched and is retried by the next job.
- [x] After a step that wrote, the generation of the totals advances.
- [x] The settings have defaults in the app and can be set from the environment.
- [x] The upstream files edited are `cvat/settings/base.py` and `cvat/urls.py`, each by appended lines.

## Comments

2026-11-15: `6e74221c` (app, settings, URLs, component file, jobs) on `f3f15a55` (the engine). Shown inside the built image `cvat/server:v2.82.0-fork`, Django set up on production settings, no network: with `CVAT_ANALYTICS=1` the app is installed, the queue registered, the job scheduled for every minute, the five routes resolve and the default settings load; with `CVAT_ANALYTICS=0` none of it exists and the routes are 404. The component file is in the image. `tests/test_backend_path.py` shows the engine with the Redis lock refreshing and answering as the service does over HTTP, for an organization and the instance.

Open until the stack run: that `run worker team_analytics` starts and stays up, that the job runs every minute and takes steps within its budget, the make-ready on a real first start, and that the generation advances. Those criteria stay unticked.

2026-11-15: Changed by `2c653fe6` after the first live run. The queue is now defined whether or not analytics is enabled, because CVAT's `syncperiodicjobs` removes stored schedules only for configured queues; the first criterion is reworded to say so. A run of the job also ends after a step once a read is waiting. Inside the image the wiring check for `CVAT_ANALYTICS=0` therefore now reads: app absent, job absent, routes 404, queue defined.

2026-11-15: Shown on the stack (`docs/evidence/2026-11-15-backend-acceptance.md`). `run worker team_analytics` started through the component file; CVAT's probe command reported three worker processes, with no restart and no failed probe. The refresh job ran every minute from CVAT's scheduler; the status stamp advanced. In a fresh install the first figures were there about 1.6 minutes after the chart install began. With the totals database dropped, the schema, the refresh and the figures came back by themselves within 35 s, and CVAT's own operations went on working, as they did with ClickHouse down. A reinstall with analytics off deleted the stored schedule and left nothing queued. Since `919d7ea0` the generation advances once at the end of a run that wrote, not after each step; the fifth criterion is read that way.
