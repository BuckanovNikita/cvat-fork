# 02: Frontend tests fail without their browser environment

**What to build:** When the browser environment the frontend tests need cannot be loaded, the suites fail and say why. Today about sixty page tests and the whole keyboard-and-mouse logging file skip themselves and the run still passes. The library is declared by the fork, where today it is present only as another package's optional dependency. See "Tooling" in the spec (`../spec.md`).

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] With the library unavailable, the page suite and the UI logging suite exit non-zero and name what is missing. This is shown once and noted in this ticket.
- [ ] With it available, every test that was gated on it runs; none is skipped for that reason.
- [ ] The library is declared in a manifest the fork owns, with a lock, and the harness resolves it from there. No file of the import is edited for it.
- [ ] The optional browser check of the task-progress suite stays optional; it needs a browser binary, which is a different thing.
- [ ] How to install the harness's dependencies is written where the suites are described.
