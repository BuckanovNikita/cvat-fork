# Final run on a fresh stack, 2026-11-15

Ticket 27 of the defect fixes. The ticket is done in two parts. Part one, below, prepared
the run without a stack: the steps the launcher lacked, the fork specification's limits,
and what each criterion ticked on a reading needs before it may be ticked again. Part two,
at the end, is the run itself: images, `up`, `up`, the fix steps, the look beside the
prototype, `down`. Part one is a plan; only part two holds live outcomes. Where part two
changed a step, part two says how; the table in part one describes the plan.

The stack's namespace is written `cvat-ta-it-<user>` here; its default name carries the
machine user's name.

## Part one: what was prepared

`run.sh check-fixes [STEP]` (`fixes_run.py`, `fixes_browser.cjs`) drives each fix of the spec
along the path that failed. It is not part of `up`: browser steps that have never met a
stack may need changes, and a failure inside `up` must not cost the fresh-`up` criterion.
It runs on a stack `up` has passed on, since it needs the final run's tagged work and the
volume. Every step judges itself except `sessions-at-limit`, which records a number. The
two steps that change the stack's own state run last, and both are supplied boundaries:

| Step | Path that failed | What it does and judges |
| --- | --- | --- |
| `status-roles` | a maintainer saw the instance's first event day and day counts | `status` as `ta-maintainer` and `ta-owner` has `complete`, `percent`, `periods`, `earliest_month`, `complete_weeks`, `trends_ready` and nothing else in `history`; as `ta-admin`, with and without an organization, also `ready_from`, `ready_from_day`, `first_day`, `days_ready`, `days_total`; all carry the same `cutover` |
| `technical-project` | a project whose only work is a technical account's saved boxes had no details row | `ta-bot` saves 3 boxes through the API in a new project of `ta-org-c` that holds no job work of anyone (as the service reads job work); the details table by project (`ids` = that project) lists it with working time 0, sessions 0, annotators 0, saved boxes 3 and Model 3, under both shape choices; a search for `ta-bot` in the table by annotator finds nothing. The expected row is the one the service suite's `TechnicalAccountOnlyProjectTest` expects |
| `gestures` | a redo counted as a second creation; a group drag counted as one alignment of one object and a selection-box move as nothing; a held frame key counted repeats that moved no frame | `ta-worker-c`, in a new job of 24 frames with one frame per chunk (the chunk size read back from the task), draws a box, undoes and redoes it with the header buttons, draws two more and saves; selects those two with the selection region (Shift and a drag on the background), drags one of them, moves the selection box, clears the selection, drags one box alone, saves; holds F for 4 s (key-downs every 50 ms) with 1.5 s of network latency on every request; types the last frame into the frame field and presses F; presses the slider near its start; leaves the job. Then from the events table: one `action:undo` and one `action:redo`; exactly two `drag:object` with `group` = `move`, each `count` 2, `rectangle_count` 2, `shape_type` rectangle, `object_type` shape, `input_method` mouse, a `frame`, no `object_ref`, no `obj_id`; one with `group` = `grabbed`, `object_ref` and `obj_id`; one plain drag last, with `object_ref`; every `POST /api/events` answered 201. The summaries' `NEXT_FRAME` equals the frames the page showed during the hold, which must be fewer than the key-downs, with the highest frame shown below the last (otherwise the frame was not slow and the step fails); with no backward jump it also equals the single steps in CVAT's `change:frame` records (merged records carry their count); the press at the last frame moved nothing; the summaries' hotkeys equal what was pressed. The project's figures after one more refresh: creation 3, drawn 3, deletion 0, alignment 5 (2 + 2 + 1), hotkey actions as pressed |
| `look` | the overview lacked the split bars and the definitions | the volume organization's overview, opened without a shapes choice, has Bounding boxes pressed; at 1400 px and at 400 px both working-time cards have a legend of at least two operations and every bar in parts inside its card, with some bars in two or more parts; the definitions block has its four terms, lies below the details table and after every card, inside the page's column and the window, in several columns at 1400 px and one at 400 px; at 1400 px the page does not scroll sideways; a full view shows no definitions. Full-page screenshots go to `TA_SCREENSHOT_DIR`, outside the repository |
| `unprocessed` | a direct call for a period still being processed returned its figures | holds the refresh lease (at most 110 s; the service's claims see it taken and wait) and inserts one marker event three days before the earliest of the first event day and the first day recorded as processed (so that a rerun finds new days), which makes those days unprocessed. While held, `ta-maintainer` (with `ta-org-a`) and `ta-admin` (no organization) read: status (`complete` false, the year not offered, the week offered); overview, list, details by annotators and by projects for the year (`processed` false, every field outside the documented envelope null, the overview's `operations` with only its legacy flags); the week (processed, figures); trends by week and by month (the bucket holding the marker day not processed, every value of its points null). After release, once history is complete again, the year is processed and has figures. The marker is deleted; the three days stay recorded in `history_days`, before the first event, as the probes of 2026-11-15 left theirs |
| `sessions-at-limit` | (a count the owner asked for) | the stored sessions of the instance-wide set, each hour's newest version: how many, how many span at least a day less the session gap (every session cut at the one-day read-back is among them), the longest |
| `cutover-restart` | right after an in-place upgrade the cutover was unknown until a shape-tagged hour reached the stored totals | the expected cutover is the hour of the first tagged operation event in the events table (the condition of `control/cutover_find.sql`); the service is scaled to 0, the totals database's `cutover` table emptied and `history_today` dropped (what a totals database written before the cutover search and the short-window history holds), the service scaled to 1; the first `status` answer to `ta-admin` and to `ta-maintainer` must carry that hour; `history_today` exists again; the pod's restart count is recorded (the liveness probe during the start-up search) |

