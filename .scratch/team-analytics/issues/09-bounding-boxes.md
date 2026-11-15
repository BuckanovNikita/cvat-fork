# 09: Bounding boxes

**What to build:** A team lead sees operations for bounding boxes specifically, can widen them to all shapes, and sees an alignment counted once per box however many drags it took. For that the UI starts recording which shape each action touched. See Bounding box, All shapes and Alignment in `GLOSSARY.md`, the UI logging section of the spec (`../spec.md`) and ADR 0002.

**Blocked by:** 08 (Operations and time per operation, all shapes).

**Status:** resolved

- [x] The existing draw, paste, propagate, drag, resize and delete events carry the shape type, the number of single-frame rectangles among the objects, whether the object is a single-frame shape or a track, and, for drag and resize, a reference to the object and the frame.
- [x] No new event type is sent, and every added record carries its project, task and job.
- [x] Nothing is recorded outside a job, and only the 2D canvas is instrumented.
- [x] A failure inside the added logging never reaches the code that called it, and annotation behaves exactly as before.
- [x] A bounding box is a single-frame rectangle; a rectangle track counts only under all shapes.
- [x] The page has a switch between Bounding boxes and All shapes that applies to every operation figure.
- [x] For a period with shape-tagged events the page opened on Bounding boxes on the stack, with no shape choice in the address.
- [ ] For a legacy period the page shows all shapes with the notice: shown by the page suite only; not seen on the stack.
- [x] Consecutive drags and resizes of the same object by the same person are one alignment; an operation on another object or a change of frame ends it; returning to the object later is a new alignment.
- [x] The time of an alignment runs from the action before its first drag to the end of its last.
- [x] Legacy drags and resizes, which carry no object reference, each count as one alignment.
- [x] The events the UI sends are tested at the boundary to the server; the figures are tested through the service's read interface.

## Comments

2026-11-14: Resolved on `feat/team-analytics-page` by merge `0643537`. Review fixes that followed are in merge `401576e`. Live results, review outcomes and what remains unverified: `docs/evidence/2026-11-14-team-analytics-final-run.md`.

2026-11-15: Ticket 27 of the defect fixes restated this criterion, ticked on a reading (decisions ledger, V11), and split it: the stack part is ticked, the legacy part is not. Original wording: "For a period with shape-tagged events the page opens on Bounding boxes; for a legacy period it shows all shapes with the notice." Evidence: `docs/evidence/2026-11-15-final-run-on-a-fresh-stack.md`.
