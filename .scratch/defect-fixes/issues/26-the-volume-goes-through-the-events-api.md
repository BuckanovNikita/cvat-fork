# 26: The volume goes through the events API

**What to build:** The large-team data of the test stack reaches ClickHouse the way real work does, through CVAT's events API and Vector. Until now it was inserted straight into ClickHouse. The current week goes through the API; older weeks do too only if the API accepts old timestamps, which is not known. That is a default the owner was not asked about. See "Testing Decisions" in the spec (`../spec.md`).

**Blocked by:** 08 (The stack runs on the fork server image and the in-tree chart).

**Status:** resolved

- [x] It is found out and recorded what the events API does with events that carry old timestamps.
- [x] The current week of the volume, one hundred annotators, is sent through the real events API in each annotator's own session and arrives through Vector. None of it is inserted directly.
- [x] Older weeks go through the API if it accepts them unchanged; otherwise they stay direct inserts and the evidence says so.
- [x] The figures of the current week equal the generator's expected values, as before.
- [x] A second run on the same stack does not load the volume twice.
- [x] How long the load takes is recorded in the dated evidence.

## Comments

2026-11-15: All six were shown on the running stack, in organization `ta-org-w`
(`TA_VOLUME_ORG=ta-org-w`). That stack's `ta-org-v` still holds the direct load from before
this ticket, and the load refuses an organization like that. The evidence is in
`docs/evidence/2026-11-15-volume-through-events-api.md`.

The API accepts old timestamps, but not unchanged: it moves every event by the time between
the request's own timestamp and its arrival (26 to 43 ms here). It refuses
`send:working_time` and `create:shapes` from any source, and CVAT stamps saved boxes with
the time of the save. So the older weeks stay direct inserts, and only the current week
goes through the API (default (f)).

The annotators are real accounts made by `seed_users.py`. Each one signs in, posts its
session and saves its boxes in its own job. The current week's figures equal the
generator's.

The older weeks' trends needed the service's daily recount. Those days had already been
computed before the second organization's load, so I ran the recount by hand with the
service's own two statements. A fresh stack does not run into this.

A plain `run.sh check-final` on this stack (in `ta-org-v`) now stops at the volume step.
That is on purpose.

2026-11-15: Resolved on `feat/team-analytics-page` by merge `5df1b412`; evidence `docs/evidence/2026-11-15-volume-through-events-api.md`. A load from an empty namespace is still to be seen in ticket 27's final run.
