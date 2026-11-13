# 08: Operations and time per operation, all shapes

**What to build:** A team lead sees how many objects were created, aligned and deleted, how long each kind of operation takes on average, and how working time divides between them and Other. This ticket uses only events CVAT already records, so it works for any past period and delivers the legacy-period view. See Operation, Time per operation, Idle pause and Other in `GLOSSARY.md`, and the spec (`../spec.md`).

**Blocked by:** 02 (Tracer: working time per annotator for the last week).

**Status:** ready-for-agent

- [ ] Creation counts objects drawn, pasted or propagated; deletion counts objects removed; alignment counts each drag or resize.
- [ ] Operations count what people did: a creation that is undone and redone is two creations and no deletion.
- [ ] Time per operation runs from the person's previous action to the end of the operation.
- [ ] A pause longer than 100 seconds before an action is dropped, and that action is left out of the average.
- [ ] Navigation that happens while an object is being drawn or adjusted gives its time to that operation.
- [ ] Other is the working time not spent on an operation, computed for the scope being displayed and never shown below zero, including for a batch of events that spans a project switch and an hour boundary.
- [ ] A chart shows how working time divides between the operations and Other, with its legend inside the card and shares readable without hovering.
- [ ] A table lists each operation with its count, average time, total time and share of working time.
- [ ] Headline figures show objects created and the average time to create one.
- [ ] For a period with no shape-tagged events the page shows the legacy-period notice and marks class change as not recorded.
- [ ] The figures respect the period and, once ticket 07 is in, the project and annotator filters.
