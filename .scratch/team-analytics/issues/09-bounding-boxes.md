# 09: Bounding boxes

**What to build:** A team lead sees operations for bounding boxes specifically, can widen them to all shapes, and sees an alignment counted once per box however many drags it took. For that the UI starts recording which shape each action touched. See Bounding box, All shapes and Alignment in `GLOSSARY.md`, the UI logging section of the spec (`../spec.md`) and ADR 0002.

**Blocked by:** 08 (Operations and time per operation, all shapes).

**Status:** ready-for-agent

- [ ] The existing draw, paste, propagate, drag, resize and delete events carry the shape type, the number of single-frame rectangles among the objects, whether the object is a single-frame shape or a track, and, for drag and resize, a reference to the object and the frame.
- [ ] No new event type is sent, and every added record carries its project, task and job.
- [ ] Nothing is recorded outside a job, and only the 2D canvas is instrumented.
- [ ] A failure inside the added logging never reaches the code that called it, and annotation behaves exactly as before.
- [ ] A bounding box is a single-frame rectangle; a rectangle track counts only under all shapes.
- [ ] The page has a switch between Bounding boxes and All shapes that applies to every operation figure.
- [ ] For a period with shape-tagged events the page opens on Bounding boxes; for a legacy period it shows all shapes with the notice.
- [ ] Consecutive drags and resizes of the same object by the same person are one alignment; an operation on another object or a change of frame ends it; returning to the object later is a new alignment.
- [ ] The time of an alignment runs from the action before its first drag to the end of its last.
- [ ] Legacy drags and resizes, which carry no object reference, each count as one alignment.
- [ ] The events the UI sends are tested at the boundary to the server; the figures are tested through the service's read interface.
