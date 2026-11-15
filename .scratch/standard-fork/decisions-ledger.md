# Team Analytics: what was decided or changed against the first plan

**Note, 2026-11-14:** the plan this ledger was compiled for (a conversion to a
standard full-source fork) was dropped by the owner the same day and its file
deleted; it is in history up to commit `fb3148e`. The column "Under the new
plan" and the rows that argue for that plan (O1 to O3) describe it and no
longer say what will happen. What is planned now is in
[`../defect-fixes/plan.md`](../defect-fixes/plan.md).

**Note, 2026-11-15:** the owner took the conversion up again and decided it
([ADR 0005](../../docs/adr/0005-a-full-source-fork-joined-to-upstream-history.md),
[ADR 0006](../../docs/adr/0006-team-analytics-inside-the-backend-with-reads-on-a-worker.md));
the work is specified in [`spec.md`](spec.md) and ticketed under `issues/`.
The column "Under the new plan" again describes what is planned, with three
differences from the first draft: the reads run on a dedicated worker and not
in the API process (rows S1, S12); the defect fixes of 2026-11-14 have already
settled rows S9, S13, S15, Q6, Q8, Q9, A4, L2, L10, P9 and P10 and the
verification gaps V4, V5 and V7; and the repository joins upstream's history
by a merge, with no rewrite of `main`.

Compiled 2026-11-14 for `plan.md`. "The first plan" is
`.scratch/team-analytics/spec.md`, its eighteen tickets,
`docs/design/team-analytics/`, ADRs 0001 to 0003 and `GLOSSARY.md` as they
stood at commit `f492c65`, when implementation began.

## How it was compiled

Three passes, merged here:

- the design sessions with the owner and the session that put the review-fix
  questions to the owner;
- the implementation session: the orchestrator's messages and briefs, and the
  final report of every implementer, merger, fixer and reviewer;
- the written record: the implementation notes, ticket comments, evidence
  files, fork documents and every commit of `main..feat/team-analytics-page`.

This file is the consolidated view: 105 rows, one per decision or group
of closely related decisions. The row-level ledgers (about 320 rows before
merging, with line citations) and the three upstream maps behind the plan are
kept with the implementation notes outside this repository, as files 30 to 32
and 40 to 42 there. They hold local paths and session identifiers and are not
committed.

Limits: subagent transcripts were read for their final reports only, so a
choice an implementer made and did not report is not here. Agent reasoning is
not stored in transcripts; why something was chosen is known only from what
was written down.

## How to read it

- **Who.** *owner*: the owner's own statement, or a choice against the agent's
  recommendation. *owner approved*: an agent proposed it and the owner said
  yes. *disclosed*: an agent decided, said so, and got no answer. *agent*: the
  orchestrator (O), an implementer (I, with the ticket), or a reviewer (R)
  decided; the owner was not asked.
- **Source.** A commit on `feat/team-analytics-page`, or: `spec`; `FS` =
  `docs/fork-specification.md`; `EV` =
  `docs/evidence/2026-11-14-team-analytics-final-run.md`; `N` = the
  implementation notes outside the repository; `DS` = the design session of
  2026-11-13, not in the repository.
- **[R]** marks a rule added during the two review rounds that the first plan
  does not contain.
- **Under the new plan.** *goes away*: the thing it concerns is deleted.
  *carries over*: moves with the code unchanged. *changes*: still exists,
  differently. *owner to decide*: never ratified, and the move is the moment
  to settle it. *open*: unfinished, and not addressed by the new plan.

One fact frames everything below: in the implementation session the owner
sent three messages (start, "resume", and a request for a link to the running
stack). Every "say if you want this changed" from the orchestrator went
unanswered, and the eighteen review-fix questions put to the owner in a
separate session were never answered. Rows marked *agent* or *disclosed* are
therefore unratified.

## O. Owner constraints and who shaped the architecture

