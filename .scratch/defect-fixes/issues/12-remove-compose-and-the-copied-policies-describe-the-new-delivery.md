# 12: Remove Compose and the copied policies; describe the new delivery

**What to build:** Nothing in the repository suggests a Compose path or a second copy of the policies any more, and the documents describe delivery as it now is: three images, the patch inside the import, checks on Kubernetes. See "Stack and removals" and "Documents" in the spec (`../spec.md`).

**Blocked by:** 09 (Issue and comment permissions checked on the stack), 10 (Task progress checked on the stack).

**Status:** ready-for-agent

- [ ] The Compose overlay, the three Compose verification files, the two Compose launchers and the copied policy directory are deleted. Seed and check scripts the stack uses stay; the others go with them.
- [ ] A search for their names finds only history, dated evidence and the ledger.
- [ ] The fork specification describes packaging and policy delivery as built: the three images, the in-place patch, the bundle check.
- [ ] The upgrade procedure covers refreshing the mirror with the widened list, merging the policies with the import, running the policy test from the repository and rebuilding the server image. No step mentions Compose or a mount.
- [ ] The Team Analytics spec gets a dated comment that its lines on the stock backend, the chart download and the Compose checks are superseded by ADR 0004 and the amended ADR 0003.
- [ ] The READMEs are updated, and the infrastructure migration note records its outcome.
- [ ] A stack `up` still passes after the removal.
- [ ] The delivery change as integrated (policies, image, stack, removals) gets an independent review.
