# 03: Prove the widened import's path list

**What to build:** The import filter can be widened only once without changing the import's identifiers again. Before that happens, the candidate files are shown to be sufficient in a scratch copy taken at the recorded upstream commit, and the mirror script is made safe to rerun. See "Import" in the spec (`../spec.md`); the candidate path list is in `../plan.md`.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] The candidate paths are fetched at the recorded upstream commit of the current release into a scratch directory outside the repository. The import is not touched.
- [x] ESLint and stylelint load upstream's configuration on the fork's UI paths using only files the widened import will hold. Any further file they turn out to need is added to the path list.
- [x] The formatting-only change in the imported ClickHouse setup file is reverted, so that file equals upstream's.
- [x] The chart from the candidate tree, rendered with the stack's values, equals the render of the cached chart the stack uses today. Any difference is explained.
- [x] The existing policy test passes against the four stock policy files of the candidate tree, with the stock expectations.
- [x] The mirror script builds the new mirror beside the existing one and replaces it only on success.
- [x] The final path list and the three results are recorded in a dated evidence file.
- [x] Nothing else in the import changes in this ticket.

## Comments

**2026-11-14.** All eight criteria were run and seen; the record is
`docs/evidence/2026-11-14-widened-import-proof.md`.

- The path list gained one file the plan did not name: `tests/.eslintrc.js`.
  Upstream's `eslint.config.mjs` loads it when the configuration is evaluated;
  without it ESLint exits before linting any file. The final list has
  twenty-four paths and is in the evidence file.
- `PATHS` in `mirror-cvat.sh` was left as it is. This ticket changed only how
  the script replaces the mirror; ticket 04 puts the proven list in.
- The chart render does not depend on the ClickHouse setup file: the chart
  reads only Vector's configuration and Grafana's dashboards through its link.
  The file was reverted as the criterion says, and now equals upstream's.
- The chart render equals the cached one except for two lines that change on
  every render of the same chart (the Grafana subchart's generated password
  and the checksum of its Secret).
- The old mirror script had a second fault, found with the local test
  repositories and fixed in the same commit: a source with only branches and
  tags ended the run before the filter.
- ESLint and stylelint report findings on the fork's UI files (25 errors and
  7 warnings; 7 style findings). They are ticket 05's and were not touched.

2026-11-14: Resolved on `feat/team-analytics-page` by merge `ccd4f59`. Evidence: `docs/evidence/2026-11-14-widened-import-proof.md`.
