# Issue tracker: Linear and GitHub PRs

Active requirements, specs, implementation plans, acceptance criteria, dependencies, discussion and status live in Linear: team `SIP`, project `cvat-fork`. Resolve an issue by its identifier (`SIP-NN`) or URL. GitHub PRs in `BuckanovNikita/cvat-fork` own implementation review and delivery. Link issues, PRs and evidence in both directions.

Linear is private and this repository is public: PR descriptions, commit messages and committed evidence are readable by anyone.

**PRs as a request surface: no.** `/triage` reads this flag; a PR is a delivery of a Linear issue, not a request.

## Conventions

- **Feature**: one parent issue whose description is the spec. Its implementation tickets are sub-issues, one issue per ticket.
- **Implementation ticket**: the description records the outcome, scope, an implementation plan where needed, compatibility constraints, acceptance criteria as a checklist, and the selected verification.
- **Blocking**: Linear's native blocked-by relation.
- **State**: one lifecycle state (Triage, Backlog, Todo, In Progress, In Review, Done, Canceled, Duplicate) and, outside wayfinding, one readiness label ([triage labels](triage-labels.md)). A ready label does not override an open blocker. An issue awaiting triage sits in Triage with `needs-triage`.
- **Discussion**: Linear comments on the issue.
- **Vocabulary and decisions**: `GLOSSARY.md` and `docs/adr/` ([domain docs](domain.md)). The behavior to preserve is in the [fork specification](../fork-specification.md).

## When a skill says "publish to the issue tracker"

Search Linear for an existing issue first, then create the issue in team `SIP`, project `cvat-fork`.

## When a skill says "fetch the relevant ticket"

Read the issue by its identifier or URL, with its comments and relations.

## Lifecycle and acceptance

Start dependent work only when its prerequisite is implemented and verified on the branch used as its base; the dependency still orders the merges. Outside wayfinding, a canceled prerequisite requires replanning or removing the dependent work, never silently bypassing it. Move an issue to In Review when the implementation and its selected verification are ready for review. Mark it Done only after its changes reach `main` through a merged PR and its acceptance criteria are satisfied. Verification-only work completes on its recorded acceptance outcome, a wayfinding ticket on its recorded answer, and a wayfinding map when the skill calls it done.

Record evidence with the source revision, the environment, the checks actually run and their outcomes, exclusions, reuse reasons and remaining limitations. Dated evidence files stay in `docs/evidence/`; link them from the issue. The repository has no CI, because the fork deletes upstream's `.github/`: run the selected checks of the [upgrade procedure, section 4](../upstream-upgrade.md#4-verify-the-integrated-changes) locally and record their outcomes in the issue and the PR. Confirm a GitHub check, a branch protection or a Linear automation exists before relying on it. Required verification that is deferred blocks merge readiness.

## Delivery

- **Branch and PR**: one task branch and one PR against `main` for a cohesive feature, with several tickets in it when they belong together; routine grouping needs no approval. Link every included issue and map its acceptance criteria to the implementation and the evidence. Keep those issues open until the PR merges. A draft PR may hold incomplete work.
- **Who does what**: agents commit task-owned work with Conventional Commits, push task branches to `origin` and open PRs. Humans merge. `main` changes only through a human-merged PR: an agent session never pushes `main` and never delivers by merging into it locally. Explicit session limits take precedence.
- **Upstream release PRs**: a PR whose branch merges an upstream release tag ([upgrade procedure](../upstream-upgrade.md)) is merged with **Create a merge commit**, and its description says so. A squash or rebase merge drops the release's parent and breaks the join to upstream's history ([ADR 0005](../adr/0005-a-full-source-fork-joined-to-upstream-history.md)). Such a branch takes later commits of `main` by merge and is never rebased.
- **Review**: changes to behavior, interfaces, dependencies, security or operational policy get a fresh independent review after integrated verification. Wording edits may be self-reviewed.
- **Stacked PRs**: optional, for separate review units or dependency order. Record the grouping in Linear before implementation. The first PR targets `main` and each descendant targets its parent branch; link the parent PRs and the merge order. Review the incremental diffs and verify the cumulative feature delta against `main`, recording the base and head revisions. Humans merge bottom-up; after each merge, retarget or restack the remaining branches (an upstream release branch by merge only), inspect the resulting diffs, reassess whether the evidence still applies and repeat the affected checks and review. Use force-with-lease only on task-owned branches.
- **Images and deployment**: publishing an image and deploying each need their own authorization.

## Wayfinding operations

Used by `/wayfinder`. The **map** is one issue with **child** issues as tickets. Maps and tickets carry `wayfinder:` labels only, never a readiness label.

- **Map**: one issue labelled `wayfinder:map`, holding the map body the skill defines.
- **Child ticket**: a sub-issue of the map with the question in its description and a `wayfinder:<type>` label (`research`/`prototype`/`grilling`/`task`). Create a missing `wayfinder:` label on first use.
- **Blocking**: the native blocked-by relation. A ticket is unblocked when every blocker is closed: Done, Canceled or Duplicate.
- **Frontier**: the map's open sub-issues with no open blocker and no assignee; first in map order wins.
- **Claim**: assign the issue to the dev driving the map, as the session's first write.
- **Resolve**: post the answer as a comment, set the issue to Done, then append a context pointer (gist + link) to the map's Decisions-so-far.
- **Rule out of scope**: set the ticket to Canceled.

## Local tracker archive

`.scratch/` holds the local Markdown tracker used until 2026-11-17: specs, plans, tickets and their `Status:` lines. Linear supersedes it. The files stay as they are, as the record that documents, evidence and code comments cite by path; read them for history and for where a requirement came from, and check the current source and configuration before relying on a claim made there. A ticket cited by number alone ("ticket 27", "ticket 17 of the defect fixes") is a ticket of this archive; a Linear issue is always cited as `SIP-NN`.

A requirement needed for active work is transferred into a Linear issue that names its original path, after a search for an issue already carrying that path, and the transfer is recorded in dated evidence. The first mapping of local tickets to Linear issues is in the [migration evidence](../evidence/2026-11-17-linear-migration.md).
