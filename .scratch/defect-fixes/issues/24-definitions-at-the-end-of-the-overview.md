# 24: Definitions at the end of the overview

**What to build:** The overview ends with short definitions, so a maintainer can check what a figure means without leaving the page. The design asks for them and the prototype shows them; they were never built. See the design under `docs/design/team-analytics/` and "Page" in the spec (`../spec.md`).

**Blocked by:** 05 (First lint run on the fork's UI code).

**Status:** resolved

- [x] Test first, on the page with supplied answers: the overview ends with a definitions block that covers the terms the design names.
- [x] Each definition is worded from `GLOSSARY.md`; where the prototype's wording differs, the glossary wins.
- [x] The block is part of the overview and is not shown in a full view.
- [x] It stays inside the page's column in a narrow window: on the stack at 400 px the block is one column inside the page's column and the window; at 1400 px it is four columns below the details table, after every card.
- [x] No service change is needed.

## Comments

2026-11-14: Built in `definitions.tsx` and `definitions.scss`, mounted once after the details table in the overview branch of `team-analytics-view.tsx`. Evidence: `docs/evidence/2026-11-14-definitions-at-the-end-of-the-overview.md`.

- Terms. `design.md` asks for "short definitions" and names no terms. The set is the prototype's four (`Main.dc.html`): Session, Working time, Time per operation, Model.
- Glossary over prototype. Each difference, with the glossary's text used:
  - Session. The prototype says "work inside jobs"; the glossary says "job work by one person". The prototype leaves out "at most a day long". Its "A pause longer than 5 minutes starts a new session" becomes "A pause longer than five minutes ends it" (the glossary's sentence with the session gap inlined). Its "only sessions that touched that project are counted" becomes the glossary's sentence, which also says the length is only the time spent inside the project.
  - Working time. The prototype says "The server's own figure, the same one the Grafana dashboard shows, counted for the project of the job". The glossary has no "counted for the project of the job"; it says "It is the only total: every breakdown of time adds up to it", which the prototype lacks.
  - Time per operation. The prototype says "the annotator's previous action to the end of this one"; the glossary says "a person's previous action to the end of the operation", and adds that finding, deciding and pointing are part of it. The prototype's "Pauses over 100 seconds are left out" becomes "A pause longer than 100 seconds before an action belongs to no operation" (the glossary's Idle pause, its two sentences joined).
  - Model. The prototype says "Boxes saved by technical accounts or made with the built-in detector. The server records no time for them, so they have counts only." The glossary's two sentences replace it: "Created without a person drawing it: ..." and "Model boxes have counts but no time."
- Wording check. A one-off script compared each sentence with `GLOSSARY.md`: seven sentences are verbatim. The two composed ones are the five-minute and the 100-second sentences named above.
- Narrow window (criterion 4, not ticked). Seen: at seam 3 the block is the last child of `.cvat-team-analytics-cards`, the page's grid. In the styles it spans that grid (`grid-column: 1 / -1`), has `min-width: 0`, lays its items in `repeat(auto-fit, minmax(min(100%, 280px), 1fr))`, and each item has `min-width: 0` and `overflow-wrap: anywhere`. Not seen: rendering, which needs a browser. Ticket 27 should check at 400 px that the definitions are one column, inside the page's column, with no sideways scroll, and at 1400 px that they sit in several columns below the details table, as in the prototype.
- No service change. The diff touches only the page directory and the seam 3 tests, and the supplied answers carry no new field.

2026-11-14: Merged into `feat/team-analytics-page` in `7ce5a449`. On the merged tree: ESLint, stylelint and the UI type check pass; `definitions.scss` compiles with the UI's Sass against `base` (the stylesheet the evidence file lists as not compiled); seam 3 and UI logging pass with nothing skipped. Outstanding: criterion 4, the narrow window, needs a browser and is left for ticket 27, so the ticket stays open.

2026-11-15: Follow-up to the independent review of tickets 23 and 24 (branch `fix/page-review`; the review is in `docs/evidence/2026-11-14-overview-bars-split-by-operation.md`, "Independent review, 2026-11-15", and this ticket's evidence points to it). The definitions held. One finding is recorded and nothing changed: when a row's operation time exceeds its working time, Other is clamped at zero and the parts fill the bar, in the full view as before and now in the overview's bars, so for such a row the parts shown add up to more than its working time, while the definitions block says of working time that every breakdown of time adds up to it. That is the service's rule, and the owner was not asked about the wording beside it. Written into `docs/fork-specification.md` ("Known limit of the split by operation"). The glossary and the block are not reworded; that is an open decision for the owner. Criterion 4 stays with ticket 27.

2026-11-15: The narrow-window criterion, restated as what was shown, is ticked from ticket 27's final run (evidence: `docs/evidence/2026-11-15-final-run-on-a-fresh-stack.md`): at 400 px the definitions are one column, inside the page's column and the window, after every card and below the details table; at 1400 px they are four columns there; a full view shows none. The page itself fits the window at 400 px; the document still scrolls sideways because CVAT's own header keeps the app 1025 px wide, as before.

2026-11-15: Resolved on `feat/team-analytics-page` by merge `ba33aeb4` (ticket 27's final run); the narrow window on the stack is in `docs/evidence/2026-11-15-final-run-on-a-fresh-stack.md`.

2026-11-15: Reversed by the owner's later decision. The definitions move into tooltips on the terms they explain (ticket 04 of `.scratch/team-analytics-admin-settings/`), and the block at the end of the Overview goes. The four texts and their glossary wording are kept; only where they are shown changes. This ticket's status is left as it was, since what it built was delivered.
