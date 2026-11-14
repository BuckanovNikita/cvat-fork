# The large-team volume through the events API on the test stack, 2026-11-15

Ticket 26 of the defect fixes (plan row V5b, spec default (f)). The volume of the final run
(`verify/team-analytics-stack/final_run.py`, 100 annotators, 40 projects, ten weeks) used to
be inserted straight into ClickHouse, all of it, under made-up user ids. Now the annotators
are real CVAT accounts. Each annotator signs in and sends the current week itself, through
`POST /api/events` and Vector. The older weeks are still inserted directly; the first part
below says why.

All runs were made on the running stack (namespace `cvat-ta-it-<user>`, server image
`4b38c649ae96`, service image `42d4bb9ab97e`, UI image `310e9bbc6a47`) on 2026-11-14 between
22:45 and 23:07 UTC (2026-11-15 local time). The organization `ta-org-v` on that stack
already held a direct load from before this ticket, so the new load went into another
organization, `ta-org-w` (`TA_VOLUME_ORG=ta-org-w`), owned by `ta-owner-v` as `ta-org-v` is.

## What the events API does with old timestamps (live)

How the stock server takes client events (`cvat/apps/events/serializers.py` and
`utils.py` in `cvat/server:v2.82.0`, read in a container with no network): the request
body carries its own `timestamp`, the client's send time. The server computes
`time_correction = receive time - that timestamp` and adds it to every event of the body.
It sets the user and organization fields from the session, whatever the event says. It
accepts only client scopes from source `client` and nothing from any other source.

Five probes, sent as `ta-outsider` (member of nothing) as `debug:info` events without a job,
one event per request, and read back from the `events` table 15 s later:

| Probe | Event time sent | Request time sent | Event time in ClickHouse |
| --- | --- | --- | --- |
| a | 2026-10-15 22:45:33.582 (30 days back) | 2026-11-14 22:45:33.582 (now) | 2026-10-15 22:45:33.611 |
| b | 2026-10-15 22:45:33.582 (30 days back) | the same 30 days back | 2026-11-14 22:45:33.643 (now) |
| c | 2020-01-01 08:00:00.000 | now | 2020-01-01 08:00:00.028 |
| d | 2026-09-05 22:45:33.582 (ten weeks back) | now | 2026-09-05 22:45:33.610 |
| e | 2026-11-15 22:45:33.582 (a day ahead) | now | 2026-11-15 22:45:33.609 |

Each request was answered `201` in about 32 ms, and the response already carried the moved
time. Every probe also sent `user_name` `spoofed-name` and `user_id` 1; each row arrived
with `ta-outsider` and its real id. The payload arrived unchanged.

So the API **accepts old timestamps but does not keep them unchanged**: it neither refuses
nor clamps them, and it moves every event by the time between the request's own timestamp
and its arrival. With the request stamped at sending, that is the transit time (26 to 43 ms
in the load below); with an old request timestamp the event lands at the time it arrived.

Four more requests, each with one event, all answered `400`, and nothing arrived:

| Event | Answer |
| --- | --- |
| `create:shapes`, no source | `Event scope **create:shapes** is not allowed from client` |
| `create:shapes`, source `server` | `... is not allowed from server` |
| `send:working_time`, source `server` | `... is not allowed from server` |
| `debug:info`, source `server` | `... is not allowed from server` |

The working time (`send:working_time`) and the saved boxes (`create:shapes`) cannot be sent.
CVAT writes them itself: the working time from the client events of a request, the saved
boxes when annotations are saved, stamped with the time of the save. A saved box cannot be
dated back. **The older weeks therefore stay direct inserts** (spec default (f)); only the
current week goes through the API.

