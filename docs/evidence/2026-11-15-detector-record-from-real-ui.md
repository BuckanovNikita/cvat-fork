# The detector record from the real UI on the test stack, 2026-11-15

Ticket 25 of the defect fixes (plan row V5a, spec default (e)). The final run of the test
stack (`verify/team-analytics-stack/run.sh check-final`) used to post a hand-made
`team_analytics:model_creation` record through the API. Now the annotator in the run's
headless Chrome uses the detector in the real UI, and the UI sends the record itself.

**The model's answer was supplied.** The stack has no model function: nuclio is off. A
read-only request on 2026-11-15 got `503` from the server for `HEAD` and
`GET /api/lambda/functions`, because it cannot resolve the nuclio host. The run therefore
answers the model list and the model's answers in the browser. **No deployed model function
was used.** Whether a real model function returns answers the UI can create objects from is
still unverified.

## What is supplied and what is real

cvat-core makes these requests for a detector run from the annotation view
(`cvat-core/src/server-proxy.ts`, `getLambdaFunctions` and `callLambdaFunction`). The UI
calls them through `getModelsAsync` at app start and through the detector runner of the AI
tools control (`tools-control.tsx`). This is a code reading; the run's log below matches it.

| Request | When | In the run |
| --- | --- | --- |
| `HEAD /api/lambda/functions` | each page load, model list | supplied: 200 |
| `GET /api/lambda/functions` | each page load, model list | supplied: one detector, labels `box` and `other` (type `any`) |
| `POST /api/lambda/functions/<id>` | Annotate in the detector runner | supplied: the model's answer for the frame |

The browser answers them with the DevTools `Fetch` domain on the annotation page, matching
`*/api/lambda/*`. Every other request matching that pattern is passed on to the server
unchanged and recorded. In the runs there was one: `GET /api/lambda/requests`. The tasks
page makes it (`getInferenceStatusAsync`) when the browser leaves the job. The run does not
record its answer.

Everything else ran for real. On the UI side: the AI tools control, its Auto-labeling tab,
the model selector, the label mapper and the Annotate button. Then the create thunk, the
object collection, the job save, `recordModelCreation`, the cvat-core logger and
`POST /api/events`. Behind them, the server, Vector, ClickHouse and the service's scheduled
refresh.

- The label mapper mapped the model's labels to the job's by name, with no action from the
  script. Each run had 2 mapping rows. The model call's body carried
  `mapping: {box: {name: box}, other: {name: other}}`, `frame` 0 and the job's id.
- The frontend ran `cvat/ui:v2.82.0-team-analytics`. Read-only, on 2026-11-15: the pod's
  image id was `sha256:310e9bbc6a47...`, the same as the local image. The image was built
  from `3dc1a7bc`, and the UI code in `cvat/` is unchanged between that commit and this
  ticket's branch.

The answers came in a fixed order. The first was empty (`shapes: []`, `tags: []`). The
second held two rectangles (labels `box` and `other`) and one polygon (`box`) on the job's
frame 0. It used the job's label ids, which `final_run.py prepare-ui` now hands to the
browser.

## Checks with supplied boundaries: the live runs

Everything below ran on the live stack. The model list and the model's answers were the only
supplied parts.

**`run.sh check-final`**, 2026-11-14 22:01–22:06 UTC (2026-11-15 local), project 54 in
`ta-org-c`. The whole final run passed: volume, access, the page, and the service stopped
and started again. The detector part, from the run's log:

```
  detector: ran twice; answered 0, 3 objects; shapes 2 -> 2, 2 -> 5
  F x3, D x2, Ctrl+S: 7 boxes saved in the job; detector objects saved {"objects":3,"rectangles":2}
  left the job; 3 POST /api/events: [201,201,201]
  detector: supplied ['HEAD /api/lambda/functions', 'GET /api/lambda/functions', 'POST /api/lambda/functions/ta-supplied-detector', 'POST /api/lambda/functions/ta-supplied-detector']; passed to the server ['GET /api/lambda/requests']; canvas shapes per run [(0, 2, 2), (3, 2, 5)]; saved in the job with source auto {'objects': 3, 'rectangles': 2}
  team_analytics:model_creation from the real UI: 1 record (sent 1), count 3, rectangle_count 2; none for the empty answer
  figures of project 54: ready after 32 s
  operations: {'creation': 6, 'alignment': 1, 'class_change': 1, 'deletion': 1, 'other': 0}, methods {'drawn': 2, 'pasted': 1, 'propagated': 3}, model {'objects': 6, 'share': 0.5}
  bounding boxes: model 5
  Model (all): overview {'objects': 6, 'share': 0.5}, ta-worker-c in the details 3 = the detector's 3
  Model (bounding_boxes): overview {'objects': 5, 'share': 0.45454545454545453}, ta-worker-c in the details 2 = the detector's 2
  real UI figures on the page (project 54): {"Creation":"6","Alignment":"1","Class change":"1","Deletion":"1"}, methods {"Drawn":"2","Pasted":"1","Propagated":"3","Model":"6"}, hotkey actions 12
```

