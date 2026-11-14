# 14: Trends and comparison

**What to build:** A team lead sees how the team's figures changed over the last twelve weeks or months and can put up to five annotators, or five projects, side by side. See Trend and Comparison in `GLOSSARY.md`, the spec (`../spec.md`) and the trends section of the prototype.

**Blocked by:** 05 (Periods, time zone and freshness), 07 (Projects and filters), 08 (Operations and time per operation, all shapes), 13 (Keyboard and mouse).

**Status:** resolved

- [x] Four charts show working time, boxes created, average time per box and hotkey share over the last twelve weeks, or the last twelve months.
- [x] Weeks start on Monday and follow the viewer's time zone.
- [x] Trends do not change with the selected period; they follow the project and annotator filters and the shape switch.
- [x] With nothing compared, each chart shows one line for the current scope.
- [x] The team lead can compare up to five annotators, or switch to comparing up to five projects; each is one line in every chart.
- [x] A compared line keeps its colour while others are added and removed.
- [x] People and projects to compare are found by typing; at five, further choices are disabled with a hint.
- [x] Every chart has a legend that names its lines, and each value can be read without relying on colour alone.
- [x] Weeks or months from before the new logging show hotkey share as not recorded.
- [x] Each chart has one vertical scale; two measures never share a chart.

## Comments

2026-11-14: Resolved on `feat/team-analytics-page` by merge `dd9e5f1`. Review fixes that followed are in merge `401576e`. Live results, review outcomes and what remains unverified: `docs/evidence/2026-11-14-team-analytics-final-run.md`.