| # | Decision | First plan | What happened | Who | Source | Under the new plan |
| --- | --- | --- | --- | --- | --- | --- |
| O1 | The backend stays the stock image | spec "Shape of the solution", "Out of Scope"; ADR 0002 | Never said by the owner and never put to them as a choice. It was the starting premise taken from the overlay layout on `main` (no backend in the tree). The out-of-scope line exists only in the spec file | agent premise | DS; `74d5c53` | reversed |
| O2 | Where the figures come from | ADR 0001: a separate thin service | The owner asked for "possibly a dedicated backend endpoint". The agent answered with a separate service; an endpoint inside CVAT was never offered and is not among ADR 0001's options | owner asked, agent reshaped, owner approved | DS; `8da354e` | the new plan delivers what was asked |
| O3 | Dropping the service | ADR 0001 rejects the Grafana route | The owner asked whether the service could be dropped in favour of the export or raw queries. It stayed only because Grafana could not meet O4 | owner raised it | DS | the service is dropped; O4 is met by CVAT's own permission system |
| O4 | Access | design "Purpose and access" | Two hard requirements, both stated against the alternative: organizations must not see each other's figures, and owners and maintainers get in by role, not by individual grant | owner | DS; `46fff57` | carries over |
| O5 | Coupling and failure isolation | design; ADR 0001, ADR 0002 | The only architectural constraint the owner volunteered: low coupling with existing functionality, reuse of existing API methods, and a failure of the feature must not break core functions | owner | DS; `46fff57` | carries over and must be proven again (plan section 6) |
| O6 | Kubernetes only, newest CVAT only, test infrastructure as part of the work | ADR 0003 | Stated twice, both times against the agent's recommendation of a Compose run | owner | DS | carries over |
| O7 | Production | ADR 0003: air-gapped production out of scope | The owner's only statement: production is air-gapped, forget about it, all work is here. The owner did not require the feature to cross the air gap | owner (scope) | DS | owner to decide (plan D3): a fork server image changes what production would take |
| O8 | Stored totals, some delay acceptable | ADR 0001 | The owner's goal was incremental totals with tolerable delay. The trailing-window redo, hourly units and the ten-minute interval were the agent's mechanism, approved | owner (goal), owner approved (mechanism) | DS | carries over |
| O9 | Upstream Helm chart for the test stack | ADR 0003 | The owner first accepted the recommendation of own manifests, then reversed it in favour of the upstream chart | owner | DS | carries over; the chart is now in the tree |
| O10 | How the chart is obtained | spec "Test stack": downloaded into a cache, not added to the filtered import | Decided by the agent so the import's recorded identifiers would not change. The only decision that touched the subtree arrangement; the owner never discussed that arrangement | disclosed | DS; spec | goes away |
| O11 | Who is an administrator; scope of each role | ADR 0001; design | Admin group, not only the superuser flag. Admins: a named organization or the whole instance. Annotators: no access, not even to their own figures | owner approved | DS; `46fff57` | carries over (`privilege == admin` in the policy input) |
| O12 | Addresses | ADR 0001: nothing may start with `/analytics` | An agent finding (that prefix is routed to Grafana), approved | owner approved | DS | carries over; `/api/team-analytics/` and `/team-analytics` both comply |
| O13 | Totals database | spec "Stored totals": own database on the same ClickHouse server, with CVAT's account | Approved. A reviewer later noted that this account can write to the events table and create databases, and did not count it as a finding | owner approved; R | DS; N | carries over, including the note |
| O14 | Spec decisions listed to the owner as "not discussed" | spec | Identity answers cached for a minute and refusal when CVAT is unreachable; state kept in the page address; the input summary sent at most once a minute; part-hour time zones (Q11). The owner replied only about the test seams | disclosed | DS; spec "Further Notes" | the first goes away; the rest carry over |
| O15 | The review-fix decisions | — | Eighteen questions on the first fix round were put to the owner. None was answered; the fixes had already been implemented when they were asked | agent (O) | DS; `401576e` | owner to decide where a row below says so |
| O16 | How the work is done | — | Standing preferences the owner stated: design before code; prototype first with sign-off; check claims against the upstream source; issues as local markdown, tracked although the repository is public | owner | DS; `f492c65` | carries over |

## S. Service

