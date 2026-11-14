# 17: Full view for every chart

**What to build:** A team lead with a hundred annotators opens any chart alone on the page and sees all of it, while the overview stays short. See Overview and Full view in `GLOSSARY.md`, the spec (`../spec.md`) and the two full-view screens in the prototype.

**Blocked by:** 07 (Projects and filters), 12 (Model, technical accounts and saved boxes), 13 (Keyboard and mouse), 14 (Trends and comparison).

**Status:** resolved

- [x] Every chart on the overview has a Full view button: working time over the period, where working time goes, operations, creation methods, working time by project, working time by annotator, hotkeys, and each trend chart.
- [x] A full view replaces the overview, keeps the header and the filter row, and returns with "Back to overview" or the browser's back button.
- [x] Which full view is open is part of the page address.
- [x] The "show all" control of a chart opens its full view; a card on the overview never grows.
- [x] By project, by annotator and hotkeys: every row with its rank, whole name, bar, value and share, with search and sorting by value or by name.
- [x] Where working time goes: the same list with a switch between annotators and projects.
- [x] Working time over the period: a large chart and every value listed.
- [x] A trend: a large chart, a legend with whole names and latest values, and a table of all twelve points.
- [x] Operations and creation methods: a table by annotator or by project with a switch between the two.
- [x] The legend sits at the top of a full view, above the rows.
- [x] Clicking a row in a list sets the page's filter, as on the overview.
- [x] The period, shape switch and filters still work inside a full view.

## Comments

2026-11-14: Resolved on `feat/team-analytics-page` by merge `c3ee2e3`. Review fixes that followed are in merge `401576e`. Live results, review outcomes and what remains unverified: `docs/evidence/2026-11-14-team-analytics-final-run.md`.