Note added later on 2026-11-15, after an independent review of the run: the table above is the
plan and is superseded by part two wherever the two differ. For `gestures` that is two
points. The held key's frames are no longer required to be fewer than its key-downs: the step
failed exactly there on the stack, every key-down moving a frame, and the requirement was
removed (`c61ec366`); the step now judges `NEXT_FRAME` against the frames shown. The drag
marked `grabbed` is allowed at most once, not required: no gesture on the stack produced it.

Also changed: `stack_api.upload_images` takes a chunk size and keeps every generated
frame's shade within a byte (24 frames went past 255 before); the stack README (Russian)
and the header of `run.sh` describe `check-fixes`.

The fork specification now states the limits the ticket lists: counts lost on tab close
(already there); tags and objects made with the interactive AI tools or OpenCV not counted
as creations; 3D jobs; session length as the SQL bounds it; a shape-tagged event with a
wrongly early date (already there). The acceptance paragraph no longer says the stack does
not cover the detector from the UI or a removed member, and the two integration-map lines
that named "ticket 27" point at `check-fixes gestures`. Nothing else in the specification
was found to describe a limit that is fixed.

Found while writing the 3D limit, from reading only: the glossary says that in 3D jobs only
sessions and working time are measured, but the stock 3D canvas logs its own draw and paste
events (and a deletion is logged as in 2D) without shape fields, and the service counts
untagged events as it counts records from before the cutover. Under All shapes, 3D work
therefore shows as drawn or pasted creations and deletions; under Bounding boxes it does
not. The specification states this; the owner has not been asked whether to keep it.

### Checks run in part one

Stated checks, not tests, all on the branch after its merge of the integration branch at
`b8521e3f` (which already holds the last review follow-up): `node --check` on the new
script; a Python compile; the control SQL of the lease rendered with literals and read;
`bash -n run.sh` and its usage text; `run.sh preflight`, which passed (the server image
check, both sides of the issue matrix against the policy engine, the chart build and the
render checks; nothing created or pulled); and `prek run --all-files`, which passed
(ESLint, stylelint, the type check, ruff, both policy tests, the three fast frontend
suites). None of the new steps has run against a stack.

## The ten criteria ticked on a reading

Named in the decisions ledger (`.scratch/standard-fork/decisions-ledger.md`, V11; the
record behind it lists them by file and line, the same lines at `dca82a3` and now). Each is
restated in its ticket as what was shown. The rule proposed for the ticks: a criterion is
ticked again only for what this run shows on the stack. Where part of it is shown only by a
suite with supplied boundaries, the line is split in two: the part the stack showed
(ticked when shown) and the part a suite shows (left unticked, saying which suite). A
criterion with no stack part stays one unticked line.

