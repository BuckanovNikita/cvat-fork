# The detector record from the real UI on the test stack, 2026-11-15

Ticket 25 of the defect fixes (plan row V5a, spec default (e)). The final run of the test
stack (`verify/team-analytics-stack/run.sh check-final`) used to post a hand-made
`team_analytics:model_creation` record through the API. Now the annotator in the run's
headless Chrome uses the detector in the real UI, and the UI sends the record itself.

**The model's answer was supplied.** The stack has no model function: nuclio is off, and the
server answers `503` to `HEAD` and `GET /api/lambda/functions`, because it cannot resolve
the nuclio host. The run therefore answers the model list and the model's answers in the
browser. **No deployed model function was used.** Whether a real model function returns
answers the UI can create objects from is still unverified.

## What is supplied and what is real

cvat-core makes these requests for a detector run from the annotation view
(`cvat-core/src/server-proxy.ts`, `getLambdaFunctions` and `callLambdaFunction`; the UI calls
them through `getModelsAsync` at app start and through the detector runner of the AI tools
control in `tools-control.tsx`):

| Request | When | In the run |
| --- | --- | --- |
| `HEAD /api/lambda/functions` | each page load, model list | supplied: 200 |
| `GET /api/lambda/functions` | each page load, model list | supplied: one detector, labels `box` and `other` (type `any`) |
| `POST /api/lambda/functions/<id>` | Annotate in the detector runner | supplied: the model's answer for the frame |

The browser answers them with the DevTools `Fetch` domain on the annotation page, matching
`*/api/lambda/*`. Every other request matching that pattern goes on to the server and is
recorded. In the run there was one: `GET /api/lambda/requests`. The tasks page makes it
(`getInferenceStatusAsync`) when the browser leaves the job, and the real server answered it.

Everything else ran for real: the AI tools control, its Auto-labeling tab, the model
selector, the label mapper (it mapped both labels by name on its own), the Annotate button,
the create thunk, the object collection, the job save, `recordModelCreation`, the cvat-core
logger, `POST /api/events`, the server, Vector, ClickHouse and the service's scheduled
refresh. The UI image was `cvat/ui:v2.82.0-team-analytics` (`310e9bbc6a47`), built from
`3dc1a7bc`. The UI code in `cvat/` is unchanged between that commit and this ticket's branch.

The answers came in a fixed order. The first was empty (`shapes: []`, `tags: []`). The
second held two rectangles (labels `box` and `other`) and one polygon (`box`) on the job's
frame 0. It used the job's label ids, which `final_run.py prepare-ui` now hands to the
browser.

## Live outcome

One `run.sh check-final` on the running stack, 2026-11-14 22:01–22:06 UTC (2026-11-15
local), project 54 in `ta-org-c`. The whole final run passed: volume, access, page, and the
service stopped and started again. The detector part, from the run's log:

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

What this shows:

- **The objects the UI created.** The first Annotate created nothing and showed no error
  notice; the canvas stayed at 2 shapes. The second created 3 shapes on the canvas (2 to 5).
  After the save, the job's annotations held 3 objects with source `auto`, 2 of them
  rectangles.
- **The record.** The run read every `POST /api/events` body the page sent; all three were
  answered 201. Exactly one `team_analytics:model_creation` record was in them, with
  `count` 3, `rectangle_count` 2 and the job's id. ClickHouse holds exactly one such record
  for the project, checked again 10 s after it arrived: user `ta-worker-c`, job 44, `count`
  3, payload `{"rectangle_count": 2, "client_id": ..., "is_active": true}`. Both are compared with the objects read from the job, not
  with constants. The events table also shows the stock `click:element` event for
  `cvat-inference-run-button` twice, and `create:shapes` rows for `rectangle` and `polygon`
  from the save.
- **No record for the empty answer.** The empty run's model call was made and answered
  (`answered 0`). The page sent no record for it: one record in the bodies and one in
  ClickHouse, and that one has `count` 3. `recordModelCreation` is not reached when the
  create thunk returns no ids.
- **Model figures after a refresh.** The run triggers no refresh. The figures were read
  when the service's scheduled refresh had processed the period (32 s after the records). For
  the project, Model is 6 under All shapes (3 detector objects and 3 boxes of the
  technical account `ta-bot`) and 5 under Bounding boxes (2 and 3). `ta-worker-c`'s Model in
  the details table holds the detector run alone, since the technical account is not listed
  among people: 3 under All shapes, 2 under Bounding boxes. The overview's Model carries only
  `objects` and `share`, and the details row only a `model` count. Neither has a time field.
  The page showed Model 6.
- **The hand-made record is gone.** `final_run.py` no longer posts to `/api/events`, and its
  `DETECTOR` constant is removed.

An earlier run of only the UI part (`run.sh check-final-ui`, project 52) found the same
requests, objects and record. Its first pass stopped on two script mistakes: the passed
`GET /api/lambda/requests` was not yet allowed, and ClickHouse's `job_id` was compared as
text. Both were fixed, `check-ui-records` and `check-ui-figures` were run again on that
run's state, and they passed with the same figures (Model 6 and 5; `ta-worker-c` 3 and 2).

Observed and not investigated: in the full run the overview's session for project 54 lasted
171 946 ms, while that project's own events span about 29 s. 171 946 ms is exactly the time
from `ta-worker-c`'s last event in project 52 (21:59:08.939) to the last one in project 54
(22:02:00.885). The two runs were about three minutes apart, so one session seems to span both
projects. The final run's checks do not compare session time with working time.

## Checks with supplied boundaries

None new. The seam 2 test `verify/team-analytics-logging/model-creation.test.cjs` covers
`recordModelCreation` and its call site with a supplied detector answer and object collection;
this ticket did not change it.

## What remains unverified

- A deployed model function (nuclio or another provider) answering the UI. The stack has
  none. Its request and answer were supplied in the browser.
- Detector runs that create tags, masks or skeletons, or objects on several frames. The
  supplied answer had two rectangles and a polygon on one frame.
