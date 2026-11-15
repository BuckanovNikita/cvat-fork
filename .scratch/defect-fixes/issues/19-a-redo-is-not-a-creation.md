# 19: A redo is not a creation

**What to build:** Drawing a box, undoing it and redoing it counts as one creation. Today the redo counts as a second one, with a guessed creation method. See Operation and Creation in `GLOSSARY.md` and "Service: refresh" in the spec (`../spec.md`).

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Test first, through the service's read interface: draw, undo, redo gives one creation, Drawn, and the redo's time is under Other. The existing redo tests are changed and seen to fail before the fix.
- [x] The same holds after a paste and after a propagation: a redo adds no object to any creation method.
- [x] An undone creation still counts.
- [x] A redo still ends an alignment run: a drag of a box, a redo, and another drag of that box are two alignments. This is a default the owner was not asked about.
- [x] Operation shares still add up, and Other is never below zero.
- [x] Nothing changes in the UI; the redo event is sent as before.
- [x] The ticket states what happens to hours already stored under the old rule, and the fork specification says the same.

## Comments

**2026-11-14. Hours already stored under the old rule.** Nothing computes them again
because the rule changed. At start the service applies its schema and goes on with its
usual steps, so:

- The trailing refresh window (48 hours unless configured otherwise) is computed again
  at the next refresh and follows the new rule from then on.
- An older day keeps the figures it was stored with until it is computed again. That
  happens only when the daily check finds that its raw event count, or that of the day
  before or after it, changed.
- In hours stored under the old rule a redo of created objects stays a creation with its
  time, under the method of the creation it restored or as Drawn. Rows an earlier version
  stored as `redone` are still read as Drawn. The read queries are unchanged.
- A period can therefore hold hours of both rules.

`docs/fork-specification.md` (TA-1) says the same. This was read in the code and then
seen once on a throwaway ClickHouse, with the old calculation file standing for the
service before the upgrade: `docs/evidence/2026-11-14-redo-is-not-a-creation.md`. No
recount of stored history was added; that would be a new mechanism and a decision for
the owner.

**2026-11-14. Which redo ends an alignment run.** The same one as before this ticket:
a redo of created objects inside a job. A redo of anything else did not end a run and
still does not. The criterion's "a redo" is read as that one.

**2026-11-14. Criteria whose tests never went red on the old code.** "An undone creation
still counts" and the alignment default held before the fix and hold after it, so their
tests pin behaviour. The alignment test was seen to fail once the redo was no longer an
operation and not yet listed as ending a run, and to pass again when it was.

**2026-11-14. UI.** No file under `cvat/` changed, which is all this ticket shows for
that criterion. A redo made in the browser and read back from the events table belongs
to ticket 27.

2026-11-14: Resolved on `feat/team-analytics-page` by merge `ff5dda4`. Evidence: `docs/evidence/2026-11-14-redo-is-not-a-creation.md`.

2026-11-15: An independent review of tickets 19, 21 and 22 found the redo rule sound (a redo across a window edge gives 2 alignments and 0 creations), with no finding for this ticket. Recorded in `docs/evidence/2026-11-14-frame-navigation-hotkeys.md` ("Independent review, 2026-11-15"), with a pointer from this ticket's evidence. Nothing changed for this ticket.