| Ticket:line | Ticked on | Must be shown before a tick | Restated as (if shown) |
| --- | --- | --- | --- |
| 04:12 supervisor, worker, non-member, removed member refused | stand-in CVAT for the removed member | `check-final` access (supervisor, worker, outsider: 403 on every endpoint) and `check-access removed-member` pass | With real accounts on the stack, a supervisor, a worker and a user who is a member of nothing get 403 on every endpoint, and a maintainer removed through CVAT's API gets 403 on the same session once the one-minute reuse has passed, with and without an organization. |
| 04:16 CVAT unreachable: refusal, not stale knowledge | stand-in only | no stack step; seam 1 only | Shown by the service suite with a stand-in CVAT that stops answering; not seen on the stack. Stays unticked. |
| 04:17 answers reused at most a minute | stand-in only | `check-access removed-member` passes | Split: (a) a member removed through CVAT's API is refused on the same session after the one-minute reuse has passed (the case waits that time with a margin); (b) that an answer is reused for at most one minute is shown by the service suite with supplied CVAT answers, unticked. |
| 12:13 detector boxes recorded by the UI, Model for annotator and project | a script sent the record in the UI's shape | `check-final` (ticket 25's part) passes | Boxes made with the built-in detector in the annotation view, with the model list and the model's answer supplied in the browser, are recorded by the real UI inside `debug:info`, accepted by the stock server, and count as Model for the annotator who ran it and for the project. A deployed model function is not exercised. |
| 13:10 a held key counts once; frame navigation every frame moved | the rule then counted every invocation | `check-fixes gestures` passes | Split: (a) on the stack, a next-frame key held on frames slowed by network latency counted one hotkey action per frame shown, fewer than its key-downs, and nothing for a press at the last frame or for the slider; (b) that another held key counts once is shown by the logging suite only, unticked. |
| 13:13 summary only when active and when the job closes; never on a timer alone | closing waited for the 90 s timer; loss on tab close | `check-final` and `check-fixes gestures` find the summary written when the job is left through the UI | Split: (a) a summary record is written when the job is closed through the UI and leaves with the closing save; (b) that it is otherwise written only at a moment of activity and never on a timer alone is shown by the logging suite, unticked. Counts since the last summary are lost when the tab is closed, a limit in the fork specification. |
| 15:14 an event two days late counted at the next check | the service suite only | no stack step (the daily check runs once a day; the API cannot date a record back) | Shown by the service suite on a supplied clock; not seen on the stack. Stays unticked. |
| 18:9 the real server accepts every record the UI logging adds | the detector record came from a script | `check-final` and `check-fixes gestures` pass with every `POST /api/events` answered 201 | On the stack the real server accepted, and the events table holds, every record the real UI added in the run: shape fields on draw, drag, paste, propagate and delete, the group drag record, class change by hotkey, the detector record (model answer supplied in the browser) and the input summary. Class change by mouse and resize were not driven. |
| 08:18 legacy period: notice, class change not recorded | a legacy rule since replaced by the stored cutover | no legacy period with job work exists on a fresh stack (all its work is after the cutover); page suite only | Shown by the page suite with supplied answers; the service decides a legacy period from the stored cutover (fork specification, Legacy rule). Not seen on the stack. Stays unticked. |
| 09:15 tagged period opens on Bounding boxes; legacy shows all shapes with the notice | as 08:18 | `check-fixes look` shows the first half; the legacy half as 08:18 | Split: (a) for a period with shape-tagged events the page opened on Bounding boxes on the stack; (b) for a legacy period it shows all shapes with the notice, shown by the page suite only, unticked. |

Note added later on 2026-11-15, after an independent review of the run: the column "Restated
as (if shown)" is the plan's wording, superseded by what part two showed and the tickets now
say. For 13:10 the plan expected the held key to count fewer actions than its key-downs; on
the stack every key-down moved a frame and no frame data request was held back. Ticket 13
states criterion 10 as shown: one hotkey action for each frame shown, nothing for the press
at the last frame or the slider, and no repeat arriving while a frame change waited; the
waiting path is its unticked criterion 11.

## Coverage of the run

What part two runs, criterion by criterion of ticket 27 and of the tickets that wait on it.

