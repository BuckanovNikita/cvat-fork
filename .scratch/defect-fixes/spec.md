# Defect fixes: Team Analytics figures, the issue and comment policies, and fork delivery

Status: ready-for-agent

Vocabulary follows [`GLOSSARY.md`](../../GLOSSARY.md). Structural decisions are recorded in
[ADR 0001](../../docs/adr/0001-thin-analytics-service-with-stored-totals.md),
[ADR 0002](../../docs/adr/0002-new-measurements-inside-existing-event-types.md),
[ADR 0003](../../docs/adr/0003-kubernetes-only-with-the-upstream-helm-chart.md) with its
amendments of 2026-11-14, and
[ADR 0004](../../docs/adr/0004-a-fork-server-image-that-adds-only-the-patched-policies.md).
The order of work, the file-level notes and how each defect is known are in
[`plan.md`](plan.md). Item ids such as S13 or Q9 refer to
[`../standard-fork/decisions-ledger.md`](../standard-fork/decisions-ledger.md).

The owner settled the behaviour in this spec on 2026-11-14. Eight defaults were chosen
without the owner being asked; they are marked "default" where they appear and listed in
"Further Notes".

## Problem Statement

Team Analytics was built and reviewed, but its figures and its delivery cannot yet be
trusted in several places.

- Anyone who calls the service directly reads totals of a period that is still being
  processed; only the page hides them.
- Some work is miscounted. A creation that is undone and redone counts twice. A group of
  objects dragged together counts as one alignment of one object, and moving the selection
  box counts as nothing. Holding a frame-navigation key on a slow frame counts hotkey
  actions that moved no frame.
- A period can be labelled legacy when it is not: right after an upgrade, and for good when
  an early shape-tagged event arrives late.
- A project whose only work is boxes saved by a technical account is missing from the
  details table.
- An organization maintainer sees when the whole instance first recorded events and how
  many days of history it holds.
- The overview lacks two things the signed-off prototype shows: bars split by operation,
  and the definitions at its end.
- The patched issue and comment policies are in force nowhere. The only delivery was a
  Compose mount that silently stopped working after an upstream change, Compose is no
  longer used, and nothing delivers the policies on Kubernetes. The patch is also wider
  than meant: it admits an account with no global role.
- The repository carries Compose files and launchers nobody uses, a second copy of the
  policies that must be re-patched by hand on every upgrade, and a chart downloaded from
  outside the tree.
- The safety net has holes. ESLint never ran on the feature's UI code. The frontend tests
  skip themselves, and pass, when a library is missing. One refresh test depends on how
  fast the host is. A local machine path sits in tracked files of a public repository.
- A replica that is killed while refreshing blocks every refresh for thirty minutes.
- Several claims rest on stand-ins and were never seen for real: access cases against a
  real CVAT, the detector record produced by the UI, the large-team volume passing through
  the events API, the service's Ingress route, and a full run after the review fixes.

## Solution

Figures are withheld until they are complete, counted by the rules of the glossary, and
labelled legacy only when they are. Organization maintainers see their organization's
state and nothing about the instance beyond the cutover day. The overview gains the split
bars and the definitions.

The issue and comment patch is delivered inside a fork server image, so it is in force on
Kubernetes and cannot be switched off by a moved directory. It requires a global role;
below that, an account gets exactly what stock CVAT gives it.

The fork's import brings in upstream's lint configuration, the Helm chart and the stock
policies. The policies are patched in place, like the UI. Everything that existed only for
Compose is removed, and the two checks it ran move to the Kubernetes stack.

A gate runs the linters and the fast suites; tests fail when something they need is
missing. One fresh run on the stack shows the fixes and the claims that were never seen
for real.

## User Stories

"Maintainer" below means an organization owner or maintainer reading Team Analytics.
"Fork maintainer" means the person who builds, upgrades and verifies this fork.

### Processed history

1. As a maintainer, I want the service to give no figures for a period that is not fully
   processed, so that nobody reads partial totals as final.