| # | Decision | First plan | What happened | Who | Source | Under the new plan |
| --- | --- | --- | --- | --- | --- | --- |
| S1 | Process model | spec: the service schedules the refresh; several replicas possible | Every replica is web server and refresher in one process: schema applied at start, refresh loop in a daemon thread, no separate worker | agent (I 02) | `a003b89`, `55dde47` | goes away: DRF views on the server, the job on an RQ worker |
| S2 | HTTP server | no dependency beyond the stock image | Python's standard-library server, HTTP/1.1 keep-alive, GET only, no health endpoint, TCP probes | agent (I 02) | `a003b89` | goes away |
| S3 | [R] Request bodies | spec: read-only service | A body on a kept-alive connection was parsed as a second request. Fixed: read and dropped up to 64 KiB, otherwise the connection is closed | agent (R, O) | `5cb3705` | goes away |
| S4 | [R] Shutdown | silent | On SIGTERM the service finishes the step in progress (up to 25 s) so the lease is released | agent (I 18) | `bfffb23` | goes away; a killed worker is covered by the lock's expiry and by unmarked rows staying invisible |
| S5 | Image and manifests | spec "Images and manifests" | Image built from the stock server image with code copied in; ConfigMap, Deployment (one replica), Service, an Ingress that was never applied; the backend address assumes a release named `cvat`; the pod restarts once or twice at install until ClickHouse is up | agent (I 03) | `ceab5d5`, `4ba6b26`; N | goes away; the bootstrap must still tolerate ClickHouse not being ready |
| S6 | Configuration | environment variables | `TEAM_ANALYTICS_*` for the technical accounts, intervals, window, look-back, ClickHouse and CVAT addresses, listen address; the lease length is a code constant | agent (I 02, 03) | `4ba6b26`; N | changes: Django settings; the CVAT and listen settings go away |
| S7 | One refresh at a time | spec: also with several replicas, mechanism not named | A lease row in ClickHouse; the earliest live claim wins after a short settle time | agent (I 02) | `a003b89`, `2566751` | goes away: a Redis lock inside the job |
| S8 | [R] Lease rules | silent | Reworked twice in review: released on every failure, renewed while a step runs, a replica that cannot prove it holds the lease stops before its next write, an expired claim is never revived, the wait for a hanging renewal is capped at 2 s | agent (R, O) | `ec8512e`, `a130954` | goes away; the idea of a deadline check before each write is kept |
| S9 | A replica killed mid-step | silent | Blocks every refresh until the 30-minute lease expires | known limit | FS | changes: bounded by the lock's expiry, which is ours to choose |
| S10 | Replacing an hour | spec: totals replaced as whole units | Rows are written under a new version, a marker table names the live version of each hour, superseded rows are deleted afterwards. Eleven numbered schema files, applied by the service | agent (I 02) | `a003b89` | carries over, minus the lease table |
| S11 | [R] ClickHouse client | silent | One shared client without a session, SQL text read once. The measured gain was small and its test passes on old and new code | agent (R) | `e7da85e` | carries over |
| S12 | Latency and memory | spec: a year loads as quickly as a week | An overview runs about thirteen queries in sequence, about 2 s in the measurement. A ClickHouse capped at 2 GiB runs out of memory at about twelve concurrent overviews during a refresh. Reported, not addressed | known limit | N | carries over and matters more: the reads will occupy CVAT's API workers (plan section 6) |
| S13 | Unprocessed periods | spec stories 94 and 95: a period is offered only when all of it is processed | The service returns the partial figures flagged `processed: false`; only the page withholds them. A direct API caller reads partial figures | agent (I 15), accepted (O) | `330c874`, `52e7d1d` | owner to decide: under `/api/` the endpoint should withhold them itself |
| S14 | The worker loop | spec: refresh every ten minutes, history newest first, a daily recount | One prioritised step: a due refresh, else one history day, else the daily check; fast retry after a failure. The daily check is one count query over all days. A changed day also recomputes its two neighbours | agent (I 15) | `943a7dd`, `6afc9f2` | carries over as the job's step; how often the job fires is new |
| S15 | Refresh window under a day | spec: 48 hours | If the window is configured below 24 hours, today's earlier hours count as processed without being computed | known limit | N | carries over |
| S16 | Endpoint contracts | spec lists five endpoints in prose | Invented in full: `details` (paging, search, ids), `list` (three row kinds, one wide row), `trends` (limits, zero rows for foreign ids, per-bucket flags), the overview's sections and filter echo, the status history block, `shapes` defaulting to all | agent (I 05 to 17) | `d243bbb`, `96bf27d`, `530fcb0`, `0d3dab3` | carries over; the address prefix changes |
| S17 | Errors | silent | 401, 403 `forbidden`, 403 `organization_required`, 503 `cvat_unavailable`, 400, 500, as `{"error": code}`; `Cache-Control: no-store` | agent (I 02, 04) | `ee7f671` | changes: DRF error bodies; no 503; an unknown organization is a 404 from CVAT's middleware |
| S18 | [R] Parameter validation | silent | Identifiers, pages, id lists and months take ASCII digits only; a month before 1970 is a bad request | agent (R) | `2868e00`, `d907813` | carries over as query serializers |
| S19 | Technical accounts | spec story 58: a configured list | Matched by user name when figures are read, so the list can change without recomputing history, and a renamed account changes class | agent (I 12) | `486f4f2` | carries over; matching by user id becomes possible |