| Item | How it is shown |
| --- | --- |
| 27.1 `up`, `up`, `down` from an empty namespace, three images from the integrated branch | `run.sh status` shows no namespace; `up`; `up` again in place; `down`; `check-ingress-gone`; `status` |
| 27.2 service suite on both ClickHouse images; three fast suites; gate | rerun on the final tree (the last follow-up changes the service's list endpoint) |
| 27.3 each fix along the path that failed | `check-fixes`: status-roles, technical-project, gestures, unprocessed, cutover-restart |
| 27.4 split bars and definitions beside the prototype at 1400 and 400 px | `check-fixes look` judges the layout; a person compares its screenshots with the prototype's Main (1440 px) and Narrow (390 px) boards on the design canvas and writes what is seen here. The prototype's sources in the repository need the canvas's runtime and do not render alone |
| 27.5 sessions at the one-day limit | `check-fixes sessions-at-limit` |
| 27.6 the fork specification's limits | done in part one (above) |
| 27.7 the ten criteria | the table above |
| 27.8 one dated evidence file | this file |
| 27.9 independent review, access rules and policies on their own | the existing records (`2026-11-15-integrated-branch-review.md` and those it names); whether the last follow-up and `check-fixes` get one is the orchestrator's call |
| 27.10 teardown | `down` |
| 08, criterion 6: a fresh `up` passes every existing check; `down` leaves nothing | the first `up` and the `down` |
| 12, criterion 7: a stack `up` passes after the removal | the first `up` |
| 23, last criterion; 24, narrow window | `check-fixes look` and the person's comparison |
| Notes, ticket 01: `helm template` and `helm upgrade --install` through `helm_run` | the first `up` |
| Notes, ticket 16: both ClickHouse images on its queries | the service suite on both images |
| Notes, ticket 17: pod start on a loaded volume, liveness during the start-up search, the in-place upgrade read | `cutover-restart` (on the volume of the final run, restart count recorded) |
| Notes, ticket 18: an upgrade of an existing totals database creates `history_today` | `cutover-restart` (dropped, then created at start); a deployed window under 24 h stays unverified |
| Notes, ticket 19: a redo in a browser; an upgrade of a deployment holding stored totals | `gestures`; the second `up` on the first's totals |
| Notes, ticket 20: a replica killed on the stack | stays unverified |
| Notes, ticket 21: held key, the last frame, the slider, out-of-order frames | `gestures` (a backward jump is recorded and, when present, the `change:frame` comparison is left out); the capture `mousedown` listener is exercised by the slider press, judged only through the count |
| Notes, ticket 22: group payload, grabbed drag, later plain drag, `count` accepted | `gestures` |
| Notes, ticket 25: the detector from the real UI | the final run inside `up` |
| Notes, ticket 26: the volume through the events API from an empty namespace | the first `up` |

## Part two: the run, 2026-11-15

Run from branch `ticket/27-final-run`, which holds the integration branch at `b8521e3f`
(every ticket and every review follow-up, the last one included). Times are UTC. The
machine was otherwise free; no other agent changed the cluster.

### Images

Built one after another from that tree with the repository's three scripts:

| Image | ID |
| --- | --- |
| `cvat/server:v2.82.0-fork-policies` | `sha256:4b38c649ae96`, the same ID as before: its two policies are unchanged since that build, and `build-server.sh`'s two bundle checks passed |
| `cvat/ui:v2.82.0-team-analytics` | `sha256:a7229efd9174` |
| `cvat/team-analytics:v2.82.0` | `sha256:3bf1631cd7da` |

The stack ran the UI image by that ID (`check-task-progress` printed the running image's
digest).

### Live outcomes

**`up` from an empty namespace (ticket 27 criterion 1; ticket 08 criterion 6; ticket 12
criterion 7).** Before it, `run.sh status` showed no namespace and `check-ingress-gone`
passed. Attempt 1 (02:39 to 02:45) created the namespace, installed the chart through
`helm_run` (the first live `helm template` and `helm upgrade --install` of ticket 01's
filter), passed the policy bundle, the seed, the Ingress, the event, the tracer, the task
progress and the volume load (100 annotators posted their current week through the events
API, `0 of 1000 sessions already loaded`, all records in the events table 3 s after the last
request), then stopped: `ta-owner-c: POST /api/auth/login -> 429 "Request was throttled.
Expected available in 20 seconds."` CVAT throttles sign-ins, and the volume's hundred had
just used them up. A fault in the launcher: API requests now wait the time a 429 names (at
most five minutes) and the browser sends the login form again after a pause (`d61dd877`).
The namespace was deleted with `down`, which left nothing, and `up` repeated from an empty
namespace.

Attempt 2 (02:47 to 03:01) passed from start to finish. In order:

- preflight: the server image, the issue matrix's expectations against both policy sides,
  the chart build and the render checks;
- both policies in the served bundle are the patched ones, each by itself;
- the seed read back; one request through the Ingress (200 with a session, 401 without);
  a client event found in ClickHouse with its added payload field;
- the tracer's figures from a scheduled refresh, and the browser check as a maintainer and
  as a worker;
- task progress: 12 jobs in every stage and state and a single-job task, legend, segments,
  colours and totals as specified;
- the final run. The volume loaded through the events API as above. The real UI annotated
  a new job: two draws, two drags, a paste, a propagation of three, a class change by
  hotkey and a deletion. The detector ran twice from the AI tools; only the model list and
  the model's answer were supplied in the browser. Its record came from the UI, count 3 and
  `rectangle_count` 2, and every `POST /api/events` was answered 201. The figures followed:
  Model 6 under all shapes and 5 under bounding boxes, the worker's details 3 and 2. On the
  volume: 100 annotators, 40 projects, 100 sessions, 9 000 000 ms, 300 drawn, 290 saved,
  697 hotkeys, 100 mouse and 600 canvas clicks, ten weeks of trends. Every account then
  read every endpoint. The page in a browser passed the period, both filters, a full view,
  trends compared, the overview's length with 100 annotators and the narrow window. With
  the service stopped, the page showed its error panel and annotation was unaffected;
- the issue and comment matrix through the real API, 124 rows as expected;
- the four access cases: `removed-member` (403 with and without the organization after
  60 s), `group-admin`, `personal-workspace`, `header-credentials` (Basic and Bearer).

**The second `up`, in place (criterion 1).** Attempt 1 (03:02) stopped at the seed check.
On a stack holding the volume, the volume's organization has its hundred annotators as
members. The check compared the seeded members exactly and read one page of 100, which no
longer held the owner. A fault in the check, fixed in `abb02a10`: it reads every page and
allows the volume's annotators besides the seeded members. Attempt 2 (03:02 to 03:11)
passed every step on the first `up`'s data: `1000 of 1000 sessions already loaded`, the
tracer's work already loaded, a new real-UI project, the matrix and the four cases.

**`run.sh check-fixes` (criteria 3 to 5).** On its first contact with the stack five steps
needed changes to the steps themselves (commits `c61ec366`, `674ab90c`; the attempts' logs
are in the notes directory). No step showed a product defect. The whole command then ran
end to end and passed. The figures below are that end-to-end run's (`fix-all.log`), brought
to it later on 2026-11-15 after an independent review found that `unprocessed` and
`cutover-restart` first quoted the earlier single-step runs; those runs' figures, where they
differ, are given in brackets:

- `status-roles`. `ta-maintainer` and `ta-owner` with `ta-org-a` got `complete`,
  `complete_weeks`, `earliest_month`, `percent`, `periods` and `trends_ready` in `history`,
  and nothing else. `ta-admin`, with and without the organization, also got `days_ready`,
  `days_total`, `first_day`, `ready_from` and `ready_from_day`. All four got cutover
  `2026-09-12T08:00:00+00:00`.
- `technical-project`. A project in `ta-org-c` with no job work by anyone and three boxes
  saved by `ta-bot` through the API: by project, under both shape choices,
  `{working_time_ms: 0, sessions: 0, saved_boxes: 3, model: 3, annotators: 0}`. A search
  for `ta-bot` in the table by annotator found nothing.
- `unprocessed` (a supplied boundary: the step held the refresh lease and inserted one marker
  event on 2026-09-06, three days before the earliest recorded day 2026-09-09, which was the
  single-step run's probe day [that run: marker on 2026-09-09, before the first event day
  2026-09-12]). While the lease was
  held, `ta-maintainer` (with `ta-org-a`) and `ta-admin` (none) read the year directly:
  - overview, list, details by annotators and details by projects all answered
    `processed: false`, with no field outside the documented envelope non-null; the
    overview kept only `filters`, `operations` (legacy flags), `period` and `processed`;
  - trends by week (bucket of 2026-08-31 [2026-09-07]) and by month (2026-09) had that
    bucket not processed and every value null;
  - the week stayed processed, with figures.

  The step released the lease after 7 s. The service processed the three days within 30 s
  [5 s], and the year then had figures for both callers. The marker was deleted.
