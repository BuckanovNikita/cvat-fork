# 14: Trends and comparison

**What to build:** A team lead sees how the team's figures changed over the last twelve weeks or months and can put up to five annotators, or five projects, side by side. See Trend and Comparison in `GLOSSARY.md`, the spec (`../spec.md`) and the trends section of the prototype.

**Blocked by:** 05 (Periods, time zone and freshness), 07 (Projects and filters), 08 (Operations and time per operation, all shapes), 13 (Keyboard and mouse).

**Status:** ready-for-agent

- [ ] Four charts show working time, boxes created, average time per box and hotkey share over the last twelve weeks, or the last twelve months.
- [ ] Weeks start on Monday and follow the viewer's time zone.
- [ ] Trends do not change with the selected period; they follow the project and annotator filters and the shape switch.
- [ ] With nothing compared, each chart shows one line for the current scope.
- [ ] The team lead can compare up to five annotators, or switch to comparing up to five projects; each is one line in every chart.
- [ ] A compared line keeps its colour while others are added and removed.
- [ ] People and projects to compare are found by typing; at five, further choices are disabled with a hint.
- [ ] Every chart has a legend that names its lines, and each value can be read without relying on colour alone.
- [ ] Weeks or months from before the new logging show hotkey share as not recorded.
- [ ] Each chart has one vertical scale; two measures never share a chart.
