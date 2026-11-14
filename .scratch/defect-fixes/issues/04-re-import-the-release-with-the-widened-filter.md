# 04: Re-import the release with the widened filter

**What to build:** The import gains upstream's lint configuration, the Helm chart and the four stock policy files, and loses the Compose file, in one re-import of the current release. From this ticket on the two Compose launchers cannot run: Compose is no longer used, their files are removed in ticket 12, and their checks return on the Kubernetes stack in tickets 09 and 10. See "Import" in the spec (`../spec.md`) and the amendments of ADR 0003.

**Blocked by:** 03 (Prove the widened import's path list).

**Status:** resolved

- [x] The mirror is rebuilt with the path list proven in ticket 03, unchanged, and the current release is pulled into the import from it.
- [x] Every path the import held before, except the Compose file, is unchanged by the pull, the fork's own edits included.
- [x] Every new path equals the recorded upstream commit byte for byte.
- [x] The existing release tags still point at the earlier filtered commit. The new filtered commit has its own tag, and the documented way to list the fork's changes inside the import compares against that tag.
- [x] The old and new identifiers of the import are recorded in a dated baseline evidence file.
- [x] The UI image builds from the import as before.
- [x] The three fast frontend suites and the type check pass.

## Comments

2026-11-14: Re-imported in merge `a135a65` (snapshot `2137ba8`); new filtered commit `361a0e6`, local tag `cvat-v2.82.0-widened`, root tree `f09b92a` as computed in ticket 03. Checks and identifiers: `docs/evidence/2026-11-14-widened-import-baseline.md`. The documented squashed pull accepted the re-filtered mirror in a trial, but its snapshot message lists every commit of the re-filtered history and cannot carry the commit trailers, so the snapshot was written by hand the way `git subtree` writes it; a second documented pull afterwards reports that the subtree is already at the new commit. The method is in `docs/upstream-upgrade.md`, section 2.

2026-11-14: The UI image build is outstanding. It was not allowed while the machine's user was busy; the orchestrator runs it when the machine is free. The merge changed none of the build's inputs.

2026-11-14: Merged into `feat/team-analytics-page` in merge `8860b71`; evidence `docs/evidence/2026-11-14-widened-import-baseline.md`. On the merged tree the import holds 50 added paths and the deleted Compose file, the import tree equals `cvat-v2.82.0-widened` outside `cvat-ui/`, and the three fast frontend suites pass. The ticket stays open: the UI image build is still outstanding and runs when the machine is free.

2026-11-15: The UI image build ran once the machine was free: `IMAGE=cvat/ui:v2.82.0-team-analytics ./build-ui.sh` at `3dc1a7bc` exited 0 (image `sha256:310e9bbc6a47`), recorded in `docs/evidence/2026-11-14-widened-import-baseline.md`. With that the last criterion is shown. Resolved on `feat/team-analytics-page` by merge `8860b71`.
