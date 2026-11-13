# Team Analytics

Status: ready-for-agent

Vocabulary follows [`GLOSSARY.md`](../../GLOSSARY.md). Structural decisions are recorded in
[ADR 0001](../../docs/adr/0001-thin-analytics-service-with-stored-totals.md),
[ADR 0002](../../docs/adr/0002-new-measurements-inside-existing-event-types.md) and
[ADR 0003](../../docs/adr/0003-kubernetes-only-with-the-upstream-helm-chart.md).
The agreed design is [`docs/design/team-analytics/design.md`](../../docs/design/team-analytics/design.md);
the page design is the prototype beside it.

## Problem Statement

People who run annotation teams on this CVAT fork cannot see how the work is done. The
stock Grafana dashboards show raw events and one working-time table. They do not answer
the questions a team lead actually has:

- How many sessions did each annotator work, and for how long?
- How much of the working time goes into creating bounding boxes, aligning them,
  changing their class and deleting them, and how long does each of those take?
- Who works with hotkeys and who with the mouse, and which hotkeys are used?
- How do these figures differ between projects, and how do they change over weeks and
  months?

Grafana is also open only to administrators, shows every organization's events to
whoever gets in, and is hard to read for anyone who is not an engineer. Several things a
team lead needs are not recorded by CVAT at all: which shape an action touched, class
changes, how a box was created, and hotkey use.

## Solution

A Team Analytics page inside the CVAT UI. An owner or maintainer of an organization, or
an administrator, opens it from the header and sees, for a chosen period, the sessions,
working time, bounding box operations, creation methods and keyboard and mouse use of
the team, per annotator, per project and overall. They can filter by annotator and
project, follow trends over the last twelve weeks or months, compare up to five
annotators or projects, and open any chart in a full view that shows every row.

The page reads ready-made figures, so a year loads as quickly as a week. Figures are at
most about ten minutes behind. The UI starts recording the missing measurements from the
day it is deployed; for earlier periods the page shows what the old data can support and
says what is missing.

The existing header link to the stock dashboards is renamed Grafana.

## User Stories

### Access

1. As an organization maintainer, I want a Team Analytics link in the header, so that I can reach the page without knowing its address.
2. As an organization owner, I want to open Team Analytics by virtue of my role, so that nobody has to grant me access separately.
3. As an organization maintainer, I want to see only my organization's figures, so that I am not shown other teams' work.
4. As an organization owner, I want to be sure maintainers of other organizations cannot see my team's figures, so that our work stays private to us.
5. As an administrator with an organization selected, I want that organization's figures, so that I see what its maintainers see.
6. As an administrator with no organization selected, I want instance scope, so that I can see all job work including personal workspaces.
7. As an organization maintainer with no organization selected, I want to be told to select one, so that I understand why the page is empty.
8. As an ordinary annotator, I want no Team Analytics link in my header, so that I am not offered a page I cannot use.
9. As an ordinary annotator who follows a direct link, I want a clear "not available" message, so that I know it is a matter of role and not an error.
10. As an ordinary annotator, I want the service to refuse me the figures even if I call it directly, so that the role rule cannot be bypassed from the browser.
11. As a person who was removed from an organization, I want to lose access to its figures at once, so that old membership grants nothing.
12. As a user of a server without analytics enabled, I want no Team Analytics link, so that I am not sent to a page that cannot work.
13. As anyone using the header, I want the stock dashboards link to read Grafana, so that the two destinations are not confused.

### Period and filters

14. As a team lead, I want to choose Week, Two weeks, Month or Year, so that I can look at the span I care about.
15. As a team lead, I want to step back through earlier months, so that I can review a finished month.
16. As a team lead, I want the current month shown "to date", so that I know it is incomplete.
17. As a team lead, I want days to follow my own time zone, so that a working day is not split in two.
18. As a team lead, I want to filter the whole page by one annotator, so that I can review one person.
19. As a team lead, I want to filter the whole page by one project, so that I can review one project.
20. As a team lead, I want to combine both filters, so that I can see one person's work in one project.
21. As a team lead, I want to set a filter by clicking a row in a chart or table, so that I do not have to search a list.
22. As a team lead, I want to clear a filter with one click, so that I can return to the whole team.
23. As a team lead, I want to switch between bounding boxes and all shapes, so that I can include other kinds of objects when I need to.
24. As a team lead, I want to see how old the figures are, so that I know whether the last hour is included.
25. As a team lead, I want a warning when the figures are more than thirty minutes old, so that I notice when refreshing has stopped.
26. As a team lead, I want my period and filters kept in the page address, so that the browser's back button and a shared link behave as expected.

