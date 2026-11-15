# 28: Security review of the branch

**What to build:** A completed security review of the work, which the first implementation never got. `main` was pushed on 2026-11-14 on the owner's instruction with this review outstanding, so it now covers what is already public as well as these fixes.

**Blocked by:** 27 (Final run on a fresh stack).

**Status:** resolved

- [x] A reviewer that did not write the code reviews everything on the branch since the last state that was reviewed.
- [x] It covers the policies and the role floor, the fork server image, the service's access rules and status, what the launcher pulls and applies, and secrets or local paths in tracked files and captured logs.
- [x] Each finding is fixed, or recorded with the reason it stands.
- [x] The report states what the push of 2026-11-14 already published, including the local path in history.
- [x] The report is kept in dated evidence.

## Comments

2026-11-15: The review of `fe87ffaf` found six findings; its report and what was done about each are in `docs/evidence/2026-11-15-security-review.md`. Done on branch `fix/security-review`, first step (no cluster): finding 2's idle connections fixed test first (closed after 120 s); finding 3's container restrictions added to the manifest; finding 4's guard checks turned into allowlists and replayed without a cluster; finding 5's service image build made local-only and shown with one build under a check tag, the vendored filter tool's hash recorded. Recorded with the reason they stand: finding 1 (trust model in the specification, `.scratch/team-analytics/issues/19-any-account-can-move-the-cutover-and-add-its-own-figures.md` for the owner), the worker pool and NetworkPolicy, the ClickHouse account and read limits, what the UI build pins by tag, finding 6 and the earlier findings still partly open. Outstanding: the live step (the service pod running under the new restrictions, `check-render` on the cluster, `up` and `down`), the owner's decision on finding 1, and the reviewer's second pass over the commits after `fe87ffaf`, these fixes included. Nothing is ticked until that pass.

2026-11-15 (later): The live step is done (evidence, part four). After merging the integration branch at `236b3878` and rebuilding the service image locally, one `up` from an empty namespace passed on the first attempt with the changed guard. The live `check-render` accepted the chart render and the earlier duplicate-key render: kubectl keeps the last key, so the guard judges what kubectl applies. The service pod ran under the new restrictions (no capabilities, no new privileges, the default seccomp profile), Ready with 0 restarts. `down` left nothing. Still outstanding: the owner's decision on finding 1 (Team Analytics issue 19) and the reviewer's second pass over the commits after `fe87ffaf`. Nothing ticked.

2026-11-15 (last): The reviewer's second pass over `fe87ffaf..02e5423d` is done (evidence, part five). All six findings are answered as claimed: findings 2 to 5 fixed in the parts named above, findings 1 and 6 and the rest of 2, 3 and 5 recorded with the reason each stands. The second pass added one low finding, recorded (a claim can bind an existing volume without naming it; the specification and the stack's README now name it as not judged), and a note on the upstream chart's Grafana defaults. The whole service suite passed on both ClickHouse images with the fixes. The evidence states what the push of 2026-11-14 published, the local path in history included, and what a push of the branch would add. All five criteria ticked. Resolved on `feat/team-analytics-page` by merge `02e5423d`. Waiting for the owner: finding 1 (Team Analytics issue 19), and whether anything public is to be withdrawn.
