# 10: Independent review, fixes, delivery

**What to build:** An independent review of the integrated work, the fixes it asks for, and delivery to the owner (item 10 of the spec).

- Two reviewers who wrote none of the work: (a) access, the first write endpoint and the user search, the SQL switch to user ids, and the order of save and generation; (b) the image build and the changed stack checks. One fixer applies the fixes; then the affected checks run again: the pipeline, the calculation suite if the app changed, both image builds and at least `preflight`, `up`, `check-settings` and `check-review` on a verification stack.
- Final images built at the branch tip, only now under the release tags `cvat/server:v2.82.0-fork` and `cvat/ui:v2.82.0-fork`. The previous server image is kept under a dated tag.
- The owner's stack (default namespace, port 8490) removed with `run.sh down` and installed fresh with `run.sh up` on those images; the page opened at `http://localhost:8490/team-analytics` as an administrator.
- The branch pushed, not merged.
- Clean-up: the work image tags, the verification namespace and its port-forward, agent worktrees and any process this work started.

**Blocked by:** 09.

**Status:** ready-for-agent

- [ ] Both reviews are recorded with their findings, and each finding is fixed or answered with a reason.
- [ ] After the fixes, the pipeline, the calculation suite (if the app changed), both image builds and `preflight`, `up`, `check-settings` and `check-review` pass again.
- [ ] Both release images are built from the branch tip; the previous server image is kept under a dated tag named in the final report.
- [ ] On the owner's stack, installed fresh: the filter bar, both selectors, the operations card, a tooltip and the settings modal are seen working as an administrator.
- [ ] The branch is pushed and not merged; the work tags, the verification namespace, its port-forward, agent worktrees and started processes are gone.
- [ ] The final report states what each check established, what stayed unverified, and every card other than the operations card that still scrolls sideways.

## Comments
