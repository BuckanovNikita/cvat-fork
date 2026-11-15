# 23: Overview bars split by operation

**What to build:** The overview's bars for working time by annotator and by project are split by operation, with a legend, as the prototype shows. Today they are single-colour bars and the split exists only in the full view. See Overview and Full view in `GLOSSARY.md` and "Page" in the spec (`../spec.md`).

**Blocked by:** 05 (First lint run on the fork's UI code), 14 (Unprocessed periods carry no figures).

**Status:** resolved

- [x] Test first, through the service's read interface: each overview row by annotator and by project carries its operation parts, and they equal that row in the full view.
- [x] The remainder row carries the parts of the rows it stands for.
- [x] For a period that is not fully processed the parts are null like every other figure.
- [x] In a legacy period the split follows what the full view shows for that period.
- [x] The overview asks no extra question per row.
- [x] Test first, on the page with supplied answers: the two cards draw each bar as segments in the full view's colours, with a legend, and still show the row's working time.
- [x] The look was checked in a browser on the stack at 1400 px and at 400 px (layout measured, screenshots looked at) and compared with the prototype's source and the design text; the prototype itself was not rendered beside it.

## Comments

**2026-11-14:** Evidence is in `docs/evidence/2026-11-14-overview-bars-split-by-operation.md`. The rows and the rest come from the full view's own row read (`team_analytics/rows.py`), and the bars from the full view's part logic (`operations.ts`). "No extra question per row" is a stated check (query log, 4 rows against 16), not a kept test. The last criterion is ticket 27's.

What ticket 27's browser run should look at, beside `docs/design/team-analytics/prototype/Main.dc.html` (and `Narrow.dc.html` for 400 px):

- At 1400 px: the two cards side by side. Each bar is 16 px high, split into Creation, Alignment, Class change, Deletion and Other, in the operations table's colours and with 2 px gaps. The longest bar is the full width and the others are in proportion. Hovering a part names the row, the operation and its hours. The legend sits above the rows, inside the card. The row's hours still show at the right of its name, and the selected row is still highlighted. The rest line is text only, as in the prototype. Compare a row with its row in the full view: same parts, same order. A row with no time in some operations shows the 2 px gaps of its empty parts at the bar's end, as the full view's bars do.
- At 400 px: the cards stack. The legend wraps onto two lines inside the card, and no bar, legend or name pushes the page sideways. Long names are cut with an ellipsis. Watch the smallest rows of the top eight: with five parts and four 2 px gaps, a bar narrower than about 8 px shows gaps and no colour. The single-colour bar used to keep a 2 px sliver.
- In a legacy period (a month before the cutover): no Class change in the legend or the bars.
- One known difference: the prototype puts the name, the bar and the hours on one line. The page keeps its existing row, with the name and hours on top and the bar under them. This ticket changed the bar, not the row layout.

**2026-11-14:** Merged into `feat/team-analytics-page` in `6a442e9a`. Evidence is in `docs/evidence/2026-11-14-overview-bars-split-by-operation.md`. The ticket stays open: its last criterion, the look beside the prototype in a browser, is outstanding and belongs to ticket 27's run.

**2026-11-15:** Follow-up to the independent review of tickets 23 and 24 (branch `fix/page-review`; the review, its six findings and what was done about each are in `docs/evidence/2026-11-14-overview-bars-split-by-operation.md`, "Independent review, 2026-11-15"). Two findings changed this ticket's cards:

- The overview bars' legend and the "where working time goes" list shared class names, so each took the other's spacing, lines and layout. Each now has its own (`b5743f8a`); a compiled-style probe found four rules reaching both before and none after. What either shows is unchanged, but both now render differently from an image built before the change.
- A row without operation parts was drawn in Creation's colour. It is now one neutral grey bar (`#595959`, in no legend colour) with a hover ending "not split by operation", and the legend stays (`27a62f78`, three seam 3 tests seen failing first).

What ticket 27's browser run should also look at for these, at 1400 px and at 400 px:

- The bars' legend in both cards: the swatches and names on one line, wrapping inside the card on a narrow window, with the "Select a row to filter the whole page" hint beside them. No 1 px line above any item and no extra vertical padding between items.
- "Where working time goes": the legend is a list under the bar, one operation per line with its swatch, name, hours and share (share right-aligned), each line under a thin 1 px line with 7 px of padding above and below. It is no longer laid out as a wrapping row with space between items, and its type is the card's normal size, not 12 px.
- A row without parts, if an older service can be put in front of the page: one dark grey bar, clearly unlike Other's light grey, and its hover saying it is not split.

The last criterion stays unticked; it remains ticket 27's.

**2026-11-15:** The review follow-up (`fix/page-review`) was merged into `feat/team-analytics-page` in `bd1d00d9`. Evidence is in `docs/evidence/2026-11-14-overview-bars-split-by-operation.md` ("Independent review, 2026-11-15"). On the merged tree, seam 3, UI logging and `prek run --all-files` passed with nothing skipped. The ticket stays open; its last criterion belongs to ticket 27's browser run.

2026-11-15: The code review of the integrated branch (finding 4, recorded in `docs/evidence/2026-11-15-integrated-branch-review.md`) is recorded, not fixed. The overview's rows by annotator and by project each run the full view's whole row read, and that one shared read is what keeps an overview row's split equal to the full view's. Overview latency is outside this spec. The fork specification now lists the cost as known and not measured at scale.

2026-11-15: The last criterion, restated as what was shown, is ticked from ticket 27's final run (evidence: `docs/evidence/2026-11-15-final-run-on-a-fresh-stack.md`, "The look beside the prototype"). `run.sh check-fixes look` measured both cards at 1400 px and 400 px on `ta-org-c` (every row in several parts) and on the volume's organization (eight rows, long names; its rows are almost all creation, so their bars are one part), and the full-page screenshots were looked at and compared with `Main.dc.html`, `Narrow.dc.html` and `design.md`. The prototype was not rendered: its sources need the design canvas's runtime. Differences seen are listed in the evidence: the row layout (name and hours above the bar), the legend's added hint and its wrap at 400 px, the gaps of empty parts showing before Other rather than at the bar's end; no neutral bar was seen, since every row came with its parts. Hover titles were not checked.

2026-11-15: Resolved on `feat/team-analytics-page` by merge `ba33aeb4` (ticket 27's final run); the look in a browser on the stack, compared with the prototype's source and not with a rendered prototype, is in `docs/evidence/2026-11-15-final-run-on-a-fresh-stack.md`.
