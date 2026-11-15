# 12: Remove Compose and the copied policies; describe the new delivery

**What to build:** Nothing in the repository suggests a Compose path or a second copy of the policies any more, and the documents describe delivery as it now is: three images, the patch inside the import, checks on Kubernetes. See "Stack and removals" and "Documents" in the spec (`../spec.md`).

**Blocked by:** 09 (Issue and comment permissions checked on the stack), 10 (Task progress checked on the stack).

**Status:** resolved

- [x] The Compose overlay, the three Compose verification files, the two Compose launchers and the copied policy directory are deleted. Seed and check scripts the stack uses stay; the others go with them.
- [x] A search for their names finds only history, dated evidence and the ledger.
- [x] The fork specification describes packaging and policy delivery as built: the three images, the in-place patch, the bundle check.
- [x] The upgrade procedure covers refreshing the mirror with the widened list, merging the policies with the import, running the policy test from the repository and rebuilding the server image. No step mentions Compose or a mount.
- [x] The Team Analytics spec gets a dated comment that its lines on the stock backend, the chart download and the Compose checks are superseded by ADR 0004 and the amended ADR 0003.
- [x] The READMEs are updated, and the infrastructure migration note records its outcome.
- [x] A stack `up` still passes after the removal.
- [x] The delivery change as integrated (policies, image, stack, removals) gets an independent review.

## Comments

2026-11-15: Criteria 1 to 6 done on `ticket/12-remove-compose`: removal `2ad619ca`, documents `d05adde1`, merge of the integration branch `130c3696`. What went, what stayed and why, the name search and its hits, and the check pipeline's result are in `docs/evidence/2026-11-15-compose-removed.md`. Outside history and dated evidence the search finds one removed name: `opa/` in ADR 0004's statement of the removal, a decision record.

Outstanding: a stack `up` after the removal (criterion 7). The stack was in use by ticket 26, and no launcher was run for this ticket; the run waits until the stack is free. The independent review (criterion 8) follows the merge and is not this ticket's work.

2026-11-15: The removal and the documents are merged into `feat/team-analytics-page` in merge `740f4a9b`; evidence `docs/evidence/2026-11-15-compose-removed.md`. Still outstanding: a stack `up` after the removal, which waits for the stack to be free, and the independent review of the delivery change.

2026-11-15: Raised by the independent review of the delivery change (finding 4): the removal was merged (`740f4a9b`) after both live checks it waited for had passed on the stack (ticket 09's matrix and ticket 10's task progress), and before a fresh `up` and `down` on the integrated tree. Criterion 7 stays unticked; ticket 27's final run, a fresh `up`, `up`, `down`, shows it.

2026-11-15: The independent review of the delivery change as integrated is done (criterion 8): who reviewed, the verdict, the nine findings and what branch `fix/delivery-review` did about each, the failing cases before and the outcomes after, what held and what was not checked are in `docs/evidence/2026-11-15-compose-removed.md`, "Independent review of the delivery change, 2026-11-15".

2026-11-15: Criterion 7 shown in ticket 27's final run (evidence: `docs/evidence/2026-11-15-final-run-on-a-fresh-stack.md`): a fresh `up` from an empty namespace passed on the tree without the Compose files (second attempt; the first stopped at CVAT's sign-in throttle, fixed in the launcher), and so did a second `up` on the running stack (second attempt; the first failed the seed check on a stack holding the volume, fixed in `abb02a10`).

2026-11-15: Resolved on `feat/team-analytics-page` by merge `ba33aeb4` (ticket 27's final run); the stack `up` after the removal is in `docs/evidence/2026-11-15-final-run-on-a-fresh-stack.md`.
