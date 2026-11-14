# A group move is one alignment per object, 2026-11-14

Ticket 22 of the defect fixes. A group drag was logged and counted as one
alignment of the grabbed object, and moving the selection box was logged as
nothing. Now a group move is one alignment for each object moved, sharing the
gesture's time equally.

## The event

Fixed first in `cvat/cvat-ui/src/utils/team-analytics-logging/contract.ts`
(`PAYLOAD.group`, `GROUP`). A group move is one `drag:object` for the gesture,
sent through the job's logger:

| Field | Value |
| --- | --- |
| `scope` | `drag:object` (no new event type, ADR 0002) |
| `count` (column) | the number of objects moved |
| `duration` (column) | the gesture's duration, from the canvas |
| `obj_id` | absent |
| `project_id`, `task_id`, `job_id` | the job's |
| payload `group` | `move` |
| payload `shape_type`, `object_type` | of all objects moved (`mixed` when they differ) |
| payload `rectangle_count` | how many of them are bounding boxes |
| payload `frame` | the frame |
| payload `input_method` | `mouse` |
| payload `object_ref` | absent |

When the gesture began by dragging one of the objects, the canvas then reports
that object's own drag in the same task, and CVAT logs its `drag:object` as
before: `obj_id`, the shape fields, `object_ref`, `frame`, plus payload
`group` = `grabbed`. That event is no operation. Moving the selection box
sends only the group event. If the group event cannot be built or sent, the
grabbed drag carries no mark and counts as a single drag, as before.

The UI hook is one line in the group-moved handler of `canvas-wrapper.tsx`
(`groupMoved(jobInstance, e.detail)`, before the move is saved); the rest is
`group-move.ts` in the logging module.

## Observed

### Seam 2, the events the UI sends

`verify/team-analytics-logging/group-move.test.cjs`, seven tests, drives the
canvas wrapper's handlers in the canvas's order (group event, then the grabbed
drag, without waiting between them). Before the UI change four failed: a group
drag of three boxes sent only the grabbed box's plain drag, and moving the
selection box sent no drag event. The three that passed already are guards: a
failure in the logging, a refusing logger and a 3D job. After the change all
seven passed, and the whole logging suite passed with 0 skipped.

ESLint (`--max-warnings 0`) on the four UI files touched and the UI type check
passed.

### Seam 1, the service's read interface

The new `GroupMoveTest` in `tests/test_bounding_boxes.py` feeds the pair the UI
really sends (group event, then the marked grabbed drag 1 ms later, or at the
same millisecond). On the old rule all five failed:

| Case | Old rule (objects, timed objects, ms) | New rule |
| --- | --- | --- |
| Group drag of three boxes, 6 s | (2, 1, 1) | 3 alignments, 6 s, 2 s each |
| Grabbed drag at the same millisecond | (2, 1, 0) | 3, 6 s |
| Selection box moved, three boxes | (1, 0, 0) | 3, 6 s |
| Two boxes and a polygon, Bounding boxes | 2 objects, 1 ms | 2 objects, 4 s (All shapes: 3, 6 s) |
| Drag box 1, group move of boxes 1 and 2, drag box 1 | (3, 3, 15000) | (4, 4, 14999): three of box 1, one of box 2 |

The first version of four of the tests gave the gesture a 6 s duration from
the job's opening, so the opening event (no known gap before it) fell inside
the gesture, and the rule left it untimed: counts right, time 0. That is the
rule for any operation. The tests now give the gesture 5 s, starting 1 s after
the opening.
The old-rule column above was seen with that first version. The corrected
tests (`5981c50`) were not run on the old rule; the counts they check differ
either way (the old rule gives one or two alignments per gesture, never three).

The modules the operations rule feeds were run on the fix: `test_bounding_boxes`,
`test_operations`, `test_creation_methods`, `test_keyboard_mouse`,
`test_sessions`, `test_class_change`, `test_model_saved_boxes`, `test_full_view`,
`test_details_table`, `test_trends`, `test_cutover`. Default ClickHouse image
(`cvat/clickhouse:23.12.2-debian-11-r0`).

### After the fix

- The eleven modules above and the stored-hours check, on the fix with the
  first version of the group tests: every test passed except four of
  `GroupMoveTest`, which counted right but read the gesture as untimed (see
  above).
- `test_bounding_boxes` again after the tests were corrected (`5981c50`):
  all passed. Only that file changed between the two runs.
- Existing cases that pin the old behaviour still pass unchanged: single drags
  and resizes of one box, the end of a run by another object, a frame change,
  a redo or a pause, and legacy drags without `object_ref` as one alignment
  each.

### Hours already stored

Seen once with a check that is not kept as a test (ticket 19's method: inside
one process the service first ran with the old calculation file until history
was complete, then with the new one, on the same totals database). The same
gesture, a group drag of three boxes, was stored on a day eight days before the
test clock and in the trailing window. Once as the new UI logs it (group event
and marked grabbed drag), once as a UI without the group event logs it (one
plain drag of the grabbed box). Alignments for the month:

| Moment | New UI, old day | New UI, recent | Old UI, old day | Old UI, recent |
| --- | --- | --- | --- | --- |
| Old rule, everything processed | 2 | 2 | 1 | 1 |
| New rule, after the next refresh | 2 | 3 | 1 | 1 |
| New rule, a day later, after the daily check | 2 | 3 | 1 | 1 |
| New rule, after a late event on the old day and the next daily check | 3 | 3 | 1 | 1 |

So events from a UI without the group event read the same under both rules.
Hours stored from the new UI by a service without the new rule keep two
alignments per group drag until they are computed again. The fork
specification (TA-1, "Known limit of the stored totals") says so.

## Supplied boundaries

- Seam 2 calls the canvas wrapper's handlers with the canvas's event details.
  The real canvas, which dispatches the group event and then the grabbed drag
  in one task, was read, not run.
- Seam 1 events are rows inserted into the events table, shaped as the UI
  sends them. CVAT was the tests' stand-in.
- The stored-hours check replaced the text of one SQL file inside the process.

## Not verified

- A group drag and a selection-box move in a real browser, read back from the
  events table. That is ticket 27. That run should look for, per gesture,
  exactly one `drag:object` with payload `group` = `move` and `count` = the
  objects moved, and for a drag of a selected object also CVAT's own
  `drag:object` of it with `group` = `grabbed`, `obj_id` and `object_ref`. A
  later single drag of one of those objects must carry no `group`. On the page
  the alignments should rise by the objects moved, not by two.
- That the stock server accepts `count` on `drag:object`. Upstream's UI
  already sends `count` on `paste:object`, which is not among the scopes that
  require it, so the field is accepted on any scope. The server was not run.
- The whole seam 1 suite: it is run on the integration branch after this
  package's tickets are merged.
- The second ClickHouse image.

## Independent review, 2026-11-15

An independent review of the counting changes of tickets 19, 21 and 22 found the
group-move rule sound through the read interface (a group record and its grabbed
drag either side of a window or hour edge give 3 alignments once; a duplicated
group record counts twice, as any duplicated record does). Four of its findings
concern this ticket, all recorded in documents with no code change: the canvas's
dispatch order as an upstream dependency (fork specification and
`docs/upstream-upgrade.md`), the old rule's effect on a group drag followed by a
drag of the grabbed box (stored as 2 under the old rule, 3 under the new), and
two limits for the owner: a refused group record after the mark is set loses
the gesture's objects, and a selection-box move adds one `drag:object` to
CVAT's own log. The review and what was done about each finding are in
`docs/evidence/2026-11-14-frame-navigation-hotkeys.md` ("Independent review,
2026-11-15").