2. As a maintainer, I want that rule to hold for a direct request as well as for the page,
   so that an export or a script cannot get what the page withholds.
3. As a maintainer, I want such an answer to say that the period is still being processed,
   so that I know to come back and not that something failed.
4. As a maintainer, I want a trend bucket that is not fully processed to carry no value,
   so that a half-computed week is not drawn as a drop.
5. As a maintainer, I want the page to keep showing its "being processed" state for such
   a period, so that the change in the service is invisible to me.
6. As a fork maintainer running the service with a refresh window shorter than a day, I
   want today's earlier hours either computed or reported as not processed, so that hours
   nobody computed never count as done.

### Status and scope

7. As a maintainer, I want status to tell me whether processed history is complete, so
   that I know whether older periods can be trusted.
8. As a maintainer, I want to see progress as a percentage while history is processed, so
   that I can tell it is moving.
9. As a maintainer, I want to see which periods can be offered, so that the period control
   only offers what exists.
10. As a maintainer, I want to see how fresh the figures are, so that I know how old the
    last refresh is.
11. As a maintainer, I want to see the cutover day, so that I understand why earlier
    periods are legacy.
12. As an organization owner, I want maintainers of other organizations not to learn when
    the instance first recorded events or how many days of history it holds, so that
    nothing about the instance leaks through status.
13. As an administrator, I want the full history block with the first event day and the
    day counts, so that I can follow processing in detail.
14. As an administrator who selected an organization, I want that same full block, so that
    selecting an organization does not hide processing state from me.

### Cutover and legacy periods

15. As a maintainer, I want the cutover to be known from the first answer after the
    service starts, so that periods are not all labelled legacy until the next refresh.
16. As a maintainer, I want the cutover found from the recorded events themselves, so that
    it is known before a shape-tagged hour reaches the stored totals.
17. As a maintainer, I want the cutover to move to an earlier hour when an earlier
    shape-tagged event turns up, so that the days in between are not labelled legacy for
    good.
18. As a maintainer, I want the cutover never to move later, so that a period that showed
    full figures does not turn legacy.
19. As a fork maintainer, I want the documents to say what a shape-tagged event with a
    wrongly early date does to the cutover and what it takes to undo, so that I am not
    told that removing the stored value is enough.
20. As a maintainer who filtered the page to one project, I want the details table by
    project to keep listing every project, so that I can pick another one.
21. As a maintainer, I want each table to describe the rows it lists, so that a project
    with legacy work shows class change as not recorded even while my filtered overview
    is empty.
22. As a reader of the fork's documents, I want it stated that in 3D jobs only sessions
    and working time are measured, so that an instance with only 3D work reading as
    legacy is understood as the definition.

### Details table

23. As a maintainer, I want a project whose only work is boxes saved by a technical
    account to have a row in the details table by project, so that automated work is not
    invisible.
24. As a maintainer, I want that row to show its saved boxes and Model boxes with no
    working time, so that it reads as what it is.

### Operations

25. As a maintainer, I want drawing a box, undoing and redoing it to count as one
    creation, so that the creation count matches what people made.
26. As a maintainer, I want the time of a redo to fall under Other, so that time per
    creation is not diluted.
27. As a maintainer, I want creation methods free of guessed methods for redone objects,
    so that Drawn, Pasted and Propagated count real acts.
28. As a maintainer, I want a redo to still end an alignment run (default), so that
    alignment boundaries stay where they are today.
29. As a maintainer, I want several objects dragged together to count as one alignment
    for each object moved, so that alignments count objects like every other operation.
30. As a maintainer, I want the time of that gesture shared equally between those
    objects, so that no single object carries all of it and the others none.
31. As a maintainer, I want moving the selection box to count the same way, so that both
    ways of moving a group are measured alike.
32. As a maintainer, I want the grabbed object of a group drag not counted a second time,
    so that a group of three is three alignments and not four.
33. As a maintainer, I want a group move to be its own alignment for each object
    (default), so that it neither extends an earlier drag of one of them nor is extended
    by a later one.