- `gestures` (`ta-worker-c`, a new job of 150 frames of 600 px, one frame per chunk):
  - **Redo.** A box drawn, undone and redone with the header buttons gave one
    `action:undo` and one `action:redo` (`name: Created objects`).
  - **Group moves.** Two more boxes were drawn and saved, then selected with Shift and a drag
    on the background. The selection was moved by its header label. The pair was copied and
    pasted, and the pasted pair dragged by its first box. One box was then dragged alone and
    the job saved. The events table holds exactly two group records, each `drag:object`
    with `count` 2, `group: move`, `rectangle_count: 2`, `shape_type: rectangle`,
    `object_type: shape`, `input_method: mouse` and `frame`, with no `object_ref` and no
    `obj_id`. The later plain drag carries `object_ref` and `obj_id` and no `group`. Every
    `POST /api/events` was answered 201.
  - **Figures.** Creation 5 (drawn 3, pasted 2: the redo added none), deletion 0,
    alignment 5 (2 + 2 + 1), hotkey actions 69 as the summaries hold them.
  - **Held key.** F was held for 4 s (65 key-downs): the page showed frames 0 to 65, one per
    key-down. The summary's `NEXT_FRAME` is 65. F pressed at the last frame (149, typed into
    the frame field) moved nothing, and a press near the slider's start (149 to 1) added no
    hotkey.
