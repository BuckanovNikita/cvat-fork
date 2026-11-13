# 05: Periods, time zone and freshness

**What to build:** A team lead chooses the period the figures cover, sees working time laid out over that period in their own time zone, and can tell how fresh the figures are. See the spec (`../spec.md`) and the filter row and time chart in the prototype.

**Blocked by:** 02 (Tracer: working time per annotator for the last week).

**Status:** ready-for-agent

- [ ] The period control offers Week, Two weeks, Month and Year. There is no custom range.
- [ ] Week and Two weeks are the last 7 and 14 days ending today; Month is one calendar month; Year is the last twelve months ending today.
- [ ] With Month selected, the team lead can step to earlier months and back; the current month is marked "to date" and no later month can be chosen.
- [ ] Days follow the viewer's time zone.
- [ ] A chart shows working time per day for the period, with values readable without hovering when there are few bars and axis labels thinned when there are many.
- [ ] For Year the chart shows weeks instead of days.
- [ ] The page shows the time of the last successful refresh and a warning once that is more than thirty minutes ago.
- [ ] The selected period, and the month when Month is selected, are part of the page address; the browser's back button returns to the previous selection.
- [ ] While figures for a new period load, the previous figures stay on screen dimmed.
- [ ] The service exposes when the last refresh succeeded.