34. As a maintainer looking at Bounding boxes, I want a group that mixes boxes and other
    shapes to count only its boxes there, with time split as for any mixed selection, so
    that the shape switch stays consistent.
35. As an annotator, I want CVAT's own event logging unchanged by these fixes, so that
    nothing I do in a job behaves differently.

### Hotkey actions

36. As a maintainer, I want a frame-navigation hotkey to count only when the frame
    actually changes, so that the figure means what the glossary says.
37. As a maintainer, I want a frame-navigation key pressed or held while a frame is still
    loading not to inflate the hotkey share, so that slow data does not look like keyboard
    skill.
38. As a maintainer, I want every other held key to stay one hotkey action, so that
    nothing else changes.

### Page

39. As a maintainer, I want the overview bars by annotator split by operation, so that I
    see what each person's time went into without opening the full view.
40. As a maintainer, I want the overview bars by project split the same way, so that
    projects compare like annotators.
41. As a maintainer, I want a legend for the split, so that the colours are readable.
42. As a maintainer, I want the split of a row to equal that row in the full view, so
    that the two never disagree.
43. As a maintainer, I want the overview to end with short definitions in the glossary's
    wording, so that I can check what a figure means without leaving the page.
44. As a maintainer on a narrow window, I want the split bars and the definitions to stay
    inside their cards, so that the page still does not scroll sideways.
45. As a maintainer, I want the history progress line to read as a percentage, so that it
    works without the instance's day counts.

### Issue and comment permissions

46. As an organization worker or supervisor, I want to create, view, update and delete
    issues and comments on any job of my organization, so that issue discussions do not
    depend on assignment.
47. As an organization member, I want to list every issue and comment of my
    organization, so that I can follow discussions I am not assigned to.
48. As an organization member, I want this to hold on the Kubernetes deployment, so that
    the patch is in force where CVAT actually runs.
49. As an administrator, I want an account with no global role to get exactly what stock
    CVAT gives it for every action, so that a deactivated or half-provisioned account
    gains nothing from the patch.
50. As an administrator, I want that account to keep what stock CVAT allows it, such as
    viewing and listing the issues it is assigned to, so that the floor removes the patch
    and nothing more.
51. As an organization owner, I want non-members, removed members and other organizations
    refused as before, so that the patch widens access only inside the organization.
52. As a fork maintainer, I want the policies delivered inside the server image, so that
    a directory moved by upstream cannot silently turn the patch off.
53. As a fork maintainer, I want every stack run to check that the served bundle carries
    each patched policy, each checked by itself, so that one stock file cannot hide behind
    the other.
54. As a fork maintainer, I want the patch to be an ordinary edit inside the import, so
    that an upgrade merges it and it shows as a difference against the release.
55. As a fork maintainer, I want the policy tests to run from this repository alone, so
    that no outside checkout is needed.

### Fork delivery

56. As a fork maintainer, I want one script to build the fork server image from the stock
    release and the two policies, so that building it is as plain as building the UI.
57. As a fork maintainer, I want that image to hold no Python change, so that the backend
    behaves as the stock release in everything but those two policies.
58. As a fork maintainer, I want the Team Analytics service to keep its own image, so
    that a change to analytics code never rolls out the CVAT backend.
59. As a fork maintainer, I want the Helm chart to come from the repository, so that a
    stack does not start by downloading the upstream sources.
60. As a fork maintainer, I want the chart's dependency archives still pinned and checked,
    so that a stack is the same on every run.
61. As a fork maintainer, I want the Compose overlay, its launchers and the copied policy
    directory removed, so that nobody takes them for a supported path.
62. As a fork maintainer, I want the issue-permission check and the task-progress check to
    run on the Kubernetes stack, so that removing Compose loses no coverage.
63. As a fork maintainer, I want the service's Ingress route applied and requested once
    per stack run, so that the manifest is known to work.
64. As a fork maintainer, I want the import's identifiers before and after the widening
    recorded, so that the provenance of the imported tree stays traceable.
