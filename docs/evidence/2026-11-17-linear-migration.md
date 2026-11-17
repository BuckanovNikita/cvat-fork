# Migration of the tracker to Linear and of delivery to GitHub PRs, 2026-11-17

Linear issue: [SIP-97](https://linear.app/sip-ds-team/issue/SIP-97/migrate-cvat-fork-workflow-to-linear-and-github-prs).
Linear project: [cvat-fork](https://linear.app/sip-ds-team/project/cvat-fork-aaa37d3eda64) (`P-SIP-3`),
team `SIP`. The workflow is the one `clearml-yolo` adopted on the same day (its PR 9, SIP-64), taken
at this repository's size: there is no Spec Kit here to archive and no release automation.

## Source

Worktree branch `chore/linear-workflow`, created from `origin/main` at `2afbb331b` after a fetch on
2026-11-17. The local `main` of the machine was one commit behind `origin/main` and was not used or
moved. The repository had no pull request, open or closed, before this one.

## What changed

Policy:

- Active requirements, specs, plans, acceptance criteria and status move from `.scratch/` files to
  Linear issues. A feature is a parent issue holding the spec, with its tickets as sub-issues.
- Triage roles are Linear labels beside a lifecycle state, not a `Status:` line. `resolved` has no
  label: it is the Done state. `wontfix` goes with the Canceled state. An issue carries one
  readiness label at a time.
- Delivery is a GitHub PR against `main`, pushed and opened by an agent and merged by a human. Until
  now work was merged locally and pushed to `main`. Pushing a task branch and opening a PR no
  longer need separate authorization; publishing an image and deploying still do. The upgrade
  procedure said "publishing or deployment" and now says "publishing an image or deployment".
- A PR that takes an upstream release is merged with a merge commit, and its branch takes later
  commits of `main` by merge and is never rebased (ADR 0005). This is new text, in the tracker
  guidance and in sections 2 and 5 of the upgrade procedure: the repository allows merge, squash and
  rebase merges on GitHub, and nothing said which one an upgrade needs. Nothing on GitHub enforces
  it.
- Rules taken from `clearml-yolo`'s tracker guidance, new to this repository: an issue is Done only
  after a merged PR and met acceptance criteria, and In Review when implementation and verification
  are ready; dependent work starts on a verified base and a canceled prerequisite means replanning;
  what an evidence record holds; deferred required verification blocks merge readiness; independent
  review after integrated verification for changes of behavior, interface, dependency, security or
  operational policy; the rules for stacked PRs, force-with-lease on task-owned branches included.
  Checks are run locally and recorded in the issue and the PR, because the repository has no CI.
- An external PR is not a request to triage ("PRs as a request surface: no").
- The wayfinding operations are mapped to Linear objects: the map is an issue labelled
  `wayfinder:map`, a ticket is its sub-issue, blocking is the native relation, the claim is the
  assignee. One meaning changed: a ticket was unblocked when every ticket it listed was
  `resolved`, and is now unblocked when every blocker is closed (Done, Canceled or Duplicate), as
  the skill defines it. The `wayfinder:` labels were not created; the guidance says to create one
  on first use.

Wording only:

- `docs/upstream-upgrade.md` said no native planning workflow existed; it now names Linear. Its
  search for the old release number excludes "the archived local tracker" instead of "the tracker".
  The commands and their `':!.scratch'` exclusions are unchanged.

Left as they are:

- `docs/agents/domain.md`: it names no tracker.
- Every file under `.scratch/`, and every citation of a `.scratch/` path in ADR 0003, the fork
  specification (ticket 19, twice, the list of fork-owned paths and one `':!.scratch'` argument),
  two docstrings under `verify/team-analytics-stack/`, `ruff.toml` and earlier evidence. They cite
  the historical record or are path arguments, and the record stays where they point.
- Citations of a local ticket by number alone: "ticket 27" twice in the upgrade procedure and
  "ticket 17 of the defect fixes" in the fork specification. The tracker guidance now says that a
  bare number names a ticket of the archive and that a Linear issue is cited as `SIP-NN`.

Not taken from `clearml-yolo`: its Spec Kit archive, release automation, task runner, Python
safeguards and `master` branch, none of which this repository has.

This repository is public and Linear is private. This file and the tracker guidance name the
Linear workspace, project and issue addresses, as the two sibling repositories do; the links open
only for members of the workspace.

## Local tickets

73 ticket files in five efforts, read at `2afbb331b`. None was edited, moved or removed.

| Effort | Tickets | Status in the file | In Linear |
| --- | --- | --- | --- |
| `.scratch/team-analytics/` | 19 | 18 `resolved`, 1 `wontfix` (ticket 19) | not recreated |
| `.scratch/defect-fixes/` | 28 | 28 `resolved` | not recreated |
| `.scratch/standard-fork/` | 15 | 15 `resolved` | not recreated |
| `.scratch/team-analytics-admin-settings/` | 10 | 10 `resolved` | not recreated |
| `.scratch/task-progress/` | 1 | 1 `needs-triage` | migrated |

The 72 closed tickets stay historical records. Their status lines were taken as written:
`clearml-yolo`'s migration reconciled each status against acceptance evidence, and this one did
not judge the acceptance of closed tickets again. The four specs, the plan and the decisions ledger
beside them are kept the same way. One ticket was active and was migrated with its text, its open
questions and its comment:

| Original source | Linear issue |
| --- | --- |
| `.scratch/task-progress/issues/01-the-legend-hides-the-progress-bar-when-a-task-has-many-buckets.md` | [SIP-98](https://linear.app/sip-ds-team/issue/SIP-98/the-legend-hides-the-progress-bar-when-a-task-has-many-buckets), Backlog, `needs-triage` |

It had no blocker, so no blocking relation was created. Before creation, Linear was searched for
the source path and for the title and held neither; a retry must match the source path first.

## Independent review

A reviewer that wrote none of the change read the first commit (`07a02ee37`) against `2afbb331b`,
read-only, with the original files, the diff, `clearml-yolo`'s guidance and the skills that read
the tracker guidance. It was given the questions, not the author's conclusions. It could not read
Linear.

Nothing was rated high. It confirmed the ticket counts and statuses, the 79 unchanged files, the
14 links, the facts stated about the repository (default branch, no `.github/`, the pipeline not
installed as git hooks, its twelve hooks, the merge command, ADR 0005) and that a squash or rebase
merge of an upgrade PR removes the release from the ancestors of `main`. Its findings, all fixed in
the second commit:

- Medium: the wayfinding operations contradicted the general rules. A wayfinding ticket has no PR,
  so "Done only after a merged PR" never let it close, and it must carry no readiness label where
  the rule said every issue carries one. Both rules now except wayfinding.
- Medium: a canceled blocker now unblocks a wayfinding ticket, which this file did not record, and
  `clearml-yolo`'s rule that a canceled prerequisite means replanning was not carried over. The rule
  is added for implementation work, the wayfinding rule names all three closed states, and the
  change of meaning is recorded above.
- Medium: "never rebase the upgrade branch" appeared only at hand-off, after the long verification
  during which `main` can move, and the stacked-PR text invited a restack of such a branch. The rule
  is now beside the merge command in section 2, and the stacked-PR text excepts the branch.
- Low: applicable rules of `clearml-yolo`'s guidance were missing (current source before historical
  claims, merge order of dependencies, no assumed GitHub or Linear automation, stacked-PR links and
  cumulative verification, draft PRs, routine grouping, dated record of later transfers). Added.
- Low: this file's list of changes omitted the rules taken from `clearml-yolo`. Added above.
- Low: the flag `/triage` reads for PRs was absent. Added, as "no".
- Low: the map body was described by an outdated list of its sections. It now defers to the skill.
- Low: bare ticket numbers in two documents became ambiguous. Recorded above and resolved by one
  rule in the tracker guidance.
- Informational: Linear addresses in a public repository. Recorded above; the owner's to accept.

The fixes were checked by the author against each finding. They were not sent back to the reviewer.

## Checks

Run in the worktree on the committed tip of the second commit, 2026-11-17.

- Passed: `git diff --check origin/main HEAD`.
- Passed: `git diff --quiet origin/main HEAD -- .scratch`, so the 79 tracked files of the local
  tracker (73 tickets, four specs, one plan, one ledger) are byte-identical to `origin/main`.
- Passed: every relative link in `AGENTS.md`, the three files of `docs/agents/`,
  `docs/upstream-upgrade.md` and this file resolves to an existing file, and every heading anchor
  among them exists (a script written for this check and not kept).
- Passed: a search of `AGENTS.md`, `docs/agents/` and `docs/upstream-upgrade.md` finds no remaining
  instruction to create or update tickets under `.scratch/`.
- Passed: Linear readback. The project lists SIP-97 and SIP-98 and nothing else; SIP-98 carries the
  source path, the `needs-triage` label and a link to the original file.
- Not selected: the check pipeline (`prek.toml`) and the test stack. The change is Markdown only,
  and the pipeline's twelve hooks read the UI code, the fork's Python, the policies and three
  JavaScript suites, none of which changed.
- Not established: that a human merge through GitHub works as described. No PR had been merged in
  this repository when this was written, and `main` has no branch protection and no ruleset.
