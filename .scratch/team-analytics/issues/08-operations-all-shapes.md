# 08: Operations and time per operation, all shapes

**What to build:** A team lead sees how many objects were created, aligned and deleted, how long each kind of operation takes on average, and how working time divides between them and Other. This ticket uses only events CVAT already records, so it works for any past period and delivers the legacy-period view. See Operation, Time per operation, Idle pause and Other in `GLOSSARY.md`, and the spec (`../spec.md`).

**Blocked by:** 02 (Tracer: working time per annotator for the last week).

**Status:** resolved

- [x] Creation counts objects drawn, pasted or propagated; deletion counts objects removed; alignment counts each drag or resize.
- [x] Operations count what people did: a creation that is undone and redone is two creations and no deletion.
- [x] Time per operation runs from the person's previous action to the end of the operation.
- [x] A pause longer than 100 seconds before an action is dropped, and that action is left out of the average.
- [x] Navigation that happens while an object is being drawn or adjusted gives its time to that operation.
- [x] Other is the working time not spent on an operation, computed for the scope being displayed and never shown below zero, including for a batch of events that spans a project switch and an hour boundary.
- [x] A chart shows how working time divides between the operations and Other, with its legend inside the card and shares readable without hovering.
- [x] A table lists each operation with its count, average time, total time and share of working time.
- [x] Headline figures show objects created and the average time to create one.
- [ ] For a legacy period the page shows the legacy-period notice and marks class change as not recorded: shown by the page suite with supplied answers; the service now decides a legacy period from the stored cutover (fork specification, Legacy rule). Not seen on the stack, where all job work lies after the cutover.
- [x] The figures respect the period and, once ticket 07 is in, the project and annotator filters.

## Comments

2026-11-14: Resolved on `feat/team-analytics-page` by merge `d7494fe`. Review fixes that followed are in merge `401576e`. Live results, review outcomes and what remains unverified: `docs/evidence/2026-11-14-team-analytics-final-run.md`.

2026-11-15: Ticket 27 of the defect fixes restated the legacy-period criterion, ticked on a reading under a rule since replaced (decisions ledger, V11). Original wording: "For a period with no shape-tagged events the page shows the legacy-period notice and marks class change as not recorded." It is unticked: a fresh stack holds no legacy period with job work. Evidence: `docs/evidence/2026-11-15-final-run-on-a-fresh-stack.md`.