65. As a fork maintainer, I want the mirror refreshed without destroying the existing one
    first, so that a failed download does not leave me without a source.
66. As a fork maintainer, I want the ClickHouse setup file to be upstream's own again
    (default), so that the chart ships to the cluster what upstream ships.

### Safety net

67. As a fork maintainer, I want ESLint, stylelint and the type check to run on the
    fork's UI code with upstream's configuration, so that the code meets the rules of the
    project it lives in.
68. As a fork maintainer, I want their first findings fixed in a commit of their own, so
    that later changes are reviewed without a formatting sweep.
69. As a fork maintainer, I want one command to run the linters, the type check, the
    policy test and the fast suites (default: a hook pipeline), so that a change is
    checked the same way every time.
70. As a fork maintainer, I want the frontend tests to fail when the browser environment
    they need is missing, so that a pass always means the tests ran.
71. As a fork maintainer, I want that library declared by the fork, so that the tests do
    not depend on another package's optional dependency.
72. As a fork maintainer, I want the UI logging module free of import cycles, so that it
    passes the linter and loads in a defined order.
73. As a fork maintainer, I want no local machine path in tracked files or in captured
    run logs, so that the public repository shows nothing about the machine it was
    built on.
74. As a maintainer, I want a replica that dies while refreshing to hold up refreshes for
    at most two minutes (default), so that figures do not go stale for half an hour.
75. As a fork maintainer, I want the refresh lease tests to run on a supplied clock, so
    that they pass or fail the same on a slow host.

### Verification

76. As the owner, I want to see a removed member lose access against a real CVAT, so that
    the rule is shown and not assumed.
77. As the owner, I want to see an administrator by group who is not a superuser get in,
    so that the administrator rule is the one I approved.
78. As the owner, I want to see a personal workspace counted under instance scope, so
    that instance scope is what the glossary says.
79. As the owner, I want to see credentials sent as an authorization header accepted, so
    that scripts can read figures the same way the page does.
80. As the owner, I want the detector record produced by the real UI (default: with the
    model's answer supplied), so that the UI path is exercised and not imitated.
81. As the owner, I want the large-team volume sent through the events API (default: the
    current week), so that the path through CVAT and Vector is exercised.
82. As the owner, I want one full run on a fresh stack after all fixes, on both ClickHouse
    versions, so that the evidence describes the code that exists.
83. As the owner, I want each fix shown on that stack along the path that failed, so that
    "fixed" means seen.
84. As the owner, I want a count of sessions that reached the one-day limit, so that I
    know whether that limit matters in practice.
85. As the owner, I want a completed security review of the branch before anything is
    pushed, so that a public push holds no surprise.
86. As the owner, I want each acceptance criterion that was ticked on a stand-in restated
    as what was actually shown, so that the tickets do not overstate.
87. As a reader of the fork's documents, I want the limits that stay stated plainly, so
    that nobody rediscovers them as defects.

## Implementation Decisions

### Import

- The path filter of the upstream mirror is widened once, at the current release. It
  gains upstream's root lint configuration (ESLint, stylelint, Prettier, EditorConfig),
  the Helm chart directory, and four policy files: the issue policy, the comment policy
  and the two helper policies they import. It loses the Compose file. The exact path list
  is in `plan.md`.
- Before the filter runs, the candidate files are proven in a scratch copy taken at the
  recorded upstream commit: the lint configurations load on the fork's UI paths, the
  chart renders the same as the cached one, and the policy test passes on the stock
  policies. The filter is then run once.
- The mirror script builds the new mirror beside the existing one and replaces it only on
  success.
- The existing release tags keep pointing at the earlier filtered commit. The new
  filtered commit gets its own tag, and the documented inventory of the fork's changes
  inside the import compares against it. Both sets of identifiers go into a dated
  baseline evidence file.
- The formatting-only change in the imported ClickHouse setup file is reverted (default).

### Policies and the fork server image

- The patch is applied to the imported stock policies. The copied policy directory is
  removed.
- The added "any member of the owning organization" rule also requires at least the
  `worker` global role, in both policies. The same holds for the added branch of the list
  filter. The stock member branch of the list filter, which the patch had replaced, is
  restored after the patched one, so that a member below the floor gets the stock result
  and not an undefined filter. Both policies were compared with their stock files; the
  patch is the same two additions in each.
- The invariant: for a caller with no global role, the patched policies decide exactly
  as the stock ones for every action. Stock CVAT lets such a caller view an issue it is
  staff of, so "refused everything" would be wrong.
- The fork server image is the stock release image with the two patched policies copied
  over the stock ones, and nothing else (ADR 0004). A build script beside the UI's builds
  it. It is never pulled; like the other two images it must be present on the node.
- The Team Analytics service image stays separate and stays on the stock base.

### Stack and removals

- The stack sets the chart's backend image to the fork server image and takes the chart
  from the import. Chart dependencies are still fetched by Helm and checked against the
  recorded hashes; the dependency lock stays fork-owned.
- The stack run gains: a check of the served policy bundle (each policy by itself); the
  issue and comment matrix with real accounts, including an account with no global role;
  the task-progress check; one request through the service's Ingress, applied beside the
  proxy under the cluster's Ingress class; and four access cases (a removed member, an
  administrator by group who is not a superuser, a personal workspace under instance
  scope, credentials as an authorization header).
