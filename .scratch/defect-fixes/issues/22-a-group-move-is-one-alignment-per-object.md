# 22: A group move is one alignment per object

**What to build:** Several objects dragged together count as one alignment for each object moved, sharing the time of the gesture equally. Moving the selection box counts the same way. Today a group drag is one alignment of the grabbed object, and moving the selection box is nothing. See Alignment in `GLOSSARY.md`, "UI logging" and "Service: refresh" in the spec (`../spec.md`), and ADR 0002.

**Blocked by:** 05 (First lint run on the fork's UI code), 19 (A redo is not a creation).

**Status:** ready-for-agent

- [ ] First, the event is fixed in the logging contract: one drag event for the gesture, carrying the number of objects moved, how many of them are bounding boxes, and a mark that it is a group. No new event type.
- [ ] Test first, at the boundary where the UI sends events: a group drag of three boxes sends one group event for three objects. CVAT's own log of the grabbed shape is still sent and is not counted a second time. Moving the selection box sends the same group event.
- [ ] Test first, through the service's read interface: a group event of three objects and six seconds is three alignments of two seconds each.
- [ ] A group that mixes boxes and other shapes counts only its boxes under Bounding boxes, with the time split as for any mixed selection.
- [ ] A group move ends the alignment runs before it and is not continued by a later drag: a drag of a box, a group move that includes it, and another drag of it are three alignments of that box. This is a default the owner was not asked about.
- [ ] Single drags and resizes count exactly as before, and legacy drags without an object reference are still one alignment each.
- [ ] CVAT's own logging is unchanged, and a failure in the added logging never reaches the code that called it.
- [ ] The ticket states what happens to hours already stored under the old rule, and the fork specification says the same.
