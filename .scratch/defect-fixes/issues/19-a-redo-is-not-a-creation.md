# 19: A redo is not a creation

**What to build:** Drawing a box, undoing it and redoing it counts as one creation. Today the redo counts as a second one, with a guessed creation method. See Operation and Creation in `GLOSSARY.md` and "Service: refresh" in the spec (`../spec.md`).

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Test first, through the service's read interface: draw, undo, redo gives one creation, Drawn, and the redo's time is under Other. The existing redo tests are changed and seen to fail before the fix.
- [ ] The same holds after a paste and after a propagation: a redo adds no object to any creation method.
- [ ] An undone creation still counts.
- [ ] A redo still ends an alignment run: a drag of a box, a redo, and another drag of that box are two alignments. This is a default the owner was not asked about.
- [ ] Operation shares still add up, and Other is never below zero.
- [ ] Nothing changes in the UI; the redo event is sent as before.
- [ ] The ticket states what happens to hours already stored under the old rule, and the fork specification says the same.
