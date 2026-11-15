# 02: Filter bar: one height and working selectors

**What to build:** Every control of the filter bar is 36px tall, border-box, on one centre line (items 1 and 2 of the spec). The step arrows grow to 36px and the leftover bottom margin of the project filters goes (`styles.scss`, `shapes.scss`, `projects-filters.scss` in `cvat-ui/src/components/team-analytics-page/`).

The Project and Annotator chips become working selectors: a new `filter-select.tsx`, a hand-written combobox in the bar's own style (a button, a search input and a listbox), one value each, "All" first and the "No project" bucket included. `filter-chips.tsx` uses it and keeps its clear button. Options load when the dropdown opens, through the existing list request (`by=annotators` or `by=projects`, with no project, annotator or shapes parameter), and are kept per organization and period. The search reuses the list's existing `arrange()`. A period that is not processed yet gives no options: the dropdown shows "All", the current value and a "not processed yet" line. Clicking a row of a card still sets the filter.

Project names: at Instance scope CVAT's own projects API returns only personal-workspace projects (confirmed on a stack on 2026-11-15: 1 project of 45), so `project-names.ts` switches to the administrators-only `project-names` action that ticket 05 adds.

**Blocked by:** 01. The switch of `project-names.ts` uses the `project-names` action of ticket 05; that part lands once 05's action exists.

**Status:** ready-for-agent

- [ ] New page test `verify/team-analytics-page/filter-select.test.cjs`: the selector opens, filters its options by the typed text, lists "All" first and the "No project" bucket, and choosing a value sets the filter while the clear button resets it.
- [ ] Options are requested only when the dropdown opens, with `by=annotators` or `by=projects` and no project, annotator or shapes parameter, and are not requested again for the same organization and period.
- [ ] For a period that is not processed, the dropdown shows "All", the current value and a "not processed yet" line, and no options.
- [ ] Clicking a card row still sets the project or annotator filter (existing tests pass, `projects-filters.test.cjs` updated).
- [ ] Project names come from the `project-names` action, and an id that is not returned still reads "Project #N".
- [ ] Keyboard use works: the selector opens, moves through options and closes with the keyboard, and has combobox and listbox roles.
- [ ] On the live stack (browser step of ticket 08): every filter-bar control and the Settings button measure 36px with one shared centre line, and a project and an annotator can be picked through the selectors.

## Comments
