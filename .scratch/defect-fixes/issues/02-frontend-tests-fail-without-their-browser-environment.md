# 02: Frontend tests fail without their browser environment

**What to build:** When the browser environment the frontend tests need cannot be loaded, the suites fail and say why. Today about sixty page tests and the whole keyboard-and-mouse logging file skip themselves and the run still passes. The library is declared by the fork, where today it is present only as another package's optional dependency. See "Tooling" in the spec (`../spec.md`).

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] With the library unavailable, the page suite and the UI logging suite exit non-zero and name what is missing. This is shown once and noted in this ticket.
- [x] With it available, every test that was gated on it runs; none is skipped for that reason.
- [x] The library is declared in a manifest the fork owns, with a lock, and the harness resolves it from there. No file of the import is edited for it.
- [x] The optional browser check of the task-progress suite stays optional; it needs a browser binary, which is a different thing.
- [x] How to install the harness's dependencies is written where the suites are described.

## Comments

2026-11-14: Done on branch `ticket/02-jsdom-fail` (`75048a1`, `3a306e6`). Everything observed, and what was not verified, is in `docs/evidence/2026-11-14-frontend-harness-browser-environment.md`.

The failure, shown at `3a306e6` with `verify/node_modules` moved away and the import's own copy of jsdom still in `cvat/node_modules`:

- `node --test verify/team_analytics_page.cjs`: exit code 1.
- `node --test verify/team_analytics_logging.cjs`: exit code 1.
- Both print: `Error: jsdom, the browser environment of the frontend suites, did not load from verify/node_modules: Cannot find module 'verify/node_modules/jsdom'. Install the harness's dependencies: npm ci --prefix verify`
- `node --test verify/task_progress.cjs` in the same state: exit code 0, its browser check skipped for want of `BROWSER_BIN` as before.

After `npm ci --prefix verify` the two suites pass with nothing skipped.

Three things differ from what this ticket assumed:

- Before the fix, without jsdom, only the page run passed (62 tests skipped). The logging run already exited 1, because two closing-summary tests used the DOM helper without a gate; their error did not name jsdom, and the twelve keyboard-and-mouse tests were skipped.
- The gate was in twelve page test files and one logging test file, thirteen in all.
- The loader requires jsdom by its installed path, not by name. By name Node also searches parent directories and system-wide folders, so a copy found there would have been used silently.

Criterion 4 was shown without a browser: the check is skipped and the suite passes, whether or not the harness's dependencies are installed, and `verify/task_progress.cjs` is unchanged. The check was not run with a browser.

For the merge: a branch cut before this one may still add a `domTest(` call, which now fails loudly, or copy the old gate `skip: !domAvailable && ...`, which skips silently because the helper no longer exports `domAvailable`. After merging such a branch, `grep -rn "domAvailable\|domTest\|{ skip }" verify/team-analytics-page verify/team-analytics-logging` must find nothing and both suites must report 0 skipped.

2026-11-14: Resolved on `feat/team-analytics-page` by merge `12b7718`. Evidence: `docs/evidence/2026-11-14-frontend-harness-browser-environment.md`.
