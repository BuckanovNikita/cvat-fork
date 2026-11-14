# 16: Details table

**What to build:** A team lead reads every figure for every annotator, or every project, in one table, and finds a row by typing. See the spec (`../spec.md`) and the details table in the prototype.

**Blocked by:** 07 (Projects and filters), 10 (Class change), 12 (Model, technical accounts and saved boxes), 13 (Keyboard and mouse).

**Status:** resolved

- [x] The table lists annotators or, by a switch, projects, sorted by working time.
- [x] Columns: name; projects worked in (or annotators, for projects); sessions; working time; drawn; pasted; propagated; Model; alignments; class changes; deletions; average time to create; hotkey share.
- [x] Ten rows a page with previous and next, and a count of which rows are shown.
- [x] A search field narrows the rows by name; an empty result says so.
- [x] Clicking a row sets it as the page's annotator or project filter.
- [x] The table respects the period, the shape switch and the filter on the other dimension.
- [x] For a legacy period the Model column gives way to saved boxes, and class changes and hotkey share are marked as not recorded.
- [x] On a narrow window the table scrolls sideways and the name column stays in place.
- [x] A long name is shortened with the full name on hover.

## Comments

2026-11-14: Resolved on `feat/team-analytics-page` by merge `3384992`. Review fixes that followed are in merge `401576e`. Live results, review outcomes and what remains unverified: `docs/evidence/2026-11-14-team-analytics-final-run.md`.