### Sessions and working time

27. As a team lead, I want the number of sessions per annotator, so that I can see how their work is split up.
28. As a team lead, I want the average and total session length, so that I can see how long people work without a break.
29. As a team lead, I want a pause of more than five minutes to start a new session, so that sessions mean uninterrupted work.
30. As a team lead, I want working time per annotator in hours, so that I can see how much each person worked.
31. As a team lead, I want working time to be the same figure Grafana shows, so that the two never disagree.
32. As a team lead, I want working time by day, so that I can see the rhythm of the week.
33. As a team lead looking at a long period, I want the time chart to switch from days to weeks, so that it stays readable.
34. As a team lead who selected a project, I want sessions that touched that project counted with only the time spent inside it, so that project figures are not inflated by other work.
35. As a team lead, I want reviewers counted like everyone else who works in jobs, so that all job work is visible.
36. As a team lead, I want technical accounts left out of annotator lists, so that scripts do not appear as people.

### Bounding box operations

37. As a team lead, I want the number of bounding boxes created, so that I can see output.
38. As a team lead, I want the number of alignments, so that I can see how much correction is done.
39. As a team lead, I want an alignment to be one uninterrupted run of adjustments to the same box, so that three small drags are not counted as three corrections.
40. As a team lead, I want returning to a box later to count as a new alignment, so that repeated rework is visible.
41. As a team lead, I want the number of class changes, so that I can see how often labels are corrected.
42. As a team lead, I want a class change of several selected boxes to count each box, so that bulk relabelling is not hidden.
43. As a team lead, I want the number of deletions, so that I can see how much is thrown away.
44. As a team lead, I want operations to count what people did even if it was undone, so that effort is not understated.
45. As a team lead, I want the average time per operation, so that I can see how long each kind of step takes.
46. As a team lead, I want that time to run from the person's previous action, so that finding and deciding are included.
47. As a team lead, I want pauses over 100 seconds left out, so that a coffee break is not charged to a box.
48. As a team lead, I want time spent zooming while a box is being drawn to count towards that box, so that drawing time is not understated.
49. As a team lead, I want to see how working time divides between the four operations and Other, so that I know where the hours go.
50. As a team lead, I want every time breakdown to add up to working time, so that the charts agree with each other.
51. As a team lead, I want only single-frame rectangles counted as bounding boxes, so that tracks do not distort box figures.

### Creation methods

52. As a team lead, I want drawn, pasted and propagated boxes counted separately, so that I can see how boxes are really made.
53. As a team lead, I want an average time for each of those methods and one for all three together, so that I can compare them.
54. As a team lead, I want Model boxes shown beside them with counts only, so that automatic work is visible but not mistaken for a person's.
55. As a team lead, I want boxes saved by technical accounts counted as Model for the project, so that pre-annotation shows up where it was applied.
56. As a team lead, I want boxes made with the built-in detector counted as Model for the annotator who ran it, so that assisted work is visible.
57. As a team lead, I want a note that a re-upload by a technical account counts again, so that I read the Model figure correctly.
58. As a fork maintainer, I want technical accounts to be a configured list, so that I can change it without changing code.

### Keyboard and mouse

59. As a team lead, I want hotkey actions and mouse actions per annotator, so that I can see who uses the keyboard.
60. As a team lead, I want the hotkey share, so that I can compare people with one number.
61. As a team lead, I want the most used hotkeys by what they do, so that remapped keys still group together.
62. As a team lead, I want a held frame-navigation key to count every frame moved, so that keyboard navigation is not understated against button clicks.
63. As a team lead, I want every other held key counted once, so that auto-repeat does not inflate the figures.
64. As a team lead, I want to see for creation, class change and deletion how often each was started by hotkey and how often by mouse, so that I know where training would help.
65. As a team lead, I want clicks on the canvas kept out of mouse actions, so that drawing is not mistaken for using the mouse instead of a hotkey.

