# 04: Definitions as tooltips

**What to build:** The definitions block at the end of the Overview becomes tooltips on the matching terms (item 7 of the spec). `definitions.tsx` becomes a `Term` component holding the four texts (Session, Working time, Time per operation, Model), worded as today from `GLOSSARY.md`. Each term is focusable and wrapped in an antd `Tooltip` that opens on hover and on keyboard focus; the tooltip renders outside the scrolling tables, so nothing clips it. The block and its render in `team-analytics-view.tsx` go.

Placement: Session on the "Sessions" label and the details header; Working time on the card titles and the details header; Time per operation on the "Avg time" headers and "Avg time per box"; Model on the Model row and the details header. Overview only; Full views are unchanged.

This reverses ticket 24 of `.scratch/defect-fixes/`, which placed the definitions at the end of the Overview.

**Blocked by:** 03 (both change the operations card).

**Status:** resolved

- [x] `verify/team-analytics-page/definitions.test.cjs` is rewritten: the Overview no longer ends with a definitions block.
- [x] Each of the four terms appears where the placement list says, and hovering it or giving it keyboard focus shows its definition.
- [x] The texts are the current ones, word for word, so they still match `GLOSSARY.md`.
- [x] A Full view shows no term tooltips and no definitions block.
- [x] The tooltip renders outside the card's scrolling area (not inside the table's container), so a narrow card does not clip it.
- [x] On the live stack (browser step of ticket 08): hovering a term on the Overview shows its tooltip.

## Comments

2026-11-16: Done in `a0284c50c`, with `d8769456d` (one tooltip, no native title) and the review's fix `0c5ccc24a` (Escape dismisses a definition opened by hover). Shown: `definitions.test.cjs` (no block at the end, terms placed, hover, focus, tap, Escape, the tooltip outside the cards, none in full views) passed in the page suite through the wrapper (fresh clone at `0bf2f41cd`). On the stack (`check-fixes page`, final run): 13 terms on the overview, each tooltip shown on hover and on focus, inside the window, with the glossary's text, hidden after; a full view showed none. Record: `docs/evidence/2026-11-16-open-lines-closed-and-admin-settings.md`.