A side effect of the probes, cleaned up: probe c made 2020-01-01 the earliest event of the
instance, and within about a minute the service had walked its processed history back to
it (2 445 more days in `team_analytics.history_days`). The five probe rows were deleted from
`events` right after they were read (`ALTER TABLE events DELETE`, the probe's marker only);
the earliest event is again 2026-09-11. The recorded days stay in the service's table; they
lie before the first event and are not read. Probes for this stack should stay inside the
ten weeks.

## How the load goes now

`run.sh load-volume` (also the first step of `run.sh check-final`):

1. The 100 accounts and their memberships, as `worker` of the volume organization, through
   the stack's `seed_users.py`, with JSON that `final_run.py volume-accounts` prints. The
   organization is created there when it is missing, with `ta-owner-v` as owner.
2. As `ta-owner-v`: the 40 projects (now with a label `box`), one task per project with one
   single-frame job per annotator of that project, each job assigned to its annotator.
3. The older weeks (900 sessions, 6 300 rows) inserted directly, with the annotators' real
   user ids and jobs. Each session's `load:job` carries the load's anchor date.
4. The current week: each of the 100 annotators signs in with its own account, posts its
   session's client records (`load:job`, the draws, the input summary) in one
   `POST /api/events?org=...`, and saves its boxes in its job with
   `PATCH /api/jobs/<id>/annotations`. CVAT writes the working time and the saved boxes.
5. A wait until every record of the load is in the events table, then a check of the
   current week record by record (below).

A later run reads which sessions the events table holds and loads only the missing ones; a
box is saved only into a job that has none. An organization that holds a load from before
this ticket (sessions without an anchor) is refused before any account is made.

## Live outcomes

### Sizing, on three annotators first

`TA_VOLUME_ORG=ta-org-w run.sh load-volume 3`: accounts 22 s, layout 105 s (40 tasks with
their images and 100 jobs), then three annotators: sign-in 0.21 s each, the events request
31 ms (about 1.6 KB), the save 54 ms. No request was refused or throttled. Their records
were all in ClickHouse when read about a minute later, as sent:

- the client records at the planned times plus 26 to 30 ms, 30 000 ms apart;
- one `send:working_time` per session, written by CVAT (its payload carries `request`):
  60 000, 90 000 and 120 000 ms, the generator's 30 s per draw;
- one `create:shapes` per save, 2, 3 and 4 rectangles, stamped at the save.

At these sizes the load needs no throttling or parallelism: one annotator after another
takes about a third of a second, and the stack's other pods were not starved.

### The full load

`TA_VOLUME_ORG=ta-org-w run.sh load-volume` right after (97 annotators left):

```
[ta-stack] volume: accounts ready after 21 s
  ta-org-w: anchor 2026-11-14; 3 of 1000 sessions already loaded
  layout: 40 projects, 100 jobs, one per annotator (5 s)
  older weeks: 6300 rows of 900 sessions inserted directly
  current week through the API: 97 annotators posted their session, 87 saved boxes, in 35 s (mean/max {'login_s': '0.214/0.352', 'post_s': '0.035/0.087', 'post_bytes': '1640.010/2310.000', 'save_s': '0.059/0.103'})
  all records in the events table 4 s after the last request: ...
  current week in the events table: 100 sessions as sent, gaps unchanged, CVAT's working time and saved boxes as planned; record time moved by 26..43 ms (receive minus send time)
  volume loaded in 44 s
[ta-stack] volume: done after 65 s
```

Ten annotators save nothing: their only draw is a polygon, and the generator counts saved
rectangles only. The counts in the events table, current week / older weeks:

| Scope | Current week (through the API) | Older weeks (direct) |
| --- | --- | --- |
| `load:job` | 100 | 900 |
| `draw:object` | 300 | 2 700 |
| `debug:info` (input summary) | 100 | 900 |
| `send:working_time` | 100, all written by CVAT | 900 |
| `create:shapes` | 90 rows, 290 boxes, all written by CVAT | 900 rows, 2 610 boxes |

How long the load takes from nothing, from these two runs: accounts about 20 s, layout about
105 s, the older weeks' insert a second, the current week about 36 s, arrival 4 s: about
three minutes.

### A second run

`TA_VOLUME_ORG=ta-org-w run.sh load-volume` again: `1000 of 1000 sessions already loaded`, no
annotator posted or saved anything, 34 s in all (the accounts step and the reads). The
volume's rows in `ta-org-w` stayed at 6 990 (6 300 + 690), for 100 users. A run against
`ta-org-v` stopped before making any account:

```
seed check failed: ta-org-v holds 1000 volume sessions of a direct load from before ticket 26; load into another organization (TA_VOLUME_ORG) or remove them first
```

### The figures of the current week

`TA_VOLUME_ORG=ta-org-w run.sh check-volume`:

```
  current week in the events table: 100 sessions as sent, gaps unchanged, CVAT's working time and saved boxes as planned; record time moved by 26..43 ms (receive minus send time)
  history processing: ready after 0 s
  volume figures: ready after 3 s
  week: 100 annotators, 40 projects, 100 sessions, 9000000 ms, 300 drawn, saved 290, hotkeys 697, mouse 100, canvas 600
  trends: 10 weeks with work match the loaded events; two annotators compared
  list: 100 annotators; details by project: 40 rows
```

These equal the generator's expected values, the same as the direct load's in
`2026-11-14-team-analytics-final-run.md`. Going through the server changed no figure. It
did change two things about the records, neither of which a figure reads:

- CVAT stamps a session's working time at the session's first record, the generator at its
  last. Both lie in the same session; the figures are per day and per week.
- The saved boxes are stamped at the save (2026-11-14 22:57 to 22:58 UTC), not a second
  after the session's last draw (2026-11-13). They stay inside the week; the trends read the
  working time.

The first `check-volume` failed on the trends: the older weeks had been inserted after the
service had computed those days, for `ta-org-v`'s load. The service would have counted them
again at its daily check, due 2026-11-15 21:19 UTC. In its place the two statements of that
check (`control/history_changed_days.sql`, then `control/history_mark_pending.sql`) were run
by hand: 34 days marked, the older weeks' days and their neighbours, and the probe's. The
service computed them again by itself; the second `check-volume`, 30 s later, passed. A
fresh stack does not meet this: its load comes before any of those days is computed.

### The whole final run

`TA_VOLUME_ORG=ta-org-w run.sh check-final`, 23:01 to 23:06 UTC, passed. Its volume step was
a third run of the load: `1000 of 1000 sessions already loaded`, nothing sent, 32 s. Then
the real UI's part (ticket 25's detector part unchanged), the volume's figures as above,
every account against every endpoint (`ta-admin`, `org=ta-org-w`: 200), and the page:

```
  page loads: 100 active annotators, 8 + "92 more" annotators, 8 + "32 more" projects; height 3387 px (ta-org-c: 3214 px); no overflow
  filters: project -> 3 annotators, + annotator -> 1 (?period=week&project=62&org=ta-org-w&annotator=29); cleared -> 100
  full view: 100 annotators listed, no overflow; "Back to overview" returns
  trends: two lines, legend ["ta-volume-annotator-001-","ta-volume-annotator-002-"]
[ta-stack] final run passed
```

The trend comparison now names the two annotators by their real CVAT user ids.

## Supplied boundaries

- The annotators' records are written by the load, not by a browser. The current week
  goes through the same request the UI makes (`POST /api/events` with the session's cookie
  and CSRF token), but its contents are the generator's.
- The older weeks are direct inserts, as before.

## Not verified

- A volume load from an empty namespace: ticket 27's final run.
- A load that crosses midnight UTC: the anchor is fixed by the first run and kept, so
  it should not move, but no run crossed it.