## Q. Calculations

| # | Decision | First plan | What happened | Who | Source | Under the new plan |
| --- | --- | --- | --- | --- | --- | --- |
| Q1 | Gaps the plan left open | exploration found 26 | Settled by the orchestrator before any ticket started: counts come from the `count` column; a legacy drag is one alignment; sessions are stored per organization plus one instance-wide set; a gap across a project switch belongs to the later project; Year is twelve months shown as weeks; trends are twelve buckets ending with the current one | agent (O) | N; `a003b89` onward | carries over |
| Q2 | Shares of working time | glossary: every breakdown adds up to working time | The denominator is operations plus Other, with Other never below zero. Shares add up to 100 % of a total that can exceed working time on a narrow slice | agent (O) | N; `1d3275a` | carries over |
| Q3 | Time per operation | spec: time since the previous client event | Counted from the previous client event even when that event is outside a job | agent (I 08) | `7a16e1c` | carries over |
| Q4 | Alignment | spec: consecutive adjustments of one box; another object or a frame change ends it | Added: a pause over 300 s ends it; any operation ends it, also on the same object; the refresh reads 300 s past its window; a run that began more than 300 s before a window is untimed there | agent (I 09) | `c29c507` | carries over |
| Q5 | Sessions | spec: read five minutes before the window | Reads from a day before to 300 s after; a session is stored whole in the hour it ends; one longer than a day is cut; a late event can leave an older row until that day is recounted | agent (I 06) | `ed579b0` | carries over |
| Q6 | Redone creations | spec story 44: an undone creation still counts | Counted; given the method of the same annotator's last creation in the job within 300 s, else Drawn. A redo has no shape type upstream, so it counts only under All shapes and as one object | agent (O, I 08, 11) | `9182ecb` | carries over |
| Q7 | Mixed selections | silent | The time of an event touching several kinds is split between boxes and other shapes by object count | agent (I 09) | `c29c507` | carries over |
| Q8 | Model | spec: boxes saved by technical accounts plus detector records | Under All shapes every object a technical account saved counts. Totals by annotator and by project differ. Model is left out of trends. A project touched only by a technical account is missing from the details table | agent (I 12, 14, 16) | `486f4f2`, `530fcb0` | carries over |
| Q9 | [R] Cutover | a legacy period is one with no shape-tagged row in scope | Replaced during review: the cutover is the first shape-tagged hour on the instance; a period before it is legacy, one that holds it is partly legacy, an empty period is neither. It is found once by a single query over all earlier raw events, stored, and never moves. Three recorded limits: none exists while only untagged or 3D work is stored; periods read as legacy right after an upgrade; a wrong value is corrected only by deleting the row. The single query goes against the spec's rule of no long-range query and its cost was not measured | agent (O, R) | `08b3803`, `f241f98`, `2c900d3`, `09fe818`; FS | carries over; owner to decide (plan D11) |
| Q10 | Legacy flag per card | one flag per period | Each read decides over the rows it sees, so the details table can disagree with the overview. Counted keyboard input is shown in a scope flagged legacy | agent (I 13, 16) | `9ceca5f` | carries over |
| Q11 | Part-hour time zones | spec "Further Notes" | Days are assembled from whole UTC hours, so such a viewer's day boundary is off by the part hour. Marked "not discussed with the owner" and never answered | disclosed | spec | owner to decide |

## A. Access