- Only after those checks pass on the stack are the Compose overlay, the Compose
  verification files, their two launchers and the copied policy directory deleted. Seed
  and check scripts the stack reuses stay.

### Service: what a read returns

- A response for a period that is not fully processed keeps its envelope (period, filter
  echo, `processed: false`, the legacy flags) and carries no figures: every
  figure-bearing field is null. This holds for the overview, the full-view list and the
  details table. A trend bucket that is not fully processed has a null value.
- Status depends on who asks. An administrator gets the history block as today. Everyone
  else who may read gets: whether history is complete, a progress percentage, the periods
  that can be offered, the freshness stamp and the cutover day. The first event day and
  the day counts are left out.
- The details table by project takes its rows from working time, operations and saved
  boxes, so a project with only technical-account boxes has a row.
- Each overview row by annotator and by project carries its operation parts, in the shape
  the full-view list already uses.
- A table's legacy content keeps following the rows it lists (its own dimension's filter
  is not applied). This is pinned by a test and not changed.

### Service: refresh

- The cutover is looked for in the recorded events at service start and in the daily
  check, no longer only when a shape-tagged hour reaches the stored totals. A found hour
  earlier than the stored one replaces it; a later one never does. Reads use the earliest
  stored hour.
- This search is a long-range query, at start and once a day. That contradicts the Team
  Analytics spec's rule of no long-range query, as the one-time search already did. Its
  cost is measured on the loaded volume before it is adopted. If it proves too costly,
  the long-range search runs only while no cutover is stored, as today, and later moves
  come from the steps that compute an hour anyway (a history day, a recounted day) when
  that hour holds an earlier shape-tagged event.
- A shape-tagged event with a wrongly early date moves the cutover earlier, and removing
  the stored value does not undo it: the next search finds the same event. The only
  correction is to remove that event and then the stored value. This is written into the
  fork specification as a limit. It replaces the earlier limit, which said that removing
  the stored value was enough.
- The history step also covers today's hours that lie before the refresh window, so a
  short window leaves no hour counted as processed without being computed. Two existing
  tests set a one-hour window as a device for exercising the edge between two refreshes,
  so short windows must stay possible; refusing them is not an option.
- A redo is no longer turned into a creation, so it has no creation method and its time
  is Other. It still ends an alignment run (default).
- A group move becomes one alignment per object moved, each with an equal share of the
  gesture's time, and with the existing split between bounding boxes and other shapes. It
  ends the alignment runs before it and starts none that a later drag continues
  (default).
- The refresh lease is 120 seconds, renewed every 40 (default). The lease tests run on a
  supplied clock, and that change lands before the lease is shortened.