### Projects

66. As a team lead, I want every figure per project, so that I can compare projects.
67. As a team lead, I want to see how many annotators worked in each project, so that I know its staffing.
68. As a team lead, I want to see in how many projects each annotator worked, so that I know how spread out they are.
69. As a team lead, I want work in tasks without a project grouped as No project, so that nothing is lost.
70. As a team lead, I want a deleted project to stay in past figures, so that history does not change when a project is removed.

### Trends and comparison

71. As a team lead, I want working time, boxes created, average time per box and hotkey share over the last twelve weeks, so that I can see whether the team is improving.
72. As a team lead, I want the same by month, so that I can look further back.
73. As a team lead, I want trends to ignore the selected period, so that changing the period does not hide the history.
74. As a team lead, I want trends to follow the project and annotator filters, so that I can look at one person's or one project's history.
75. As a team lead, I want to compare up to five annotators as separate lines, so that I can see who is ahead and who is catching up.
76. As a team lead, I want to compare up to five projects the same way, so that I can see which projects are slower.
77. As a team lead, I want a compared line to keep its colour while I add and remove others, so that I do not lose track of who is who.
78. As a team lead with a large team, I want to find people for comparison by typing, so that I do not scroll through a hundred names.

### Large teams and full view

79. As a team lead with a hundred annotators, I want each chart to show its top rows and one line for the rest, so that the overview stays short.
80. As a team lead, I want a Full view button on every chart, so that I can see all of it when I need to.
81. As a team lead in a full view, I want every row with search and sorting, so that I can find anyone.
82. As a team lead in a full view, I want the period and filters still available, so that I do not have to go back to change them.
83. As a team lead in a full view, I want names shown whole, so that long names are readable.
84. As a team lead, I want to return to the overview with one click or the back button, so that I do not lose my place.
85. As a team lead, I want the operations and creation-method charts to open as a table by annotator or by project, so that I can read exact values for everyone.
86. As a team lead, I want a legend inside every chart, so that I do not have to look elsewhere for what the colours mean.
87. As a team lead, I want long names shortened on the overview with the full name on hover, so that the layout does not break.
88. As a team lead, I want large numbers shortened in the tiles with the exact value on hover, so that tiles stay readable.
89. As a team lead, I want the details table paged and searchable, so that it does not grow without limit.
90. As a team lead on a narrow window, I want cards to stack and wide tables to scroll sideways, so that the page remains usable.

### Old data and processing

91. As a team lead looking at a legacy period, I want a notice explaining what was not recorded, so that I do not read missing figures as zero.
92. As a team lead looking at a legacy period, I want sessions, working time, projects and all-shape operations, so that old work is still visible.
93. As a team lead looking at a legacy period, I want saved boxes per annotator and project, so that I have a real box figure for past work.
94. As a team lead right after deployment, I want a progress bar while history is processed, so that I know why earlier periods are not offered yet.
95. As a team lead, I want a period offered only when all of it is processed, so that I never read a partial figure as a total.
96. As a team lead, I want the most recent days processed first, so that the page is useful quickly.

### Reliability and operation

97. As an annotator, I want annotation to work exactly as before if Team Analytics or its logging fails, so that my work is never interrupted by it.
98. As an annotator, I want event logging and working time to keep working with the new measurements, so that my recorded time is not affected.
99. As a team lead, I want an error message on the page when the service is unreachable, so that I know the page, not CVAT, has a problem.
100. As a fork maintainer, I want the feature kept in its own modules with few changes to upstream files, so that CVAT upgrades stay manageable.
101. As a fork maintainer, I want scripts that build the UI image and the service image, so that I can produce both the same way every time.
102. As a fork maintainer, I want Kubernetes manifests for the service, so that I can add it to an installation.
103. As a fork maintainer, I want one command that brings up a disposable test stack, runs the checks and tears it down, so that verification is repeatable.
104. As a fork maintainer, I want the fork specification and upgrade procedure updated, so that the next upgrade knows what to preserve.
105. As a fork maintainer, I want events that arrive late still counted, so that a flaky connection does not lose someone's work.
106. As a reviewer of the access rules, I want them tested against a real CVAT with every role, so that I can trust the isolation.

## Implementation Decisions

