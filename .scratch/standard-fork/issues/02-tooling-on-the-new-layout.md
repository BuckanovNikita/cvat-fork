# 02: The fork's tooling on the new layout

**What to build:** The build scripts, the check pipeline and the verify harness name files at the repository root and the upstream release tag, where they named the old `cvat/` import and its filtered tag. Upstream's `.github/` is removed and the fork's ignore entries are appended to upstream's.

**Blocked by:** 01.

**Status:** resolved

- [x] The check pipeline passes with nine hooks, none skipped, and the three frontend suites run as many tests as before.
- [x] ruff selects exactly the fork's own Python and none of upstream's.
- [x] The stack launcher's preflight passes with the chart of the tree.
- [x] The service suite passes.
- [x] `build-ui.sh` builds from the repository root with a context cut down to the frontend packages.

## Comments

2026-11-15: Commits `6cc31091` (`.github/` removed), `3de05f86` (jsdom and upstream's unbuilt `canvas`), `3ae9ab7d` (tooling). `prek run --all-files`: nine hooks passed. Suites: page 223, logging 77, task progress 20 and 1 skipped, as before the conversion. ruff selects 74 files: 63 under `team-analytics/`, 9 under `verify/`, 2 under `docs/`. `verify/team-analytics-stack/run.sh preflight` passed (server image, both policy matrices, chart build and render, render guard); nothing was created or pulled.

Found on the way: with the dependencies at the repository root, the harness's jsdom resolved upstream's `canvas` package, whose native part is not built, and both jsdom suites failed to load. `verify/browser-environment.cjs` now reports `canvas` to jsdom as not installed while jsdom loads.

Open: the service suite was started and had not finished when this was written; the UI image build from the root has not run (network and CPU; it is rebuilt for the acceptance run, since the page changes before then). Both criteria stay unticked until shown.

2026-11-15: Both open criteria are now shown. The service suite ran whole at `5cdd1237`, the commit after the tooling one that also moves the calculation code: 321 tests, none failed (2,715 s, default ClickHouse image), read from a snapshot of that commit. `IMAGE=cvat/ui:v2.82.0-fork ./build-ui.sh` built at `9c0d8248`; the context sent was 27 MB. Record: `docs/evidence/2026-11-15-full-fork-conversion.md`.
