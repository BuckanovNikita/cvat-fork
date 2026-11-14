# 06: Sessions

**What to build:** A team lead sees how each annotator's work is split into sessions: how many, how long on average and in total, per annotator and for the whole team. See Session and Session gap in `GLOSSARY.md` and the spec (`../spec.md`).

**Blocked by:** 02 (Tracer: working time per annotator for the last week).

**Status:** resolved

- [x] A session is an uninterrupted interval of one person's job work; a pause longer than five minutes starts a new one.
- [x] Sessions are formed from the person's job-bound client events and job-bound working-time records.
- [x] Everyone who does job work has sessions, whatever the stage of the job.
- [x] Work that continues across midnight is one session.
- [x] A session that crosses the edge of a refresh window is counted once, with its full length.
- [x] The page shows the number of sessions and their average length as a headline figure for the scope.
- [x] Per annotator, the number of sessions and the average session length are available to the page.
- [x] Sessions are stored as intervals per annotator together with the time each spent in each project, ready for the project filter in ticket 07.

## Comments

2026-11-14: Resolved on `feat/team-analytics-page` by merge `b6375a4`. Review fixes that followed are in merge `401576e`. Live results, review outcomes and what remains unverified: `docs/evidence/2026-11-14-team-analytics-final-run.md`.
