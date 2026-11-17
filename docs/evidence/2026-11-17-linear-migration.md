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
  label: it is the Done state. `wontfix` goes with the Canceled state.
- Delivery is a GitHub PR against `main`, pushed and opened by an agent and merged by a human. Until
  now work was merged locally and pushed to `main`. Pushing a task branch and opening a PR no
  longer need separate authorization; publishing an image and deploying still do.
- A PR that takes an upstream release is merged with a merge commit and its branch is never rebased
  (ADR 0005). This is new text: the repository allows merge, squash and rebase merges on GitHub, and
  nothing said which one an upgrade needs.
- The wayfinding operations keep their meaning with Linear objects: the map is an issue labelled
  `wayfinder:map`, a ticket is its sub-issue, blocking is the native relation, the claim is the
  assignee. The `wayfinder:` labels were not created; the guidance says to create one on first use.

Wording only:

- `docs/upstream-upgrade.md` said no native planning workflow existed; it now names Linear. Its
  search for the old release number excludes "the archived local tracker" instead of "the tracker".
  The commands and their `':!.scratch'` exclusions are unchanged.

Left as they are:

- `docs/agents/domain.md`: it names no tracker.
- Every file under `.scratch/`, and every citation of a `.scratch/` path in ADR 0003, the fork
  specification (ticket 19, twice, and the list of fork-owned paths), two docstrings under
  `verify/team-analytics-stack/`, `ruff.toml` and earlier evidence. They cite the historical record
  or are path arguments, and the record stays where they point.

## Local tickets

73 ticket files in five efforts, read at `2afbb331b`. None was edited, moved or removed.

| Effort | Tickets | Status in the file | In Linear |
| --- | --- | --- | --- |
| `.scratch/team-analytics/` | 19 | 18 `resolved`, 1 `wontfix` (ticket 19) | not recreated |
| `.scratch/defect-fixes/` | 28 | 28 `resolved` | not recreated |
| `.scratch/standard-fork/` | 15 | 15 `resolved` | not recreated |
| `.scratch/team-analytics-admin-settings/` | 10 | 10 `resolved` | not recreated |
| `.scratch/task-progress/` | 1 | 1 `needs-triage` | migrated |

The 72 closed tickets stay historical records; their status lines were taken as written and their
acceptance was not judged again. The four specs, the plan and the decisions ledger beside them are
kept the same way. One ticket was active and was migrated with its text, its open questions and
its comment:

| Original source | Linear issue |
| --- | --- |
| `.scratch/task-progress/issues/01-the-legend-hides-the-progress-bar-when-a-task-has-many-buckets.md` | [SIP-98](https://linear.app/sip-ds-team/issue/SIP-98/the-legend-hides-the-progress-bar-when-a-task-has-many-buckets), Backlog, `needs-triage` |

It had no blocker, so no blocking relation was created. Before creation, Linear was searched for
the source path and for the title and held neither; a retry must match the source path first.

## Checks

Run in the worktree on the working tree before the first commit, 2026-11-17.

- Passed: `git diff --check`.
- Passed: `git diff --quiet origin/main -- .scratch`, so the 79 tracked files of the local tracker
  (73 tickets, four specs, one plan, one ledger) are byte-identical to `origin/main`.
- Passed: every relative link in `AGENTS.md`, the three files of `docs/agents/`,
  `docs/upstream-upgrade.md` and this file resolves to an existing file, and every heading anchor
  among them exists (14 links, a script written for this check and not kept).
- Passed: a search of `AGENTS.md`, `docs/agents/` and `docs/upstream-upgrade.md` finds no remaining
  instruction to create or update tickets under `.scratch/`.
- Passed: Linear readback. The project lists SIP-97 and SIP-98 and nothing else; SIP-98 carries the
  source path, the `needs-triage` label and a link to the original file.
- Not selected: the check pipeline (`prek.toml`) and the test stack. The change is Markdown only,
  and the pipeline's twelve hooks read the UI code, the fork's Python, the policies and three
  JavaScript suites, none of which changed.
- Not established: that a human merge through GitHub works as described. No PR had been merged in
  this repository when this was written, and branch protection is not configured.
