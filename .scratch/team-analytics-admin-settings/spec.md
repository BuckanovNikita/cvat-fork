# Team Analytics: page fixes, settings, administrators-only access, images from scratch

Status: ready-for-agent

Vocabulary follows [`GLOSSARY.md`](../../GLOSSARY.md). This work builds on the full-source
fork described in [`../standard-fork/spec.md`](../standard-fork/spec.md) and changes three of
its decisions: who reads Team Analytics, where the Technical accounts list lives, and how the
fork server image is built. Every decision below was settled by the owner on 2026-11-15, in a
question-and-answer session that followed the owner's request to "fix issues in cvat
analytics".

## Problem Statement

The owner named ten items, here in the owner's framing:

1. The filter bar is uneven: every control must be 36px tall and sit on one centre line.
2. The Project and Annotator chips must become working selectors: searchable, one value each.
3. The "Bounding box operations" card must not scroll sideways at any window width of 1024px
   and up.
4. The page header needs a "Settings" button that opens "Team Analytics settings", a modal.
5. The Technical accounts list must be edited in that modal instead of in an environment
   variable.
6. The page, its API and the settings must be for administrators only.
7. The definitions block at the end of the Overview must become tooltips on the matching terms.
8. The two evidence records of 2026-11-15 (`backend-acceptance` and `full-fork-conversion`)
   must be closed: each open line ends verified or ruled out.
9. Our images must build from scratch: no Dockerfile of ours starts `FROM cvat/*`, and the
   server image runs on Debian 12.
10. The work is delivered on a branch, tracked here, and the owner's stack is recreated on the
    final images at the end.

## Solution

Team Analytics becomes an administrators' tool. An administrator with an organization selected
reads Organization scope; with none selected, Instance scope. Everybody else is refused with a
plain 403, so the page, its API and the settings share one access rule.

The Technical accounts list moves from an environment variable into Postgres: one list for the
instance, stored by user id, edited in a "Team Analytics settings" modal opened from the page
header. The calculation matches technical accounts by user id instead of user name. A change
applies to every past period on the next page load.

On the page, the filter bar gets one height and two real selectors, the operations card fits
its column, and the four definitions become tooltips on the terms they explain. The fork server
image is built from a public Python base instead of on top of CVAT's stock image. The open
lines of the two evidence records are closed on the final image, an independent review follows,
and the owner's stack is installed fresh on the release images.

## User Stories

Numbered for reference from tickets.

Access

1. As an administrator with an organization selected, I see that organization's figures.
2. As an administrator with no organization selected, I see Instance scope.
3. As an owner, maintainer, supervisor, worker or outsider, I am refused (403) on every Team
   Analytics endpoint, in an organization and outside one, and the header has no link to the page.
4. As anyone signed out, I am told to sign in (401).

Technical accounts

5. As an administrator, I open "Team Analytics settings" from the page header, find an account
   by searching for its user name or real name across the whole instance, and add it.
6. As an administrator, I remove an account, including one whose CVAT user was deleted, which
   stays on the list as "deleted account, id N" until someone removes it.
7. As an administrator, after a save the next page load shows every period, past ones included,
   counted with the new list; nothing is recomputed.
8. As an operator, there is no environment variable for the list; after an upgrade the list
   starts empty.

The page

9. As an administrator, every filter-bar control is 36px tall on one centre line, and the
   Settings button, in the header row at the right, is 36px tall.
10. As an administrator, I pick a project or an annotator from a searchable list that starts
    with "All" and includes the "No project" bucket; at Instance scope projects show their names.
11. As an administrator, the operations card never scrolls sideways at 1024px and wider.
12. As an administrator, hovering or focusing Session, Working time, Time per operation or Model
    on the Overview shows its definition.

## Implementation Decisions

Access

- The organization rule is deleted from the app's policy; the rego keeps one rule, the
  administrator check. The 403 body `{"error": "organization_required"}` no longer exists, and
  the `admin` flag leaves the scope, the cache key and the status answer. The page shows itself
  only to the admin group. This replaces stories 1, 2 and 5 of the standard-fork spec.
