# 18: Final run, access review and fork documentation

**What to build:** The whole feature shown working against a real CVAT, its access rules reviewed by someone who did not write them, and the fork's own documents brought up to date so the next upgrade knows what to preserve. See the Testing Decisions of the spec (`../spec.md`).

**Blocked by:** 03 (Tracer runs on the stack), 04 (Access rules complete), 15 (History processing and late events), 16 (Details table), 17 (Full view for every chart).

**Status:** resolved

- [x] On the fresh test stack the real server accepted, and the events table holds, every record the real UI added in the run: shape fields on draw, drag, paste, propagate and delete, the group drag record, class change by hotkey, the detector record (model answer supplied in the browser) and the input summary. Class change by mouse and resize were not driven.
- [x] Event logging and working time behave as before with the new logging in place.
- [x] For the data loaded by the run, the service returns the expected figures for sessions, working time, operations, creation methods, Model, saved boxes, keyboard and mouse, projects and trends.
- [x] With real accounts: admin group with and without an organization, owner, maintainer, supervisor, worker, non-member, a member of another organization, and a maintainer with no organization selected each get exactly what the rules allow.
- [x] In a browser the page loads, the period and both filters work, a full view opens and returns, and trends compare two annotators.
- [x] With a hundred annotators, forty projects and long names loaded, the overview keeps its length and nothing overflows; on a narrow window cards stack and wide tables scroll sideways.
- [x] With the service stopped the page shows its error panel and annotation is unaffected.
- [x] The access rules are reviewed independently after this run, and every finding is resolved or recorded.
- [x] The fork specification gains a section for the feature with its integration map and acceptance scenarios; the upgrade procedure gains its checks; the README links to both.
- [x] A dated evidence file records what was run, the outcomes, and what remains unverified.

## Comments

2026-11-14: Resolved on `feat/team-analytics-page` by merge `e7da2e4`. Review fixes that followed are in merge `401576e`. Live results, review outcomes and what remains unverified: `docs/evidence/2026-11-14-team-analytics-final-run.md`. The independent access review ran after the final run; its findings and their resolution are in the evidence file's "Independent access review" section, fixed in merge `401576e`.

2026-11-15: Ticket 27 of the defect fixes restated this criterion, ticked on a reading when the detector record came from a script (decisions ledger, V11), as what the fresh stack showed. Original wording: "On the test stack, the real server accepts every record the UI logging adds (shape fields, class change, detector use, input summary), and each arrives in the events table." Evidence: `docs/evidence/2026-11-15-final-run-on-a-fresh-stack.md`.