| # | Decision | First plan | What happened | Who | Source | Under the new plan |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | How a caller is identified | spec: ask CVAT with the caller's credentials | Three HTTP calls per request (`/api/users/self`, `/api/organizations`, `/api/memberships`) with the forwarded cookie or `Authorization` header, sent without an `Accept` header because CVAT answers that with 406 | agent (I 02, 04) | `95d49d0`, `ee7f671` | goes away |
| A2 | Caching | spec: at most a minute; refuse when CVAT is unreachable | A cached answer is also served while CVAT is down. A removed member keeps access for up to a minute | agent (I 04) | `ee7f671` | goes away: the check is made on every request |
| A3 | "Select an organization" or "not available" | spec: both are refusals | An extra membership lookup decides between them; [R] asked once per reading role so paging cannot hide a membership | agent (O, I 04, R) | `ee7f671`, `d2e4463` | changes: decided in the view or by the page; the policy cannot return a reason |
| A4 | Status and organizations | spec: the organization filter applies to every query | Status shows the first event day and day counts of the whole instance, and the instance-wide cutover, to an organization maintainer. A reviewer raised it; the orchestrator recorded it as accepted. The owner was asked and did not answer | agent (O) | EV; FS | owner to decide (plan D11) |
| A5 | [R] Unusable answers from CVAT | silent | A 200 without the expected shape is a 503 and is never cached | agent (R, O) | `d2e4463` | goes away |
| A6 | Unknown organization | silent | Same 403 as a foreign one | agent (I 04) | `ee7f671` | changes: 404 |
| A7 | [R] Isolation | ticket 04: every case tested | The organization clause is written out in each read file. Until review no test would have failed if details or list lost it; tests were then added and shown to fail without the clause | agent (R) | `26d9d0d` | carries over |
| A8 | Header link | spec: shown when analytics is enabled and the role allows | Admin group or current role owner or maintainer; ignores the per-user Grafana flag. A maintainer with no organization selected sees no link. The route itself renders for everyone | agent (I 02) | `76b0740` | carries over |
| A9 | Signed-out state | spec: "not available" or an error panel | A 401 got its own state | agent (I 04) | `9389c94` | carries over |

## P. Page

| # | Decision | First plan | What happened | Who | Source | Under the new plan |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | How the page calls the service | spec: the page names the organization to the service | A plain same-origin `fetch` to its own prefix, not cvat-core; the organization as a slug parameter; tests replace the fetch function | agent (I 02) | `76b0740` | changes: cvat-core's request function; the organization is attached by cvat-core |
| P2 | [R] Organization in the address | spec: full view, period and filters in the address | The address gained `org`; filters of another organization are not applied | agent (R) | `25a201c` | carries over |
| P3 | [R] Refusals | ticket 04 | A 401 or 403 from any endpoint replaces the whole page | agent (R) | `90eceae` | carries over; read from the status code |
| P4 | Project names | spec: resolved by the page through CVAT | Through cvat-core with an `in` filter on ids, [R] 100 ids per request; the details project search is done by the page and sends one table page of ids | agent (I 07, 16, R) | `54f3372`, `02b845e` | carries over |
| P5 | Wording | spec: follows the prototype | Texts invented for states the prototype lacks; glossary wording wins where the prototype differs | agent (O, I) | N | carries over |
| P6 | Components shaped by the test harness | silent | A plain link and plain buttons where the Ant Design components do not load under the node harness | agent (I 02) | `76b0740` | carries over with the harness |
| P7 | State not in the address | spec story 26 | Trend step, comparison, details search and page live in page state. "Back to overview" adds a history entry | agent (I 14, 17) | `61142c9`, `f9d332e` | carries over |
| P8 | Smaller than the stories | spec stories 27, 28, 80 | Sessions are a headline card with the total in hover text; the details table has no full view; the empty state appears in one card | agent (O, I 06, 08, 17) | `a9e18df`, `f9d332e`, `151f29e` | carries over |
| P9 | Overview bars | prototype: bars by project and annotator split by operation | Single-colour working-time bars; the split appears only in the full view. Left "for later" by ticket 07 and never picked up | scope dropped | `76452db` | open |
| P10 | Definitions footer | design: the overview ends with short definitions | Absent: nothing in the page directory mentions definitions, and no record says it was dropped | scope dropped | design | open |
| P11 | New patterns in the UI | spec: lazy page behind its own error boundary | `React.lazy` and a local error boundary, neither used in this UI before; the first UI code to check the admin group | agent (O, I 02) | `76b0740` | carries over |
| P12 | Narrow window | spec story 90 | The page container is forced to the window width; CVAT's own header still keeps the app 1025 px wide | agent (I 18) | `e456e22`, `5b38488` | carries over |
| P13 | Stale status | spec stories 24 and 25 | Status is read every 60 s; when that fails the page keeps the last stamp and ages it by its own clock | agent (I 05) | `9198667` | carries over |

## L. UI logging

