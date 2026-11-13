# 07: Projects and filters

**What to build:** A team lead sees every figure per project as well as per annotator, and narrows the whole page to one project, one annotator or both by clicking a row. See the spec (`../spec.md`) and the two bar charts and the filter row in the prototype.

**Blocked by:** 06 (Sessions).

**Status:** ready-for-agent

- [ ] Working time is available per project and per annotator for the selected period.
- [ ] Two charts, working time by project and working time by annotator, each show the eight largest rows and one line with the count and total of the rest.
- [ ] Clicking a row sets that project or annotator as a filter for the whole page; clicking it again, or the clear control in the filter row, removes it.
- [ ] The project filter and the annotator filter combine, and each chart keeps listing the other dimension within the current filter.
- [ ] The filters are part of the page address.
- [ ] Job work in a task that belongs to no project appears under No project.
- [ ] A project that CVAT no longer returns stays in the figures, shown by its identifier.
- [ ] Project names come from the existing CVAT API with the viewer's own rights.
- [ ] With a project selected, a session counts if it touched that project, and its length is only the time spent inside it.
- [ ] Headline figures show how many annotators were active in the scope and across how many projects.
- [ ] Each chart carries its legend inside the card.
- [ ] A long name is shortened with the full name on hover and never breaks the layout.
