# 15: History processing and late events

**What to build:** Right after deployment a team lead gets recent figures quickly, sees how far back history has been processed, and is never shown a partial figure as a total. Work whose events arrive late is still counted. See Processed history in `GLOSSARY.md`, the Refresh and history section of the spec (`../spec.md`) and ADR 0001.

**Blocked by:** 05 (Periods, time zone and freshness).

**Status:** ready-for-agent

- [ ] All existing history is processed, one day at a time, most recent first; no single computation covers a long range.
- [ ] The service reports how far history is processed and which periods are fully available.
- [ ] While history is being processed the page shows one progress bar with the earliest ready date.
- [ ] A period is offered only when all of it is processed; others are disabled with an explanation. No partial figure is shown anywhere.
- [ ] Trends are replaced by a short notice until at least three complete weeks are ready.
- [ ] An event that arrives two days after it happened is counted once the next check runs.
- [ ] Once a day each older day's raw event count is compared with the count stored when it was computed, and days that differ are recomputed.
- [ ] Recomputing a day replaces its totals; nothing is counted twice.
- [ ] Processing history does not delay the ten-minute refresh of recent hours.