| # | Decision | First plan | What happened | Who | Source | Under the new plan |
| --- | --- | --- | --- | --- | --- | --- |
| L1 | Event contract | ADR 0002 | Field and record names fixed by the orchestrator; tags got their own value; the payload key `client_id` is never written | agent (O, I 09) | `56463fb` | carries over (plan D7) |
| L2 | Frame navigation | spec: every invocation; ticket 13 and glossary: every frame moved | Every handler invocation counts, also repeats that arrive while a frame is loading | agent (O) | `9ceca5f` | carries over |
| L3 | Class change | spec: method from the shared mark; ticket: three entry points | Four entry points; the method is fixed by the call site, not read from the mark; unchanged and locked objects are skipped | agent (I 10) | `31b6949`, `0200d3e` | carries over |
| L4 | Input method and mouse zones | spec: hotkey or mouse; zones not named | Operations default to mouse; drag and resize are always mouse; seven zones, where "header" is the annotation top bar and CVAT's global header counts as "other" | agent (I 13) | `c2109a4` | carries over |
| L5 | Frame-change compression | ticket 13: unaffected | Writing a summary can split one compressed run of frame changes into two events | known limit | N | carries over |
| L6 | Tab close | spec: a summary when the job is closed | Counts since the last summary are lost when the tab closes or reloads. Not fixed because it needs a cvat-core change, which was ruled out | known limit (R, O) | FS; EV | becomes fixable (plan D8) |
| L7 | Closing a job | ticket 13 claimed closing writes the summary | It waited for the 90 s timer until the final run; now the annotation page chains the summary before its closing log save, in an upstream file | agent (I 18) | `3b29af0` | carries over as a touch point |
| L8 | [R] Two logging fixes | — | The detector record is written only once objects were created; a class change no longer consumes a pending drawing's input method | agent (R) | `936bf9a`, `ee901c2` | carries over |
| L9 | Guard | spec: switches itself off after repeated failures | After three, for the life of the page. The module has an import cycle that was reported and left | agent (I 09, 10) | `56463fb` | carries over; upstream's ESLint will judge the cycle |
| L10 | Never logged | spec: only the 2D canvas | A group drag logs only the grabbed shape; moving the selection box, pasting a tag, interactors and OpenCV log nothing; 3D work is never shape-tagged. No decision on record | unchanged upstream behaviour | N | open |
| L11 | Upstream names | — | A renamed scope, event or shortcut action breaks the figures silently | known limit | FS | carries over; a merge of a release makes such renames visible in the diff |

## V. Verification

| # | Decision | First plan | What happened | Who | Source | Under the new plan |
| --- | --- | --- | --- | --- | --- | --- |
| V1 | Service tests | seam 1: through the read interface, real ClickHouse | Standard-library tests inside a stock-image container, a stand-in CVAT whose answers were taken from reading the source; one test reads a stored table directly | agent (O, I 02, 06) | `4406517` | changes: Django tests, generated policy tests, REST tests |
| V2 | Frontend tests | seams 2 and 3 follow the existing suite | A hand-rolled `node --test` harness that transpiles sources per file, with a jsdom present only as another package's optional dependency | agent (O, I 02) | `76b0740` | stays fork-owned; upstream has no unit harness to move into |
| V3 | Test-first | the skill asks for it | Six tickets report tests that passed on first run because the code came first | agent (I) | N | process |
| V4 | Access against a live CVAT | spec story 106: every role, real CVAT | Seen only with the stand-in: removed member, CVAT unreachable, cache expiry, admin by group and not by superuser flag, personal workspaces under instance scope, an owner with no organization, credentials as an `Authorization` header | verification gap | EV | closed by REST tests on real roles; three of the cases stop existing |
| V5 | The final run | seam 4 | The detector record was posted through the API, not produced by the UI; the volume data was inserted straight into ClickHouse, past the events API and Vector; mouse class change and resize were not driven; no side-by-side run with the stock UI | agent (O, I 18) | EV | open; belongs to the new final run |
| V6 | Layout and wiring | spec stories 87 and 90 | Layout was checked only in the one live browser run; the wiring lines for input counting were never executed by a test | verification gap | EV | Cypress specs |
| V7 | Lint | owner's standing rule expects the project's lint pipeline | ESLint never ran: the filtered import has no root ESLint configuration. Type checks resolved workspace packages to another checkout. Python was checked with ruff only. No hook pipeline | verification gap | N | closed by the conversion |
| V8 | After the fixes | rerun checks after relevant changes | Only the fast suites were rerun on the integration branch; the stack reruns were in-place upgrades without teardown; post-fix behaviour on the stack was read by hand | agent (O) | EV | rerun in full at the end of phase 1 |
| V9 | Never seen live | — | Lease loss, a hanging renewal, the body desync behind a proxy, the production Ingress, the cutover found while history is incomplete, the tab-close loss | verification gap | EV | the first four stop existing; the last two remain |
| V10 | ClickHouse versions | nothing may depend on a difference | The full suite ran on the chart's version; the Compose version got subsets from ticket 08 on. One lease test was loosened from 3 s to 8 s for slow hosts | agent (I) | `180abb3`, `4ee92c0` | carries over |
| V11 | Criteria ticked on a reading | all criteria ticked in one commit | Ten criteria were ticked although shown only by a stand-in, a script, a different counting rule, or a rule since replaced | agent (O) | `dca82a3`, `3d7af0d` | the new specification states them as they are |
| V12 | Reviews | spec: one independent review of the access rules | One static review of the whole branch, one access review with a sceptic per finding, one reviewer per fix round. No review per ticket. The second reviewer's three low findings were recorded, not reviewed again | agent (O) | EV | process |

