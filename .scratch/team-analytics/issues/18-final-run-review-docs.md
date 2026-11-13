# 18: Final run, access review and fork documentation

**What to build:** The whole feature shown working against a real CVAT, its access rules reviewed by someone who did not write them, and the fork's own documents brought up to date so the next upgrade knows what to preserve. See the Testing Decisions of the spec (`../spec.md`).

**Blocked by:** 03 (Tracer runs on the stack), 04 (Access rules complete), 15 (History processing and late events), 16 (Details table), 17 (Full view for every chart).

**Status:** ready-for-agent

- [ ] On the test stack, the real server accepts every record the UI logging adds (shape fields, class change, detector use, input summary), and each arrives in the events table.
- [ ] Event logging and working time behave as before with the new logging in place.
- [ ] For the data loaded by the run, the service returns the expected figures for sessions, working time, operations, creation methods, Model, saved boxes, keyboard and mouse, projects and trends.
- [ ] With real accounts: admin group with and without an organization, owner, maintainer, supervisor, worker, non-member, a member of another organization, and a maintainer with no organization selected each get exactly what the rules allow.
- [ ] In a browser the page loads, the period and both filters work, a full view opens and returns, and trends compare two annotators.
- [ ] With a hundred annotators, forty projects and long names loaded, the overview keeps its length and nothing overflows; on a narrow window cards stack and wide tables scroll sideways.
- [ ] With the service stopped the page shows its error panel and annotation is unaffected.
- [ ] The access rules are reviewed independently after this run, and every finding is resolved or recorded.
- [ ] The fork specification gains a section for the feature with its integration map and acceptance scenarios; the upgrade procedure gains its checks; the README links to both.
- [ ] A dated evidence file records what was run, the outcomes, and what remains unverified.