**`run.sh check-final-ui`**, 2026-11-14 22:13–22:15 UTC, project 56. This is the new narrow
subcommand: only the UI part and its figures. It passed and logged the same detector lines,
with the figures ready after 58 s of polling. Its record reached ClickHouse at 22:13:36. The
service log shows refreshes at 22:14:00 and 22:15:01, part of its one-a-minute schedule, and
the run triggers none. So the figures it read came from a scheduled refresh. (For project 54
the log is gone: the service-stop step replaced the pod.)

What these runs show:

- **The objects the UI created.** The first Annotate created nothing and showed no error
  notice; the canvas stayed at 2 shapes. The second created 3 shapes on the canvas (2 to 5).
  After the save, the job's annotations held 3 objects with source `auto`, 2 of them
  rectangles. The save wrote `create:shapes` rows for `rectangle` and `polygon`. The events
  table holds the stock `click:element` event for `cvat-inference-run-button` twice.
- **The record.** The run read every `POST /api/events` body the page sent, and all three
  were answered 201. Exactly one `team_analytics:model_creation` record was in them, with
  `count` 3, `rectangle_count` 2 and the job's id. ClickHouse holds exactly one such record
  for the project, checked again 10 s after it arrived. In project 54 it reads: user
  `ta-worker-c`, job 44, `count` 3, payload
  `{"rectangle_count": 2, "client_id": ..., "is_active": true}`. Both the sent record and
  the stored one are compared with the objects read from the job, not with constants.
- **No record for the empty answer.** The empty run's model call was made and answered
  (`answered 0`). The page sent no record for it: one record in the bodies and one in
  ClickHouse, and that one has `count` 3. By reading the code, the call site in
  `tools-control.tsx` reaches `recordModelCreation` only when the create thunk returns
  created ids, and `recordModelCreation` sends nothing for an empty list.
- **Model figures after a scheduled refresh.** For the project, Model is 6 under All shapes
  (3 detector objects and 3 boxes of the technical account `ta-bot`) and 5 under Bounding
  boxes (2 and 3). `ta-worker-c`'s Model in the details table is the detector run alone,
  since the technical account is not listed among people: 3 under All shapes and 2 under
  Bounding boxes. The overview's Model carries only `objects` and `share`, and the details
  row only a `model` count. Neither has a time field. The page showed Model 6.
- **Saved boxes are now 10 in total and 7 for `ta-worker-c`.** The 2026-11-14 run had 8 and 5.
  The detector's two rectangles are now saved in the job.
- **The hand-made record is gone.** `final_run.py` no longer posts to `/api/events`, and its
  `DETECTOR` constant is removed.

The first `check-final-ui` (project 52, 21:58 UTC) found the same requests, objects and
record. It stopped on two script mistakes: the passed `GET /api/lambda/requests` was not yet
allowed, and ClickHouse's `job_id` was compared as text. Both were fixed before the two runs
above.

## Observed and not investigated

In the full run, the overview's session for project 54 lasted 171 946 ms, although that
project's own events span about 29 s. 171 946 ms is exactly the time from `ta-worker-c`'s
last event in project 52 (21:59:08.939) to the last one in project 54 (22:02:00.885). The two
runs were about three minutes apart, so one session seems to span both projects. In the
`check-final-ui` run ten minutes later, the session was 29 144 ms. The final run does not
compare session time with working time.

## What remains unverified

- A deployed model function (nuclio or another provider) answering the UI. The stack has
  none, and its request and answer were supplied in the browser.
- Detector runs that create tags, masks or skeletons, or objects on several frames. The
  supplied answer had two rectangles and a polygon on one frame.
- What the real server answered to `GET /api/lambda/requests`. The run passes it on and does
  not record the answer.
