# Team Analytics — agreed design

Agreed with the fork owner on 2026-11-13. This is the design of a feature that is not
built yet; it is the input for the specification. Terms are used as defined in
[`GLOSSARY.md`](../../../GLOSSARY.md). The reasons behind the three structural choices
are in [`docs/adr/`](../../adr/), and the measurements behind them in
[the dated evidence](../../evidence/2026-11-13-team-analytics-design-measurements.md).

The page design is the prototype: sources in [`prototype/`](prototype/), published as a
design canvas at <https://claude.ai/artifact/LKQ9KVAT3ieFNZCCpixVCn> (private to the
owner). All numbers and names in it are invented sample data.

## Purpose and access

- A new page, Team Analytics, as a readable alternative to the stock event dashboards.
  The existing header link to those dashboards is renamed Grafana.
- Available to administrators and to owners and maintainers of the selected
  organization, by role and automatically. An administrator is a member of the admin
  group.
- Organization scope for a selected organization; instance scope for an administrator
  with none selected. An owner or maintainer with no organization selected is asked to
  select one.
- Organizations never see each other's figures.
- Ordinary annotators have no access, not even to their own figures. For them the
  header link is hidden and a direct visit shows a "not available" message.

## What is measured

Every figure is available per annotator, per project and overall. The annotator and
project filters combine.

- **Sessions**: count, total and average length. Session gap fixed at five minutes.
- **Working time**: the server's figure, by day and in total. It is the only total;
  Other is the working time not spent on an operation, computed for the scope shown
  and never displayed below zero.
- **Operations on bounding boxes**: Creation, Alignment, Class change and Deletion, each
  with a count, an average time, a total time and a share of working time. A switch
  widens the figures to all shapes.
- **Time per operation**, with idle pauses over 100 seconds left out. Navigation that
  happens while a box is being drawn counts towards that drawing.
- **Creation methods**, each on its own: Drawn, Pasted, Propagated, Model. An average
  time for the first three together and for each separately; Model has counts only. A
  re-upload by a technical account counts again, and the page says so.
- **Keyboard and mouse**: hotkey actions against mouse actions, hotkey share, use per
  hotkey action, and for each operation how it was started. Recorded only inside jobs
  and only on the 2D canvas.
- **Saved boxes** per annotator and project, which is what a legacy period offers in
  place of bounding box operations.

All job work counts, whatever the stage of the job. Technical accounts are a configured
list; they are left out of annotator lists, and what they save is Model.

## Reading the page

- **Periods**: Week, Two weeks, Month with a selector for earlier months, Year. No
  custom ranges. Days follow the viewer's time zone.
- **Overview**, top to bottom: filters (period, shapes, project, annotator) with a
  "data as of" stamp; headline tiles; working time by day beside where working time
  goes; the operations table beside creation methods; working time by project beside
  working time by annotator; keyboard and mouse; trends; the details table; short
  definitions.
- **Trends**: the last twelve weeks or months, independent of the period. Four charts:
  working time, boxes created, average time per box, hotkey share.
- **Comparison**: up to five annotators or five projects, one line each. A line keeps
  its colour while others are added or removed.
- **Long lists**: a chart on the overview shows its top rows and one line for the rest.
  The details table shows ten rows a page and can be searched.
- **Full view**: every chart has one. It replaces the overview, keeps the filter row,
  shows every row with search and sorting, and returns with "Back to overview". Charts
  with a fixed handful of rows open as a table by annotator or by project.
- **Legends** sit inside each chart, next to what they explain.
- **Long names** are shortened with the full name on hover; the full view shows them
  whole. Large numbers are shortened in tiles with the exact value on hover. A long
  period switches the time chart from days to weeks.
- **Processed history**: one progress bar while history is being processed. A period is
  offered only when all of it is processed, and partial figures are never shown. A
  warning appears when the data is more than thirty minutes old.
- **Legacy period**: a notice, all-shape operations, sessions, working time, projects
  and saved boxes; class change and keyboard panels say that nothing was recorded.

## How it is built

- New code is isolated. A failure of the page, of the service or of the added logging
  must not affect annotation or any other part of CVAT.
- The UI records shape type, class change, detector use and hotkey and mouse counts
  inside event types the stock server already accepts
  ([ADR 0002](../../adr/0002-new-measurements-inside-existing-event-types.md)).
- A thin service checks role and organization with CVAT, serves stored hourly totals
  and refreshes them every ten minutes; the calculations are SQL
  ([ADR 0001](../../adr/0001-thin-analytics-service-with-stored-totals.md)).
- History is filled newest first. Totals are kept per task although the page stops at
  projects. Work in a task without a project is shown as No project; a deleted project
  stays in history under its identifier.
- No page or service address starts with `/analytics`.
- Kubernetes only, CVAT v2.82.0 only, two custom images built by scripts
  ([ADR 0003](../../adr/0003-kubernetes-only-with-the-upstream-helm-chart.md)).

## Verification

- A disposable namespace on the local cluster with a quota and default limits: CVAT
  from the upstream Helm chart, the service and a reverse proxy beside it, synthetic
  users, projects and events, a forwarded host port, and teardown at the end.
- It must show four things: the figures are correct; access follows the roles against
  a real CVAT, including an ordinary member, a non-member, another organization and a
  maintainer with no organization selected; the real server accepts the added logging
  and the rows arrive; the page works in a browser.
- This stack covers this feature only. The two existing Compose checks are migrated
  separately.
- The access check gets an independent review.

## Not in the first version

- Downloading figures as a file.
- A task or job view.
- The 3D canvas.
- Telling apart whole-task automatic annotation and file imports done by a regular
  annotator.
- Annotators seeing their own figures.
- A comparison with the previous period.

## Open at the time of writing

- How the Helm chart is obtained for the fork, and pinning its dependency versions.
- Two agreed definitions were not part of the timing measurement: a session counting
  for every project it touched, and an alignment ending when the person leaves the
  frame.
- The prototype has been checked by running its script, not by its author viewing the
  rendered canvas; the owner reviewed it on the canvas.
- Production is air-gapped and was left out of scope.
