# 10: Independent review, fixes, delivery

**What to build:** An independent review of the integrated work, the fixes it asks for, and delivery to the owner (item 10 of the spec).

- Two reviewers who wrote none of the work: (a) access, the first write endpoint and the user search, the SQL switch to user ids, and the order of save and generation; (b) the image build and the changed stack checks. One fixer applies the fixes; then the affected checks run again: the pipeline, the calculation suite if the app changed, both image builds and at least `preflight`, `up`, `check-settings` and `check-review` on a verification stack.
- Final images built at the branch tip, only now under the release tags `cvat/server:v2.82.0-fork` and `cvat/ui:v2.82.0-fork`. The previous server image is kept under a dated tag.
- The owner's stack (default namespace, port 8490) removed with `run.sh down` and installed fresh with `run.sh up` on those images; the page opened at `http://localhost:8490/team-analytics` as an administrator.
- The branch pushed, not merged.
- Clean-up: the work image tags, the verification namespace and its port-forward, agent worktrees and any process this work started.

**Blocked by:** 09.

**Status:** resolved

- [x] Both reviews are recorded with their findings, and each finding is fixed or answered with a reason.
- [x] After the fixes, the pipeline, the calculation suite (if the app changed), both image builds and `preflight`, `up`, `check-settings` and `check-review` pass again.
- [x] Both release images are built from the branch tip; the previous server image is kept under a dated tag named in the final report.
- [x] On the owner's stack, installed fresh: the filter bar, both selectors, the operations card, a tooltip and the settings modal are seen working as an administrator.
- [x] The branch is pushed and not merged; the work tags, the verification namespace, its port-forward, agent worktrees and started processes are gone.
- [x] The final report states what each check established, what stayed unverified, and every card other than the operations card that still scrolls sideways.

## Comments

2026-11-16: The independent review ran with three reviewers who wrote none of the code (backend and access, the page, and delivery: the image build, the stack checks and the documents), where this ticket planned two. None of their findings was rated high. Each finding, its fix or the reason it stays, and what the fixes were checked with are recorded in the dated evidence record (to be written).

2026-11-16: Delivered. The review ran in three passes by reviewers who wrote none of the code: three reviewers at `25adcb85a` (backend and access; the page; the image build, the stack checks and the documents), a second look at the fixes, and a third look at the commits after that. Nothing was rated high in any pass. Every finding of the first two passes is fixed or answered; the third pass's four low findings are recorded as limits in `docs/fork-specification.md` and in `docs/evidence/2026-11-16-open-lines-closed-and-admin-settings.md`, which holds the passes, the findings and what each fix was checked with.

After the fixes: the calculation suite ran whole on the final server image (370 tests, none failed); the check pipeline passed with twelve hooks at `9a8620e96`, in the working copy and in a fresh clone with dependencies installed from the locks at `0bf2f41cd`; the stack sequence ran from a clean start on the final images (the evidence record has every step). The commits after `9a8620e96` change documents only.

Release images: `cvat/server:v2.82.0-fork` built by `./build-server.sh` under the release tag, the same image the runs used (`7ead6d1cec4b`, every check passed). `./build-ui.sh` under the release tag gave an image with another id (`30adaed8cf00`) than the verified one; why the two builds of the same commit differ was not established (the UI build takes its context from the working copy, and no comparison of the two images was made). The release tag `cvat/ui:v2.82.0-fork` was pointed at the verified image (`1d1a6e3d425c`) instead, and the other image was dropped. The previous images are kept as `cvat/server:v2.82.0-fork-before-20261116` (`25b249e2e3e1`) and `cvat/ui:v2.82.0-fork-before-20261116` (`239758255066`).

The owner's stack (default namespace, port 8490) was removed with `run.sh down` and installed fresh with `run.sh up` on those images: both exit 0, every part of `up` passed. `run.sh check-fixes page` then passed against it as an administrator in a real browser: the filter bar's five controls 36 px at 1024, 1400 and 1920 px with Settings at the header's right end, the width sweep with no sideways scroll in the operations card, both selectors, the 13 terms' tooltips on hover and focus, the settings dialog with a save of the unchanged list, and project names at instance scope; its screenshots were looked at. Criterion 4 is ticked on that run and those screenshots, not on a person clicking through the page.

Clean-up: the work image tags are removed, the verification namespace is deleted with nothing left on its port, no agent worktree was created, and no process of this work is left running apart from the owner's stack and its port-forward. Cards other than the operations card that still scroll sideways: "How boxes are created" (creation methods) at every tested width from 1024 to 1920 px, and the details table from 1024 to 1288 px; at a 1024 px window the document is 79 px wider than the window on the Team Analytics page and on no other page of CVAT: the application's layout, with its header, takes the minimum width of the page's content (measured on the owner's stack; the evidence record has the figures). It was not compared against `main` and was not changed. The owner chose to leave other cards as they are.

2026-11-16, later: at the owner's word the work was put on `main` as one commit whose tree is this branch's tip, as the two earlier landings were. The single commits and the reviews stay on `feat/team-analytics-admin-settings`, which remains published; the commit ids cited in the tickets and in the evidence record are that branch's.
