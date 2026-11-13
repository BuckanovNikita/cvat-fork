# 17: Full view for every chart

**What to build:** A team lead with a hundred annotators opens any chart alone on the page and sees all of it, while the overview stays short. See Overview and Full view in `GLOSSARY.md`, the spec (`../spec.md`) and the two full-view screens in the prototype.

**Blocked by:** 07 (Projects and filters), 12 (Model, technical accounts and saved boxes), 13 (Keyboard and mouse), 14 (Trends and comparison).

**Status:** ready-for-agent

- [ ] Every chart on the overview has a Full view button: working time over the period, where working time goes, operations, creation methods, working time by project, working time by annotator, hotkeys, and each trend chart.
- [ ] A full view replaces the overview, keeps the header and the filter row, and returns with "Back to overview" or the browser's back button.
- [ ] Which full view is open is part of the page address.
- [ ] The "show all" control of a chart opens its full view; a card on the overview never grows.
- [ ] By project, by annotator and hotkeys: every row with its rank, whole name, bar, value and share, with search and sorting by value or by name.
- [ ] Where working time goes: the same list with a switch between annotators and projects.
- [ ] Working time over the period: a large chart and every value listed.
- [ ] A trend: a large chart, a legend with whole names and latest values, and a table of all twelve points.
- [ ] Operations and creation methods: a table by annotator or by project with a switch between the two.
- [ ] The legend sits at the top of a full view, above the rows.
- [ ] Clicking a row in a list sets the page's filter, as on the overview.
- [ ] The period, shape switch and filters still work inside a full view.
