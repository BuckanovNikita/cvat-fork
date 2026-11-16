# 03: Operations card without scroll

**What to build:** The "Bounding box operations" card never scrolls sideways at any window width of 1024px and up (item 3 of the spec). The table in `cards/operations-table-card.tsx` keeps five columns (Operation, Boxes or Objects, Avg time, Total time, Share) and moves the hotkey and mouse split to a second row under each operation, spanning all five columns, reusing `InputSplitCell` and `operations.ts`.

The table gets a class of its own: no minimum width, headers that wrap, 8px horizontal padding. The shared `.cvat-team-analytics-table` class, with its `min-width: 440px`, stays as it is, because the creation-methods card uses it too. The tightest width the card gets is about 388px, just after the page grid adds a column (near a 1356px window), not at 1024px. The creation-methods card also scrolls sideways today; it is reported in the final run, not changed.

**Blocked by:** none.

**Status:** resolved

- [x] The operations table has exactly five header cells in that order, and each operation is followed by a row holding its hotkey and mouse split across all five columns.
- [x] The figures shown (counts, average and total time, share, hotkey and mouse split) are the same as before for the same answer: `verify/team-analytics-page/operations.test.cjs`, `class-change.test.cjs` and `keyboard-mouse.test.cjs` pass, updated only for the new layout.
- [x] The operations table uses its own scoped class with no minimum width; `.cvat-team-analytics-table` and the creation-methods card are unchanged.
- [x] On the live stack (browser width sweep of ticket 08, 1024px to 1920px, including the width that gives a card of about 420px and the tightest point near 1356px): the operations card has no sideways scroll at any step.
- [x] The same sweep prints the other cards that still scroll sideways, and the final report names them.

## Comments

2026-11-16: Done in `8149b8e5f`: the table has its own class `cvat-team-analytics-operations-table` with no minimum width; the shared `.cvat-team-analytics-table` keeps its `min-width: 440px`. Shown: the page suite, the operations, class-change and keyboard-mouse tests among it, passed through the wrapper (fresh clone at `0bf2f41cd`). On the stack (`check-fixes page`, final run): columns Operation, Boxes, Avg time, Total time, Share with a "started by" line under each operation; a sweep of 127 widths from 1024 to 1920 px found no sideways scroll in the operations card. The tightest point measured is a 420 px card at 1371 px (columns change at 1371 and 1807 px), not near 1356 px as estimated here; 388 px is the table's width inside that card's padding. Other cards whose table scrolls: creation methods at 42 widths (1024-1920 px) and details at 34 (1024-1288 px), named in the record (`docs/evidence/2026-11-16-open-lines-closed-and-admin-settings.md`).