### Shape of the solution

- Three parts: logging added to the UI, a thin analytics service, and the page. They
  are built and verified on Kubernetes against CVAT v2.82.0 only.
- The backend stays the stock image. Nothing in the server, its policies or the events
  pipeline is changed.
- Each part lives in its own module with a small interface. Changes to upstream UI
  files are limited to wiring: a route, a header link and its rename, and a few guarded
  calls at the places where actions are logged.

### UI logging

- No new event type is introduced. New information is added as payload fields on
  existing events or as records of the existing debug type with a distinguishing name.
- Every call into the logging module is guarded so that it cannot throw into the caller,
  and sending is fire-and-forget. The module switches itself off after repeated
  failures.
- Every new record is logged through the open job, so it carries project, task and job.
  Nothing is recorded outside a job. Only the 2D canvas is instrumented.
- Payload fields added to the existing draw, paste, propagate, drag, resize and delete
  events:
  - the shape type, or "mixed" when an action touched several kinds;
  - the number of single-frame rectangles among the objects;
  - whether the object is a single-frame shape or a track;
  - the input method that started the action, hotkey or mouse;
  - on drag and resize, a reference that identifies the object within the job for the
    browser session, and the frame, so that consecutive adjustments of one box can be
    grouped. The browser's existing client identifier field is not reused for this.
- A class-change record: named as a class change, with the number of objects, the shape
  fields above and the input method.
- A detector record: named as model creation, with the number of single-frame
  rectangles created by the built-in detector in the annotation view.
- An input summary record: hotkey actions counted per action name and mouse actions
  counted per interface zone, with the canvas as its own zone. Counts are kept in memory
  and sent as one record at most once a minute, always at a moment when the person is
  active, and when the job is closed. A record is never written on a timer alone,
  because the server would count the wait as working time.
- A hotkey action is counted on a key press that is not an auto-repeat. For frame
  navigation shortcuts every invocation is counted, repeats included.
- The input method of an action is "hotkey" when a shortcut handler ran immediately
  before it; a mouse click clears that mark. For drawing, the method is that of the step
  that started the drawing, not the click that finished it.

### Stored totals

- Totals live in their own database on the same ClickHouse server, reached with the
  account CVAT already uses. The service only reads the events table.
- The unit of storage is one hour in UTC, per organization, project, task and annotator.
  Totals are replaced as whole units, never adjusted in place.
- Kept per unit:
  - working time;
  - for each operation, split by bounding box versus other shapes: objects, objects with
    a measured time, time, and counts by input method;
  - for creation, the same split by method (drawn, pasted, propagated);
  - model boxes (detector) and saved boxes created, updated and deleted, by shape type;
  - hotkey actions per action name and mouse actions per zone.
- Sessions are stored as intervals per annotator, together with the time each session
  spent in each project, so that a project filter can count the sessions that touched
  the project and use only the time inside it.
- Processing state is stored per day: the raw row count seen and when the day was
  computed.
- The session gap (five minutes) and the idle pause (100 seconds) are applied when
  totals are computed. Changing either means recomputing history.

### Calculations

- All calculations are SQL kept in the repository. The service contains no aggregation
  logic.
- Payloads are parsed as JSON, never matched as text: client payloads are stored with a
  space after each colon and server payloads without.
- Sessions: an annotator's job-bound client events and job-bound working-time rows,
  ordered by time; a gap over the session gap starts a new session.
- Time per operation: the time since the annotator's previous client event, dropped when
  it exceeds the idle pause. For events logged when an action ends, the action's own
  duration is credited to it, and navigation events lying inside that interval give
  their time to it.
- Alignment: consecutive drags and resizes of the same object reference by the same
  annotator form one alignment; any operation on another object or a frame change ends
  it. Where no reference exists (legacy events), each drag or resize is one alignment.
- Bounding box: a single-frame rectangle. Events without a shape type count only under
  all shapes.
- Other: working time minus operation time for the scope being displayed, never below
  zero.
- Model for a project: boxes created in saved-annotation rows by technical accounts,
  plus detector records. Model for an annotator: detector records.
- Annotators: everyone with job work in the scope except technical accounts.

### Refresh and history

- Every ten minutes the service recomputes a trailing window of 48 hours and replaces
  those hours. The computation reads five minutes before the window so that sessions and
  time per operation are exact at the edge.
