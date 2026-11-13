# 10: Class change

**What to build:** A team lead sees how often annotators change the class of an existing box and how long that takes. CVAT records nothing for this today, so the UI starts recording it. See Class change in `GLOSSARY.md`, the spec (`../spec.md`) and ADR 0002.

**Blocked by:** 09 (Bounding boxes).

**Status:** ready-for-agent

- [ ] Changing the label of an existing object is recorded wherever the UI allows it: in the object's sidebar entry, by the label hotkeys, and for a multiple selection.
- [ ] The record is carried inside an event type the stock server already accepts, with the number of objects, the shape fields from ticket 09 and the input method.
- [ ] Changing the class of several selected objects counts each object.
- [ ] Changing a class back counts again.
- [ ] Class change appears as the fourth operation in the operations table and in the split of working time, with count, average time, total time and share.
- [ ] Under Bounding boxes only single-frame rectangles are counted.
- [ ] For a legacy period class change is shown as not recorded rather than as zero.
- [ ] A failure inside the recording never affects the label change itself.
