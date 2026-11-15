# Final run on a fresh stack, 2026-11-15

Ticket 27 of the defect fixes. The ticket is done in two parts. Part one, below, prepared
the run without a stack: the steps the launcher lacked, the fork specification's limits,
and what each criterion ticked on a reading needs before it may be ticked again. Part two
(the run itself: images, `up`, `up`, the fix steps, `down`) is not done yet; until it is,
nothing in this file is a live outcome.

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

## Part two

Not run yet.
