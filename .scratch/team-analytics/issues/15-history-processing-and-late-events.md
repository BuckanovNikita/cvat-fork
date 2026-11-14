# 15: History processing and late events

**What to build:** Right after deployment a team lead gets recent figures quickly, sees how far back history has been processed, and is never shown a partial figure as a total. Work whose events arrive late is still counted. See Processed history in `GLOSSARY.md`, the Refresh and history section of the spec (`../spec.md`) and ADR 0001.

**Blocked by:** 05 (Periods, time zone and freshness).

**Status:** resolved

- [x] All existing history is processed, one day at a time, most recent first; no single computation covers a long range.
- [x] The service reports how far history is processed and which periods are fully available.
- [x] While history is being processed the page shows one progress bar with the earliest ready date.
- [x] A period is offered only when all of it is processed; others are disabled with an explanation. No partial figure is shown anywhere.
- [x] Trends are replaced by a short notice until at least three complete weeks are ready.
- [x] An event that arrives two days after it happened is counted once the next check runs.
- [x] Once a day each older day's raw event count is compared with the count stored when it was computed, and days that differ are recomputed.
- [x] Recomputing a day replaces its totals; nothing is counted twice.
- [x] Processing history does not delay the ten-minute refresh of recent hours.

## Comments

2026-11-14: Resolved on `feat/team-analytics-page` by merge `1a71c44`. Review fixes that followed are in merge `401576e`. Live results, review outcomes and what remains unverified: `docs/evidence/2026-11-14-team-analytics-final-run.md`.