- Once a day the service compares the raw row count of each older day with the stored
  one and recomputes days that differ.
- History is filled one day at a time, newest first. The fill never runs as one query
  over a long range.
- ClickHouse does not schedule anything; the service does.
- Only one refresh runs at a time, also when the service has several replicas.

### Service interface

- One address prefix on the same origin as CVAT, not under the CVAT API prefix and not
  starting with the Grafana prefix.
- Read-only for callers. Endpoints, all taking the organization, the period, the
  optional project and annotator filters, the shape switch and the viewer's time zone:
  - overview: headline figures, working time per day or week, the split of working time,
    operations, creation methods, top rows by project and by annotator with remainders,
    keyboard and mouse figures with top hotkeys and the remainder;
  - list: every row of one chart for the full view, by annotator or by project;
  - details: the paged, searchable table by annotator or by project;
  - trends: twelve weeks or months for the scope or for up to five compared annotators
    or projects;
  - status: how far history is processed, which periods are available, and the time of
    the last successful refresh.
- Responses carry identifiers for projects and annotators and the annotator's user
  name. Project names are resolved by the page through the existing CVAT API, so a
  caller sees only names CVAT would show them; a project CVAT no longer returns is shown
  by its identifier.
- Weeks start on Monday. Week and Two weeks end today; Month is a calendar month; Year
  is the last twelve months.

### Access control

- For every request the service asks CVAT, with the caller's own credentials, who the
  caller is and which groups they belong to, and, when an organization is named, what
  role the caller holds in it.
- Rules: a member of the admin group may read the named organization, or instance scope
  when none is named. An owner or maintainer may read their organization. Everyone else
  is refused, including a maintainer who names no organization.
- The organization filter applied to every query comes from CVAT's answer. An
  organization or annotator identifier sent by the browser never widens what is read.
- CVAT's answers may be cached for at most one minute per caller.
- When CVAT cannot be reached, the service refuses.

### Page

- Address `/team-analytics`, with the full view, period and filters reflected in the
  address.
- Loaded on demand behind its own error boundary. The header link appears only when
  analytics is enabled on the server and the role allows it; the role comes from what
  the UI already knows about the current organization.
- The existing header link to the stock dashboards is renamed Grafana. Its address and
  behaviour are unchanged.
- Layout, states and wording follow the prototype: overview, full view of each chart,
  overflow behaviour, narrow window, history being processed, legacy period, no access.
- Charts are plain HTML and SVG in the style of the existing task progress widget; no
  new package is added.
- While new figures load, the previous ones stay on screen dimmed.
- Colours follow the entity: each operation has one fixed colour everywhere, and a
  compared line keeps its colour until it is removed.

### Images and manifests

- Two build scripts: the UI image, built as today with the feature included, and the
  service image, built from the stock server image with the service code and SQL copied
  in. The service adds no Python dependency that image does not already contain.
- Kubernetes manifests for the service: workload, service, configuration (technical
  accounts, refresh interval, ClickHouse and CVAT addresses) and the route under its
  prefix.
- The Compose overlay is not extended.

### Test stack

- A disposable namespace on the local cluster with a quota and default limits, created
  and removed by one command.
- CVAT is installed from the upstream Helm chart for the pinned upstream commit. The
  chart is downloaded by the test tooling into a cache outside the fork's filtered
  import, so the import's recorded identifiers do not change. The chart's dependency
  versions are pinned to those in the dated evidence.
- The service and a small reverse proxy are added as separate manifests. The proxy joins
  the UI, the CVAT API and the service under one address, reached through the reserved
  forwarded host port.
- Synthetic users, organizations, projects and events are loaded on each run.

### Documentation

- The fork specification gains a section for this feature with its integration map and
  acceptance scenarios; the upgrade procedure gains its checks; the README links to
  both.

## Testing Decisions

A good test here states what a person would observe (a figure on the page, a refusal, a
record sent) and reaches it through a public boundary. It does not assert on internal
functions, intermediate tables or the text of a query. Tests exercise product code only,
never the behaviour of project tooling.

Three seams, plus one end-to-end run:

