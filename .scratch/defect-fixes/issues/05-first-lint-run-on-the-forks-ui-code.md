# 05: First lint run on the fork's UI code

**What to build:** ESLint, stylelint and the type check run on the fork's UI code with upstream's own configuration for the first time, and the code passes. The findings are fixed without changing behaviour. The import cycles in the UI logging module go away by moving the function that writes a Team Analytics record into a module of its own. Every later ticket that edits UI files waits for this one, so that it is not rebased over a formatting sweep. See "Tooling" and "UI logging" in the spec (`../spec.md`).

**Blocked by:** 04 (Re-import the release with the widened filter).

**Status:** resolved

- [x] ESLint runs with upstream's configuration on every UI file the fork added or edited, and exits clean.
- [x] stylelint runs on the fork's style files and exits clean.
- [x] The type check passes, resolving the workspace packages from this checkout.
- [x] Automatic formatting fixes are committed separately from fixes made by hand.
- [x] A finding in an upstream line the fork did not write is left alone and listed in this ticket.
- [x] The UI logging module has no import cycle, and its callers import what they imported before.
- [x] The three fast frontend suites pass before and after with the same tests. Nothing an annotator or a maintainer sees changes.
- [x] The commands used are written where the fork's checks are described.

## Comments

2026-11-14: Done on branch `ticket/05-lint`; evidence in
`docs/evidence/2026-11-14-ui-lint-first-run.md`, commands in section 4 of
`docs/upstream-upgrade.md`.

- Commits: automatic fixes `0555aaf`, fixes by hand `43fd752`, the move `763ad43`.
- Findings in upstream lines the fork did not write: none. Every finding was in a file
  the fork added; none of the 17 upstream files the fork edited had one or changed.
- The move took more than `logRecord`: `class-change.ts` also imported
  `objectShapeFields` from `index.ts`, and all three builders imported the job and
  object types. These, with the 2D check and the shape fields they rest on, moved to
  `record.ts` too; `index.ts` re-exports the same names as before.
- The type check passed resolving the workspace packages from this checkout through a
  throwaway `paths` configuration; the plain command, through the linked
  `cvat/node_modules`, resolves them from the main checkout. The merger reruns the
  plain command in the main checkout.
- "Nothing an annotator sees changes" rests on the suites, the byte-for-byte comparison
  of the compiled styles and the string checks in the evidence; no UI image was built
  and the page was not opened in a browser.

2026-11-14: Merged into `feat/team-analytics-page` in merge `0b46153`; evidence `docs/evidence/2026-11-14-ui-lint-first-run.md`. On the merged tree, in the main checkout: ESLint (`--max-warnings 0 --no-warn-ignored`) on the 66 fork .ts/.tsx files and stylelint (`--max-warnings 0`) on the 9 fork .scss files exit 0; `tsc -p cvat/cvat-ui/tsconfig.json` exits 0 with the workspace packages resolved from this checkout; `verify/team_analytics_page.cjs` passes 207 of 207 and `verify/team_analytics_logging.cjs` 55 of 55, 0 skipped in each; `verify/task_progress.cjs` passes 20 with 1 skipped (the optional browser check).