## T. Test stack, build and deployment

| # | Decision | First plan | What happened | Who | Source | Under the new plan |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | Seeding | synthetic users loaded each run | Accounts are created through the Django ORM inside the backend pod; events go through the API | agent (I 01) | `5cb9740` | carries over; the REST suite brings upstream's fixtures |
| T2 | The chart | pinned to the dated evidence, which held no versions | Downloaded into a cache; dependency versions resolved once, committed as a lock with archive hashes | agent (O, I 01) | `5cb9740`, `e452b77` | the download goes away; the lock stays fork-owned |
| T3 | The proxy | joins UI, API and service | A local nginx image outside the approved list, never pulled; it also fronts Grafana. Its host port was reserved in another repository and that edit was left uncommitted there | agent (I 01) | `5cb9740`, `3d7af0d` | the service route goes away; the reservation is still pending |
| T4 | Stack settings | — | Refresh every 60 s instead of 600 s; only the utils and webhooks workers | agent (I 01, 03) | `bccb300` | carries over; the utils worker runs the job |
| T5 | Images | two build scripts | Not published; they must be local on the node. Tags grew a suffix per run | agent (I 03) | `ceab5d5`, `1453fee` | changes: a UI image and a server image |
| T6 | The running stack | namespaces are removed after 48 hours | Left running at the owner's request after both fix rounds | owner | EV | — |

## R. Process and documents

| # | Decision | First plan | What happened | Who | Source | Under the new plan |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | Decisions outside the repository | — | The orchestrator's rulings, the as-built layout notes, both review write-ups and both fix briefs exist only in a notes directory outside the repository | agent (O) | N | this ledger is the in-repository record |
| R2 | Plan documents left behind | — | ADRs 0001 to 0003, the design and the spec body still describe the old legacy rule. The cutover, the lease rules and the limitations are only in the fork specification, the glossary and the evidence | agent (O), by omission | `dca82a3`, `08b3803`, `4143599` | phase 0 and phase 4 |
| R3 | Closing tickets | the tracker defines no closed state | A convention was invented: every criterion ticked, `Status: resolved`, one comment per ticket, all in one commit | agent (O) | `dca82a3` | process |
| R4 | Retries | one implementer per ticket | The first fan-out was stopped on a usage limit; three tickets were restarted from interrupted work on retry branches; a missing dependency edge blocked nine tickets for one run | agent (O) | `6b2d2e8`, `9eead01` | process |
| R5 | Commit hygiene | commit only your ticket's files | Implementers edited each other's tests and shared files; one commit skipped hooks that do not exist; compiled Python files were committed and later removed | agent (I) | `2303328`, `101b03f` | a hook pipeline (plan section 5.4) |
| R6 | Side effects on the machine | — | A Helm repository refresh under the owner's configuration, a tool downloaded into the owner's cache, a process kill by command line that could have hit another worktree | agent (I) | N | process |
| R7 | Model routing | owner: named subagent models, the main model only on the main agent | Followed, except the whole-branch code review, which ran on the main model; the orchestrator reported it | agent (O) | N | process |
| R8 | Left for the owner at the end | the repository is public | Committed run logs contain four lines with a home-directory cache path; the commit security review never completed; nothing was pushed after implementation | agent (O) | EV | open; to settle before the branch is pushed |
