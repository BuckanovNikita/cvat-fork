# 22: A group move is one alignment per object

**What to build:** Several objects dragged together count as one alignment for each object moved, sharing the time of the gesture equally. Moving the selection box counts the same way. Today a group drag is one alignment of the grabbed object, and moving the selection box is nothing. See Alignment in `GLOSSARY.md`, "UI logging" and "Service: refresh" in the spec (`../spec.md`), and ADR 0002.

**Blocked by:** 05 (First lint run on the fork's UI code), 19 (A redo is not a creation).

**Status:** resolved

- [x] First, the event is fixed in the logging contract: one drag event for the gesture, carrying the number of objects moved, how many of them are bounding boxes, and a mark that it is a group. No new event type.
- [x] Test first, at the boundary where the UI sends events: a group drag of three boxes sends one group event for three objects. CVAT's own log of the grabbed shape is still sent and is not counted a second time. Moving the selection box sends the same group event.
- [x] Test first, through the service's read interface: a group event of three objects and six seconds is three alignments of two seconds each.
- [x] A group that mixes boxes and other shapes counts only its boxes under Bounding boxes, with the time split as for any mixed selection.
- [x] A group move ends the alignment runs before it and is not continued by a later drag: a drag of a box, a group move that includes it, and another drag of it are three alignments of that box. This is a default the owner was not asked about.
- [x] Single drags and resizes count exactly as before, and legacy drags without an object reference are still one alignment each.
- [x] CVAT's own logging is unchanged, and a failure in the added logging never reaches the code that called it.
- [x] The ticket states what happens to hours already stored under the old rule, and the fork specification says the same.

## Comments

2026-11-14: Implemented on `ticket/22-group-move`; evidence in
`docs/evidence/2026-11-14-group-move.md`. The event: one `drag:object` with
`count` = objects moved and payload `group` = `move` (plus the shape fields);
CVAT's own drag of the grabbed object is still sent with `group` = `grabbed`
and is no operation. Hours already stored: a changed rule recomputes nothing.
Hours whose events came from a UI without the group event read the same under
the new rule. Hours from the new UI stored by a service without the new rule
keep a group drag as two alignments (a selection-box move as one) until the
day is computed again. Recent hours follow the new rule from the next
refresh, and an older day only once its raw event count, or a neighbour's,
changes. The fork specification says the same (TA-1, "Known limit of the
stored totals"). Not shown here: a group drag in a real browser (ticket 27).

2026-11-14: Merged into `feat/team-analytics-page` as `50895e77`, without conflicts. On the merged tree `node --test verify/team_analytics_logging.cjs` ran 70 tests and `node --test verify/team_analytics_page.cjs` 209, 0 failed and 0 skipped each; the skip-gate grep finds nothing. The service suite was not run by the merger. Evidence: `docs/evidence/2026-11-14-group-move.md`.