- Issue 19 of `.scratch/team-analytics/` (any account can move the cutover or add its own
  figures) is closed as `wontfix`: accounts can still send such events, but only administrators
  read the figures, and the owner accepts the risk.

The Technical accounts list

- One instance-wide list in a new model `TechnicalAccount` (`user_id` primary key without a
  foreign key, `user_name` as the last known name, `updated_date`), the app's first model and
  migration.
- A deleted user stays on the list until removed. A change is retroactive: membership is applied
  when figures are read, not when totals are stored.
- `TEAM_ANALYTICS_TECHNICAL_ACCOUNTS` is removed. The test stack sets its list through the API.
- The worker reads the list in its read job after it reads the totals generation and passes the
  ids into the core as a value, so the core stays free of Django. A save commits first and then
  advances the generation. In that order a save between the two reads cannot store an answer
  computed on the old list under the new generation.
- The 31 SQL predicates (in 14 read files) that match technical accounts switch from
  `user_name` to `user_id` (`{technical_accounts:Array(UInt64)}`); all five totals tables carry
  `user_id`. The `technical_accounts` count in the answers stays.

API contract

All under `/api/team-analytics/`, administrators only (403 for everyone else, 401 signed out),
answered by the API process from Postgres, never through the read queue, with
`Cache-Control: no-store`. The view set stays out of the OpenAPI schema.

1. `GET settings` returns `{"technical_accounts": [{"user_id": 12, "user_name": "ta-bot",
   "deleted": false}, ...]}`, ordered by `user_name` then `user_id`. `user_name` is the live
   user's current name; for a user that no longer exists it is the last known name and
   `deleted` is `true`.
2. `PUT settings` with `{"technical_accounts": [12, 40]}` (the whole list, as user ids) returns
   the `GET settings` body after the save. A bad body gives 400 `{"error": "bad_request",
   "detail": "<sentence>"}`. The rules: a list of positive integers, no duplicates, at most 1000;
   an id not already listed must be an existing user; an id already listed is kept even if its
   user is gone. The save commits, then advances the generation, and logs who added and removed
   which ids.
3. `GET settings/users?search=<text>` returns `{"users": [{"id": 12, "username": "ta-bot",
   "first_name": "", "last_name": ""}, ...]}`: at most 20 users of the whole instance (any
   organization or none, active or not) whose username, first name or last name contains the
   text, case-insensitive, ordered by username. An empty or absent `search` gives the first 20 by
   username; a `search` longer than 150 characters gives 400. It exists because CVAT's
   `/api/users` is narrowed to the selected organization even for an administrator.
4. `GET project-names?ids=4,8,9` returns `{"names": {"4": "Alpha", "8": "Beta"}}`: the names of
   the existing projects among the ids, whatever their organization; unknown ids are absent. At
   most 500 ids, each a positive integer; otherwise 400. The owner did not ask for it; the
   project selector needs it. Confirmed needed on a stack on 2026-11-15: with no organization
   selected, CVAT's `/api/projects` returned an administrator 1 project of 45 (the
   personal-workspace ones only), so the page could not name projects at Instance scope.

The read answers (`status`, `overview`, `trends`, `list`, `details`) keep their shapes.

The page

- Filter bar: every control 36px, border-box, on one centre line. The selectors are a
  hand-written combobox in the bar's own style (button, search input, listbox), "All" first,
  one value each. Options load when the dropdown opens, from the existing list endpoint, and are
  kept per organization and period. A period that is not processed yet offers "All", the current
  value and a "not processed yet" line. Clicking a card row still sets the filter.
- Operations card: five columns (Operation, Boxes or Objects, Avg time, Total time, Share), with
  the hotkey and mouse split on a second row under each operation, and a table class of its own
  with no minimum width. The tightest width is about 388px, just after the grid adds a column
  (near a 1356px window), not at 1024px. The creation-methods card also scrolls; it is reported,
  not changed.