- `look`, below.
- `sessions-at-limit`. 1 008 sessions stored in the instance-wide set (the run's own work
  and the volume): 0 span a day less the session gap or more. The longest is 1.50 h.
- `cutover-restart` (a supplied boundary: the service was scaled to 0, the totals database's
  `cutover` table emptied and `history_today` dropped, then the service scaled to 1). The
  events table held 3 052 [3 045] tagged operation events, the first in hour
  2026-09-12T08:00Z.
  The first `status` answer to `ta-maintainer` and to `ta-admin`, 3 s after the restart,
  carried that hour. `history_today` was created again at start. The pod restarted 0 times
  during the start-up search, on the volume of the final run.

What the steps first got wrong, and what the browser showed about the product:

- `look` judged the split on the volume's organization, whose rows are almost all creation
  (one part per bar is right there). It now judges the split on `ta-org-c` and the layout
  on both. Its first screenshots covered only the window: the page scrolls inside CVAT's
  layout, not the document.
- `gestures`, three findings about the canvas:
  - On 8 px frames the boxes were a few screen pixels, so the frames are now 600 px.
  - Right after a region selection the canvas is in its selecting mode. The selection box
    lets presses through, a press on a member clears the selection, and the selection
    moves only by its header label. So the step moves it by the label, and makes the second
    group move inside a pasted selection, where the canvas is idle.
  - A press inside the pasted pair hit the selection box, not the member. No gesture
    produced CVAT's own drag of a grabbed member (`group: grabbed`), so that record was not
    seen in a browser.
- `gestures`, the held key. Page-level network emulation does not reach the frame data,
  which the UI's workers fetch, so the step now holds chunk requests back through the
  browser's own interception. The final run made no chunk request during the hold: the data
  was already fetched. In an exploratory probe that held four chunk requests back by 1.5 s,
  the frame still moved on every key-down: the frame change does not wait for the frame's
  data. A repeat arriving while a frame change still waits, the path the fix is about, was
  therefore not reached in a browser. The step records key-downs that moved no frame (0)
  and judges `NEXT_FRAME` against the frames shown.