1. **The service's read interface against a real ClickHouse.** Event rows go in, the
   refresh runs, figures come out as responses. This one seam covers the calculations,
   stored totals, refresh, history and the access rules. CVAT's identity answers are
   supplied at the service's boundary to CVAT. Cases come from the agreed scenarios:
   - a session spanning two projects, seen overall and under each project;
   - three drags on one box, another box, then the first again;
   - a creation that is undone and redone;
   - navigation inside a drawing;
   - an idle pause before an action;
   - work across midnight and across a refresh boundary;
   - a batch that spans a project switch and an hour boundary, where Other must not go
     below zero;
   - an event that arrives two days late;
   - legacy events without shape type;
   - boxes saved by a technical account and a re-upload;
   - every access case: admin group with and without an organization, owner,
     maintainer, supervisor, worker, non-member, removed member, another organization,
     maintainer with no organization, CVAT unreachable.
2. **The events the UI logging sends.** UI actions go in at the points where the UI logs
   them; the serialized events at the boundary to the server come out. Cases: each
   payload field, class change of one and several objects, detector use, hotkey and
   mouse counting including a held frame-navigation key and a held ordinary key, the
   input method of an action started by hotkey and finished by mouse, flush only at
   moments of activity, nothing recorded outside a job, and a logging failure that must
   not reach the caller. Only allowed event types may appear.
3. **The page against supplied service responses.** Responses go in; rendered output
   comes out. Cases: each state in the prototype, filters and full view driving the
   address, top rows with remainder, long names, large numbers, comparison at its
   limit, a legacy period, history being processed, stale data, service error, no
   access.
4. **One end-to-end run on the test stack.** A real CVAT accepts the new records and
   they arrive in ClickHouse; the service returns the expected figures for the loaded
   data; the access cases hold with real accounts; the page loads, filters and opens a
   full view in a browser.

Prior art in this repository: the frontend regression suite under `verify/` runs the
fork's TypeScript and React sources with only API and application boundaries replaced,
with an optional browser check; the policy tests evaluate rules against synthetic
inputs; the live checks seed a stack and exercise it. Seams 2 and 3 follow the first.
Seam 1 needs a ClickHouse container and nothing else.

The access rules get an independent review after the end-to-end run.

## Out of Scope

- Downloading figures as a file.
- A task or job view. Totals are stored per task so it can be added later.
- The 3D canvas.
- Telling apart whole-task automatic annotation and file imports done by a regular
  annotator.
- Annotators seeing their own figures.
- A comparison with the previous period.
- Custom date ranges.
- The Compose deployment and the air-gapped production installation.
- Migrating the two existing Compose checks to Kubernetes.
- Any change to the stock backend, its policies, Grafana's content or its access rule.
- Server versions other than v2.82.0.

## Further Notes

- The measurements behind ADR 0001 used ClickHouse 23.11; the Helm chart runs 23.12.2.
  Nothing in the calculations may depend on a difference between them. The long-range
  memory behaviour was seen on 23.11 with default settings; the day-by-day fill avoids
  it on either version.
- Two agreed definitions were not part of the timing measurement: a session counting for
  every project it touched, and an alignment ending on a frame change. The benchmark
  queries under `docs/evidence/` are a starting point, not the final calculations.
- Stored hours are in UTC. A viewer whose time zone is offset by a part of an hour gets
  days assembled from whole stored hours, so their day boundary is off by that part.
  This was not discussed with the owner; it is accepted unless they say otherwise.
- How CVAT's own client conveys the current organization on a request was not verified.
  The page names the organization explicitly to the service, and the service checks the
  caller's role in it with CVAT.
- The owner approved pulling these images for the test stack: `cvat/server:v2.82.0`,
  `apache/kvrocks:2.15.0`, `cvat/clickhouse:23.12.2-debian-11-r0`,
  `cvat/postgresql:15.2.0-debian-11-r0`, `redis:7.2.11`, `grafana/grafana:10.1.5`,
  `busybox:1.36.1`, and using the npm registry for the UI build.
- Grafana in the chart downloads its ClickHouse plugin at every start. The Team
  Analytics checks do not depend on Grafana being up.
- The local cluster removes namespaces 48 hours after creation; a run must finish within
  that and must tolerate a missing namespace.
- This repository is public. Everything committed here, this spec included, becomes
  public when pushed.
