# A redo is not a creation, 2026-11-14

Ticket 19 of the defect fixes. The service stored a redo of created objects as
a second creation and gave it a creation method: that of the same person's last
creation in the job within 300 s, else Drawn. The rule is now the glossary's:
an undone creation is still a creation, and redoing it is not a second one.
The change is in `team-analytics/service/sql/refresh/operations.sql`.

Every run below is seam 1 (`verify/team_analytics_service.sh`): the service's
read interface against a throwaway ClickHouse, on the default image
(`cvat/clickhouse:23.12.2-debian-11-r0`). Events are inserted as rows and CVAT's
identity answers come from the tests' stand-in. No browser and no stack was
involved.

## Observed

### Before the fix

The existing redo tests were changed and the new ones added first, then run on
the unchanged service: 14 tests, 9 failed.

| Case | Old rule returned | New rule expects |
| --- | --- | --- |
| Draw (10 s), undo, redo 5 s later, 100 s of working time | Drawn: 2 objects, 15 s | Drawn: 1 object, 10 s; Other 90 s |
| Redo after a paste of two and after a propagation of three | Pasted 3, Propagated 4 | Pasted 2, Propagated 3; Other 78 s of 100 s |
| Redo with no earlier creation | Drawn 1 | no creation |
| Redo in another job, and by another annotator | Drawn 2 | no creation |
| Redo five minutes after the creation | Drawn 1 | no creation |
| Shape switch case under All shapes | Propagated 4 objects, 11 s | Propagated 3 objects, 6 s |
| Redo just after the edge of a one-hour refresh window | Propagated 3 | Propagated 2 |
| A creation undone and redone | 2 creations | 1 creation, no deletion |
| Draw, undo, redo, delete, no working time in the period | active time 19 s | active time 14 s, Other 0, shares add up to 1 |

Five tests of that run passed on the old code. Two of them are new and pin
behaviour that the fix must keep: an undone creation still counts (one
creation, no deletion), and a drag of a box, a redo of created objects and
another drag of that box are two alignments (5 s and 2 s; the 3 s before the
redo belong to no alignment).

### The alignment default

With the redo no longer an operation and not yet listed as an event that ends
a run, the alignment test failed: the two drags became one alignment of 10 s.
Once a redo of created objects was listed as ending a run, it passed again.
The redo that ends a run is the one that did before: a redo of created objects
inside a job.

### After the fix

- The whole seam 1 suite on the fix (`cc74fba`): 269 tests passed in 1409 s.
  The baseline was 265; this ticket adds four.
- The integration branch was merged after that run (`03a5fbf`). Of the files
  the suite uses (the service directory, its launcher and CVAT's ClickHouse
  setup script) the merge changed only the setup script, restored to
  upstream's formatting. Its Python syntax tree is the same before and after
  the merge, so the suite was not run again.

### Hours already stored

Read in the code: at start the service applies its schema and then runs only
its usual steps; the refresh computes the trailing window again; a history day
is computed again only when the daily check finds its raw event count, or that
of a neighbouring day, changed.

Seen once with a check that is not kept as a test. Inside one process, the
service first ran with the old calculation file (the file as on the
integration branch before this ticket) until history was complete, then with
the new one, on the same totals database. Two identical pieces of work (draw,
undo, redo) were stored, one eight days before the test clock and one in the
trailing window. Creations read through the overview for the month:

| Moment | Old day | Recent hours |
| --- | --- | --- |
| Old rule, everything processed | 2 | 2 |
| New rule, after the next refresh | 2 | 1 |
| New rule, a day later, after the daily check | 2 | 1 |
| New rule, after one more event arrived on the old day and the next daily check ran | 1 | 1 |

The period was reported as processed at each read.

### UI

No file under `cvat/` or `verify/` differs from the integration branch, before
and after the merge. The UI logging suite (`verify/team_analytics_logging.cjs`)
passed on the merged head, 55 tests. It has no case for a redo: the redo event
is CVAT's own, and this ticket shows only that the code sending it is
untouched.

## Supplied boundaries

- Events were rows inserted into the events table, shaped as the stock UI
  writes them. CVAT was the tests' stand-in.
- The stored-hours check replaced the text of one SQL file inside the process
  to stand for the service before the upgrade. No older image was run.

## Not verified

- A redo made in a browser and read back from the events table. That is part
  of the final run (ticket 27).
- The seam 1 suite on the merged head. It rests on the run before the merge
  and on the comparison above.
- The second ClickHouse image (`clickhouse/clickhouse-server:23.11-alpine`).
- An upgrade of a deployment that holds stored totals.
- Whether any deployment holds rows stored as `redone`. The read queries still
  count them as Drawn; they were not changed and not exercised here.

## Independent review, 2026-11-15

An independent review of the counting changes of tickets 19, 21 and 22 found the
redo rule sound: a redo across a refresh window edge gives 2 alignments and 0
creations, a redo is no operation, and a redo of created objects inside a job
still ends a run and nothing else. None of its five findings concerns this
ticket. The review, its findings and what was done about them are recorded in
`docs/evidence/2026-11-14-frame-navigation-hotkeys.md` ("Independent review,
2026-11-15").
