# 07: Projects and filters

**What to build:** A team lead sees every figure per project as well as per annotator, and narrows the whole page to one project, one annotator or both by clicking a row. See the spec (`../spec.md`) and the two bar charts and the filter row in the prototype.

**Blocked by:** 06 (Sessions).

**Status:** resolved

- [x] Working time is available per project and per annotator for the selected period.
- [x] Two charts, working time by project and working time by annotator, each show the eight largest rows and one line with the count and total of the rest.
- [x] Clicking a row sets that project or annotator as a filter for the whole page; clicking it again, or the clear control in the filter row, removes it.
- [x] The project filter and the annotator filter combine, and each chart keeps listing the other dimension within the current filter.
- [x] The filters are part of the page address.
- [x] Job work in a task that belongs to no project appears under No project.
- [x] A project that CVAT no longer returns stays in the figures, shown by its identifier.
- [x] Project names come from the existing CVAT API with the viewer's own rights.
- [x] With a project selected, a session counts if it touched that project, and its length is only the time spent inside it.
- [x] Headline figures show how many annotators were active in the scope and across how many projects.
- [x] Each chart carries its legend inside the card.
- [x] A long name is shortened with the full name on hover and never breaks the layout.

## Comments

2026-11-14: Resolved on `feat/team-analytics-page` by merge `192a705`. Review fixes that followed are in merge `401576e`. Live results, review outcomes and what remains unverified: `docs/evidence/2026-11-14-team-analytics-final-run.md`.