- `gestures`, CVAT's own records. cvat-core merges consecutive equal frame steps into one
  `change:frame` record and raises its count, but a record already sent keeps the count it
  had. The rows held `(count 1, 64 to 65, step 1)` for 65 single steps shown, so they are
  recorded, not judged. This is upstream behaviour.

### The look beside the prototype (criterion 4; ticket 23, last criterion; ticket 24)

What the comparison was made against: the page rendered by the stack's UI image in headless
Chrome at 1400 px and at 400 px. Full-page screenshots of `ta-org-c` and of the volume's
organization, at both widths, are kept outside the repository with the run's logs. They
were set beside the prototype's source (`docs/design/team-analytics/prototype/Main.dc.html`,
`Narrow.dc.html`, the Main board 1440 px and the Narrow board 390 px wide), `design.md`, and
the expectations tickets 23 and 24 wrote down. The prototype was not rendered: its sources
need the design canvas's runtime, which is not in the repository. This is a comparison with
its source and description, not a side-by-side look. The measurements are `check-fixes
look`'s; the rest is what was seen in the screenshots.

Matches:

- **Split bars.** Both working-time cards draw each bar in Creation, Alignment, Class
  change, Deletion and Other, in the operations table's colours, with 2 px gaps and no track
  (prototype: the parts of `partsOf`, flex by value). Every `ta-org-c` row is in several
  parts. On the volume every bar is one blue part, which matches its data: creation takes
  97 % of working time there.
- **Legend.** It sits inside the card, above the rows.
- **Rest line and button.** The rest line is text only, `32 more, not shown` and its hours,
  and the button reads `Show all 40 in full view`: the prototype's `othersLabel` and
  `toggleLabel`.
- **Long names.** They are cut with an ellipsis at both widths, and nothing leaves its card.
- **Cards at 1400 px.** The two cards sit side by side, by project and by annotator.
- **Definitions.**
  - At 1400 px: the block ends the overview below the details table, plain text and not a
    card, the term bold, in four columns. The prototype has the same grid,
    `repeat(auto-fit, minmax(280px, 1fr))`, plain 13 px text with a bold term.
  - At 400 px: one column, inside the page's column and the window.
  - A full view shows none.

Differences:

- **Row layout.** The prototype puts name, bar and hours on one line. The page keeps its
  row: name and hours on top, the bar under them (named by ticket 23).
- **Legend.**
  - The page adds the hint "Select a row to filter the whole page" under the legend, and the
    card's subtitle is "Last 7 days". The prototype's subtitle is "Hours split by operation
    · <scope>".
  - At 400 px the legend wraps onto two lines inside the card, as ticket 23 expected.
- **Gaps of empty parts.** Where a row has no time in Class change and Deletion, their empty
  parts show as a wider gap between Alignment and Other, not at the bar's end as ticket 23's
  note expected. The parts keep the operations' order, Other last.
- **Neutral bar.** Not seen: every row came with its parts from the current service.
- **Definitions' wording.** It is the glossary's, not the prototype's (named by ticket 24).
- **Width at 400 px.** The page fits the window, but the document still scrolls sideways,
  because CVAT's own header keeps the app 1025 px wide, as before.
- **Not looked at:** hover titles (headless, no pointer looked at them), and a legacy period.
- **Outside tickets 23 and 24, for the owner.** On `ta-org-c`, whose scope holds 0.1 h,
  "Where working time goes" draws its stacked bar only a few dozen pixels wide, at both
  widths. The label of its Other part is cut to "71" (Other is 71 %). On the volume the
  same card's bar spans the card.

### Checks with supplied boundaries

- **Service suite on both ClickHouse images.** The orchestrator ran it from a copy of the
  tree at `b8521e3f`; this branch changes no file the suite reads. The last lines of its
  two logs: `cvat/clickhouse:23.12.2-debian-11-r0`: `Ran 319 tests in 2591.379s`, `OK`,
  `exit=0`; `clickhouse/clickhouse-server:23.11-alpine`: `Ran 319 tests in 2467.472s`,
  `OK`, `exit=0`.
- **Fast suites.** Run on this branch: the page suite 223 pass, 0 skipped; UI logging 77
  pass, 0 skipped; task progress 20 pass, 1 skipped (the optional browser check).
