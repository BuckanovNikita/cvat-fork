# 04: Definitions as tooltips

**What to build:** The definitions block at the end of the Overview becomes tooltips on the matching terms (item 7 of the spec). `definitions.tsx` becomes a `Term` component holding the four texts (Session, Working time, Time per operation, Model), worded as today from `GLOSSARY.md`. Each term is focusable and wrapped in an antd `Tooltip` that opens on hover and on keyboard focus; the tooltip renders outside the scrolling tables, so nothing clips it. The block and its render in `team-analytics-view.tsx` go.

Placement: Session on the "Sessions" label and the details header; Working time on the card titles and the details header; Time per operation on the "Avg time" headers and "Avg time per box"; Model on the Model row and the details header. Overview only; Full views are unchanged.

This reverses ticket 24 of `.scratch/defect-fixes/`, which placed the definitions at the end of the Overview.

**Blocked by:** 03 (both change the operations card).

**Status:** ready-for-agent

- [ ] `verify/team-analytics-page/definitions.test.cjs` is rewritten: the Overview no longer ends with a definitions block.
- [ ] Each of the four terms appears where the placement list says, and hovering it or giving it keyboard focus shows its definition.
- [ ] The texts are the current ones, word for word, so they still match `GLOSSARY.md`.
- [ ] A Full view shows no term tooltips and no definitions block.
- [ ] The tooltip renders outside the card's scrolling area (not inside the table's container), so a narrow card does not clip it.
- [ ] On the live stack (browser step of ticket 08): hovering a term on the Overview shows its tooltip.

## Comments
