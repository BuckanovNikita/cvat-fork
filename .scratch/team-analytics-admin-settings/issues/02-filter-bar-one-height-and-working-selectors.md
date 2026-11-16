# 02: Filter bar: one height and working selectors

**What to build:** Every control of the filter bar is 36px tall, border-box, on one centre line (items 1 and 2 of the spec). The step arrows grow to 36px and the leftover bottom margin of the project filters goes (`styles.scss`, `shapes.scss`, `projects-filters.scss` in `cvat-ui/src/components/team-analytics-page/`).

The Project and Annotator chips become working selectors: a new `filter-select.tsx`, a hand-written combobox in the bar's own style (a button, a search input and a listbox), one value each, "All" first and the "No project" bucket included. `filter-chips.tsx` uses it and keeps its clear button. Options load when the dropdown opens, through the existing list request (`by=annotators` or `by=projects`, with no project, annotator or shapes parameter), and are kept per organization and period. The search reuses the list's existing `arrange()`. A period that is not processed yet gives no options: the dropdown shows "All", the current value and a "not processed yet" line. Clicking a row of a card still sets the filter.

Project names: at Instance scope CVAT's own projects API returns only personal-workspace projects (confirmed on a stack on 2026-11-15: 1 project of 45), so `project-names.ts` switches to the administrators-only `project-names` action that ticket 05 adds.

**Blocked by:** 01. The switch of `project-names.ts` uses the `project-names` action of ticket 05; that part lands once 05's action exists.

**Status:** resolved

- [x] New page test `verify/team-analytics-page/filter-select.test.cjs`: the selector opens, filters its options by the typed text, lists "All" first and the "No project" bucket, and choosing a value sets the filter while the clear button resets it.
- [x] Options are requested only when the dropdown opens, with `by=annotators` or `by=projects` and no project, annotator or shapes parameter, and are not requested again for the same organization and period.
- [x] For a period that is not processed, the dropdown shows "All", the current value and a "not processed yet" line, and no options.
- [x] Clicking a card row still sets the project or annotator filter (existing tests pass, `projects-filters.test.cjs` updated).
- [x] Project names come from the `project-names` action, and an id that is not returned still reads "Project #N".
- [x] Keyboard use works: the selector opens, moves through options and closes with the keyboard, and has combobox and listbox roles.
- [ ] On the live stack (browser step of ticket 08): every filter-bar control measures 36px on one shared centre line, the Settings button (in the header row at the right, not on the filter row) measures 36px, and a project and an annotator can be picked through the selectors.

## Comments

2026-11-16: Done in `bc1dc086c`, with the review's fixes in `947be8a66` (typing then Enter, focus after clearing, stale options, popup edge), `e27dc28d8`, `ebf221ef7` (names requests asked again after a failure), `98bedfebd` and `6da9f526f` (popup placement and width). Shown: the page suite with `filter-select.test.cjs` passed through `tools/gate/node-suite.sh` (fresh clone at `0bf2f41cd`). On the stack (`check-fixes page`, final run): all 5 controls 36 px at 1024, 1400 and 1920 px, Settings 36 px at the header's right end; each selector one list request and none on reopening; a project and an annotator picked through the selectors with the figures changing; an open popup inside the page at 1024, 1192 and 1400 px; at instance scope 51 project options, none named "Project #N". Record: `docs/evidence/2026-11-16-open-lines-closed-and-admin-settings.md`.

Left unticked, the live criterion, only partly met: the controls share one centre line at 1400 and 1920 px, but at 1024 px the bar wraps onto two lines (centres 148 and 192 px), each line on its own centre; heights, the Settings button and both selectors were shown.