- Definitions: the four texts keep their glossary wording and move into tooltips that open on
  hover and on keyboard focus, on the Overview only. The block at the end of the Overview goes;
  this reverses ticket 24 of `.scratch/defect-fixes/`.
- Settings: a 36px "Settings" button with a gear at the right of the header opens an antd
  modal with the list, a remote-search picker on action 3, and one sentence saying a change
  applies to all past periods on the next load.

Images

- `Dockerfile.server` becomes a full build on `python:3.12-slim-bookworm`, mirroring the stages
  of upstream's `Dockerfile`, which stays untouched. Pulled images are pinned by digest:
  `python:3.12-slim-bookworm`, `rust:1.85-slim-bookworm`, `golang:1.27.2`. Stock
  `cvat/server:v2.82.0` leaves the approved list, and the calculation suite moves to the fork
  image. The UI image keeps upstream's `Dockerfile.ui`.
- Known deviation: Debian's `supervisor` package brings Debian's Python 3.11 beside the image's
  3.12; the build checks that every supervised process runs 3.12, and a new ADR, superseding
  ADR 0004, records it.
- Until delivery every build uses work tags (`-fork-wip`), and verification stacks use their own
  namespace and port, so the owner's running stack, which never pulls its images, is not reached.

Every file the fork adds or changes inside upstream's directories (the app's `models.py`,
`migrations/`, `serializers.py`, the header, and so on) joins the list of changed upstream files
in `docs/fork-specification.md`.

## Testing Decisions

Verification runs in this order:

1. Light, any time: `prek run --all-files` (linters, type check, policy tests, the node suites).
2. The server image built from scratch under the work tag, and a one-time comparison with the
   present image.
3. The calculation suite on the work image (`verify/team_analytics_backend.sh`).
4. The UI image under the work tag.
5. A stack in its own namespace: `preflight`, a fresh `up`, a second `up`, `check-fixes`,
   `check-cross-org`, `check-settings`, the browser steps, `check-isolation`, `check-load`,
   `check-review`, `check-analytics-off`.
6. The evidence extras on the same stack (ticket 09), the Redis failure last, then `down`.
7. A fresh clone with dependencies installed from the locks, passing the pipeline.
8. Independent review and fixes; then the pipeline, the calculation suite if the app changed,
   both image builds and at least `preflight`, `up`, `check-settings`, `check-review` again.
9. Both images built under the release tags; the owner's stack removed and installed fresh on
   them; the page looked at as an administrator; the branch pushed, not merged.

The final report states what each check established, what stayed unverified, and names any card
other than the operations card that still scrolls sideways.

## Out of Scope

- Multi-select filters: each selector takes one value.
- Redesigning other cards that scroll sideways; they are reported.
- A release merge or a source version update.
- Changing the `cvat/postgresql` and `cvat/clickhouse` images. They carry the `cvat/` name but
  are not CVAT's software, are pulled unmodified, and are no base of a Dockerfile of ours.
- The UI image's Alpine nginx runtime from upstream's `Dockerfile.ui`.
- A fix that stops client events moving the cutover or adding figures (issue 19, accepted risk).
- Issue 01 of `.scratch/task-progress/`.

## Further Notes

The failed jobs seen at worker start on the owner's stack match rq 1.16.0's
`clean_intermediate_queue` (a starting worker fails a job another process just dequeued; the job
still runs). Ticket 09 confirms this from the pinned source and the job's `exc_info` and records
it as an upstream limit, without changing the pin. (2026-11-16: confirmed from the pinned source
and the worker's log order; the job's record had no `exc_info` to cite, because the scheduler
recreates it every minute. See `docs/evidence/2026-11-16-open-lines-closed-and-admin-settings.md`.)

The trust model and the correction procedure for a wrongly early event stay as documented in
`docs/fork-specification.md`. `ta-bot` is only the test stack's example technical account.
