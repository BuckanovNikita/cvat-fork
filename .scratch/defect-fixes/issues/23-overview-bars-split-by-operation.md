# 23: Overview bars split by operation

**What to build:** The overview's bars for working time by annotator and by project are split by operation, with a legend, as the prototype shows. Today they are single-colour bars and the split exists only in the full view. See Overview and Full view in `GLOSSARY.md` and "Page" in the spec (`../spec.md`).

**Blocked by:** 05 (First lint run on the fork's UI code), 14 (Unprocessed periods carry no figures).

**Status:** ready-for-agent

- [x] Test first, through the service's read interface: each overview row by annotator and by project carries its operation parts, and they equal that row in the full view.
- [x] The remainder row carries the parts of the rows it stands for.
- [x] For a period that is not fully processed the parts are null like every other figure.
- [x] In a legacy period the split follows what the full view shows for that period.
- [x] The overview asks no extra question per row.
- [x] Test first, on the page with supplied answers: the two cards draw each bar as segments in the full view's colours, with a legend, and still show the row's working time.
- [ ] The look beside the prototype is checked in a browser in ticket 27.

## Comments

**2026-11-14:** Evidence is in `docs/evidence/2026-11-14-overview-bars-split-by-operation.md`. The rows and the rest come from the full view's own row read (`team_analytics/rows.py`), and the bars from the full view's part logic (`operations.ts`). "No extra question per row" is a stated check (query log, 4 rows against 16), not a kept test. The last criterion is ticket 27's.

What ticket 27's browser run should look at, beside `docs/design/team-analytics/prototype/Main.dc.html` (and `Narrow.dc.html` for 400 px):

- At 1400 px: the two cards side by side. Each bar is 16 px high, split into Creation, Alignment, Class change, Deletion and Other, in the operations table's colours and with 2 px gaps. The longest bar is the full width and the others are in proportion. Hovering a part names the row, the operation and its hours. The legend sits above the rows, inside the card. The row's hours still show at the right of its name, and the selected row is still highlighted. The rest line is text only, as in the prototype. Compare a row with its row in the full view: same parts, same order. A row with no time in some operations shows the 2 px gaps of its empty parts at the bar's end, as the full view's bars do.
- At 400 px: the cards stack. The legend wraps onto two lines inside the card, and no bar, legend or name pushes the page sideways. Long names are cut with an ellipsis. Watch the smallest rows of the top eight: with five parts and four 2 px gaps, a bar narrower than about 8 px shows gaps and no colour. The single-colour bar used to keep a 2 px sliver.
- In a legacy period (a month before the cutover): no Class change in the legend or the bars.
- One known difference: the prototype puts the name, the bar and the hours on one line. The page keeps its existing row, with the name and hours on top and the bar under them. This ticket changed the bar, not the row layout.