### UI logging

- A group move is represented by exactly one drag event carrying the number of objects
  moved and how many of them are bounding boxes, within the existing event type
  (ADR 0002). CVAT's own log of the grabbed shape is neither removed nor counted a second
  time. Moving the selection box produces the same event. The event's fields are fixed in
  the logging contract before the UI half and the calculation half are built.
- A frame-navigation hotkey counts one hotkey action when the frame changes as a result.
  A press or a repeat that arrives while a frame is loading, or that cannot move (the
  first or last frame, navigation blocked), counts nothing. Every other rule of hotkey
  and mouse counting is unchanged.
- The function that writes a Team Analytics record moves into a module of its own, which
  removes the three import cycles. Behaviour does not change.

### Page

- The two overview cards for working time by annotator and by project draw each bar as
  operation segments with a legend, reusing the full view's segment logic.
- A definitions block ends the overview, worded from the glossary.
- The history progress line renders from the percentage when the day counts are absent.

### Tooling

- A hook pipeline (default) holds ESLint, stylelint, the type check, ruff, the policy
  test and the three fast frontend suites. Suites that need ClickHouse or the stack stay
  separate commands.
- The frontend harness fails when the browser environment cannot be loaded. The library
  is declared in a fork-owned manifest.
- The five tracked lines with a local machine path are redacted going forward; history is
  not rewritten. The launcher filters Helm's symbolic-link warning on every Helm call,
  since with the chart in the tree that warning prints the repository path.

### Documents

- The fork specification: packaging and policy delivery, the issue and comment
  permissions, and the limits that stay (below).
- The upgrade procedure: the policies are merged with the import and no longer reapplied
  by hand; the fork server image is rebuilt.
- The Team Analytics spec and READMEs where they describe the stock backend, the chart
  download or the Compose checks. `INFRA_MIGRATION.md` gets its outcome.
- The ten acceptance criteria that were ticked on a reading are restated in their tickets.

## Testing Decisions

A good test here states what a person would observe (a figure, a refusal, a record sent,
an access decision) and reaches it through a public boundary. It does not assert on
internal functions, intermediate tables or the text of a query. Tests exercise product
code only; tooling, configuration and documents get a stated check, not a test.

No new seam is introduced. The four seams of the Team Analytics spec and the policy test
carry everything:

1. **The service's read interface against a real ClickHouse.** New or changed cases: a
   period that is not fully processed carries no figures, per endpoint and per trend
   bucket; a non-administrator's status has no first event day and no day counts while an
   administrator's has both; a project with only technical-account boxes has a details
   row; overview rows carry operation parts that equal the full view's; a table's legacy
   content with its own filter set; the cutover known on the first answer after start,
   found from raw events alone, moved by an earlier late event and not by a later one; a
   one-hour refresh window; draw, undo, redo as one creation with the redo's time under
   Other; a group event of three objects and six seconds as three alignments of two
   seconds; a killed lease holder overtaken within the lease. The existing tests that
   assert the old redo and unprocessed-period behaviour change with it.
2. **The events the UI logging sends.** New cases: a frame-navigation hotkey pressed or
   held while a frame is loading adds nothing, and neither does one at the last frame; a group drag of three boxes sends one group
   event for three objects and no second counted event for the grabbed one; moving the
   selection box sends the same event.
3. **The page against supplied service responses.** New cases: the two cards draw
   segments and a legend from per-row operations; the overview ends with the
   definitions; the progress line renders from a percentage; an answer without figures
   shows the "being processed" state.
4. **One end-to-end run on the test stack**, from an empty namespace, with the fork
   server image: the checks listed under "Stack and removals", each wave's fix seen along
   the path that failed, the detector record produced by the real UI with the model's
   answer supplied at the HTTP boundary, the current week of the volume sent through the
   events API, and a count of sessions that reached the one-day limit. It runs the full
   service suite on both ClickHouse versions.