- **The gate.** `prek run --all-files` on the final commit, recorded in ticket 27's comment.
- **In `check-fixes`, the states set by hand.** The probe's lease and marker event, and the
  emptied cutover table with the dropped `history_today`, stand for an unprocessed period
  and for a totals database written before the cutover search. They are not an upgrade from
  an older release.

### Teardown (criterion 10)

Before `down` (03:45): the namespace `cvat-ta-it-<user>` was Active, created 02:47, with 14
pods. It held Ingress `team-analytics` (class `nginx`, host
`cvat-ta-it-<user>.k8s.docker.internal`) and five Bound claims:

- `cvat-backend-data`;
- `cvat-kvrocks-data-cvat-kvrocks-0`;
- `data-cvat-clickhouse-shard0-0`;
- `data-cvat-postgresql-0`;
- `redis-data-cvat-redis-master-0`.

Each was bound to its own volume of the default class. The launcher's port-forward held
8490.

`run.sh down` (03:45 to 03:46, exit 0) printed `stopping port-forward`, `deleting namespace
cvat-ta-it-<user> (with every volume claim in it)` and `nothing of cvat-ta-it-<user>
remains`. `run.sh check-ingress-gone` (exit 0) printed `no Ingress names
cvat-ta-it-<user>.k8s.docker.internal; the controller answers 404 for it`.

Looked at after `down` (03:46); nothing was deleted by hand:

- The namespace is not found, and no namespace carries the stack's `managed-by` label.
- No Ingress anywhere names the host; only k8s-infra's three ClearML Ingresses remain.
- None of the five volumes exists, and no volume has a claim in the namespace.
- No port-forward process is left, and nothing listens on 8490, neither in WSL nor on
  Windows.
- The state directory for the namespace is gone.

Not looked at: the empty per-claim directories the `hostpath` provisioner leaves inside
Docker Desktop's disk. The run's screenshots and logs are kept outside the repository, in
the shared notes directory.

### Ticks

- **Ticket 27:**
  - Ticked: criteria 1 to 3, 4 as restated, 5 to 8 and 10.
  - Two lines were split off and left unticked:
    - the held-key repeat during a waiting frame change and the grabbed drag (neither was
      reached in the browser);
    - the prototype rendered beside the page.
  - Criterion 9 (an independent review of the integrated branch) is left unticked. The
    recorded reviews cover the branch to `de181cd7` and the three follow-ups after it.
    Whether the last follow-up and this ticket's stack tooling get one is the
    orchestrator's call.
- **Ticket 08**, criterion 6, and **ticket 12**, criterion 7: ticked.
- **Ticket 23**, last criterion, and **ticket 24**, narrow window: ticked, restated as what
  was shown.
- **The ten criteria,** by the accepted rule: tick only what the stack shows, and split a
  line whose other part only a suite shows.
  - Ticked whole: 04:12, 12:13, 18:9.
  - Split, the stack part ticked: 04:17, 13:10, 13:13, 09:15.
  - Unticked: 04:16, 15:14, 08:18.

  The original wording of each is quoted in a dated comment in its ticket.

### For the owner, not asked

The specification states both of these as they are, from the code; no code was changed for
them, and the owner has not been asked:

- In 3D jobs, CVAT's own untagged draw, paste and delete events count as creations and
  deletions under All shapes.
- A stored session can span up to two days, where the glossary says at most a day. On this
  run none came near a day.

### Still unverified

- **Two fix paths not reached in a browser:**
  - a repeat of a held navigation key that arrives while a frame change waits;
  - CVAT's own drag of a grabbed member of a group.

  The logging suite shows both with supplied boundaries.
- **Not exercised on the stack:**
  - a replica killed mid-step (ticket 20);
  - a deployed refresh window under 24 h (ticket 18);
  - a late event counted by the daily check (Team Analytics 15:14);
  - CVAT unreachable (04:16);
  - a legacy period with job work (08:18, 09:15);
  - class change by mouse and resize;
  - a deployed model function.
- **Upgrades:** an upgrade from a real older release; the cutover read was shown on a state
  set by hand.
- **Not looked at in the look:** hover titles and a legacy period.
- **The prototype** was not rendered.
- **A load crossing midnight UTC** (ticket 26): this run loaded between 02:4x and 03:0x UTC.