**The policy test** evaluates the rules against synthetic inputs, now reading the
policies and helpers from the import. New cases: for a caller with no global role the
patched policies give the stock result for every action and for the list filter, once
for a caller who is staff of the issue and once for one who is not. It runs against the
stock tag and the patched tree, each with its own expectations.

Each failing test is written and seen to fail before its fix. Prior art is the existing
suites at each seam; nothing here needs a new harness.

Changes to behaviour, interfaces, delivery or access rules get an independent review after
integration and verification. The access rules and the policies get their own.

## Out of Scope

- Converting the repository into a full-source fork. Dropped by the owner on 2026-11-14.
- Any Python change in the backend, and any change to cvat-core.
- Delivering the policies by a mounted ConfigMap, and any Compose path.
- Counting tags, or objects made with the interactive AI or OpenCV tools. They stay
  uncounted and are stated as a limit.
- Delivering hotkey and mouse counts when a tab is closed. Stated as a limit.
- Sessions longer than a day. A session is at most a day long; the run only counts how
  many reached the limit.
- Measuring operations in 3D jobs.
- Rewriting history to remove the local path, and any push.
- Overview latency under load (S12), viewers in part-hour time zones (Q11), and the
  eighteen review questions the owner never answered (O15).
- The air-gapped production installation.

## Further Notes

- **Defaults chosen without the owner being asked.** Each stands unless the owner says
  otherwise: the gate is a hook pipeline; the lease is 120 seconds; a redo still ends an
  alignment run; a group move is its own alignment per object; the detector is verified
  with a supplied model answer, so a deployed model function stays unverified; only the
  current week of the volume goes through the events API, since it is not known whether
  the API accepts old timestamps; the ClickHouse setup file returns to upstream's; the
  ledger stays with a dated note.
- **A correction to what the owner was told.** When the owner agreed that the cutover
  may move earlier, the recommendation said the manual correction would remain for a
  wrongly dated event. It does not work for that case, as described under "Service:
  refresh". The owner has not seen this corrected statement.
- **Frame navigation at the first or last frame.** The owner decided "frames moved" for
  a key held on a slow frame. Counting nothing when the key cannot move at all is this
  spec's reading of the same glossary line, not a separate answer from the owner.
- **The widened import is one shot.** Every further widening changes the identifiers
  again, which is why the path list is proven first. It needs a full clone of upstream.
- **Not verified, to be found out by the work:** that upstream's lint configuration loads
  with only the imported files; that a squashed subtree pull accepts a re-filtered mirror;
  that the chart's link to the analytics components resolves inside the import as it does
  upstream; the cost of the cutover's long-range query.
- **Order.** The import comes first; the lint findings come before any other UI change;
  the policies, the image and the stack checks come before the Compose removal; the two
  service packages can run beside all of that; the verification run is last. `plan.md`
  holds the detail.
- The stack that was kept from the first run was torn down on the owner's instruction on
  2026-11-14, so the verification run starts from nothing.
- This repository is public. Everything committed here, this spec included, becomes
  public when pushed.

## Comments

2026-11-14: Broken into tickets 01 to 28 under `issues/`; the owner approved the breakdown as proposed.

2026-11-14: On the owner's instruction, `main` was fast-forwarded to this branch and pushed before any ticket started. The local path in four run logs, and in compiled files in history, is therefore public, and the security review was still outstanding. Story 85 and the out-of-scope line on pushing now mean further pushes. Ticket 01 cleans the current files only; ticket 28 reviews what is already public as well.

2026-11-14: The re-import of ticket 04 drops the Compose file from the import, so the two Compose launchers stop working there, before their files are removed in ticket 12. Between ticket 04 and tickets 09 and 10 neither the issue-permission check nor the task-progress check can run anywhere. The owner accepted the breakdown with this stated.

2026-11-14: On the owner's instruction, `main` was fast-forwarded to this branch a second time, at `6cedd04`, and pushed before any ticket started. That push carried the ticket files and two document corrections, nothing else. The security review of ticket 28 is still outstanding. Nothing more is pushed while the tickets are implemented unless the owner says so.
