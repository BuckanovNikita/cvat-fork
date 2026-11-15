# First lint run on the fork's UI code, 2026-11-14

Ticket 05 of the defect fixes. ESLint, stylelint and the type check ran on the
fork's UI code with upstream's own configuration, which the import carries since
the re-import (merge `8860b71`). The findings were fixed in three commits, and the
import cycles of the UI logging module were removed by moving the record writer
into a module of its own.

Run on one host with Node 22.22.1, from the repository root, on the installed
`cvat/node_modules` (a link to the main checkout's): ESLint 10.3.0, stylelint
15.11.0, TypeScript 5.9.3, Sass 1.77.0. The commands are the ones now written in the
"Frontend" part of section 4 of `docs/upstream-upgrade.md`.

## Files

The fork's UI files are those `git diff --name-only cvat-v2.82.0-widened HEAD:cvat`
lists: 74 at the start (`ad7cf9e`), all under `cvat-ui/`, 57 added and 17 edited
upstream files; 65 `.ts`/`.tsx` and 9 `.scss`. The move adds `record.ts`, so 66
script files at the end. Nothing else of the import was linted.

## Live outcomes

| Step | ESLint | stylelint | Type check |
| --- | --- | --- | --- |
| Start (`ad7cf9e`) | exit 1: 30 errors, 2 warnings in 15 files (12 `object-curly-newline`, 9 `max-len`, 5 unused disable directives, 2 `@stylistic/indent`, 2 `@typescript-eslint/explicit-function-return-type`, 1 `no-use-before-define`, 1 `no-param-reassign`) | exit 2: 7 errors in 5 files (4 `alpha-value-notation`, 3 `scss/double-slash-comment-empty-line-before`) | exit 0 |
| After `--fix` of both tools (`0555aaf`) | exit 1: 11 errors, 2 warnings | exit 0 | not run |
| After the fixes by hand (`43fd752`) | exit 0 | exit 0 | exit 0 |
| After the move (`763ad43`) and after the merge of the integration branch | exit 0 | exit 0 | exit 0 |

Flags: at the start ESLint ran with `--exit-on-fatal-error
--report-unused-disable-directives` (the five unused directives as errors) and
stylelint with none. The `--fix` runs took no other flag. After the fixes by
hand and after the move ESLint ran with `--max-warnings 0
--report-unused-disable-directives`. The last runs, on the tree of the move and
again after the merge of the integration branch, used the three commands exactly
as section 4 of the upgrade procedure writes them (`--max-warnings 0
--no-warn-ignored` for ESLint, `--max-warnings 0` for stylelint), on the lists
made as written there.

The ESLint findings at the start are the 32 of ticket 03's run on its scratch
copy, where they read 25 errors and 7 warnings: without
`--report-unused-disable-directives` the configuration reports the five unused
directives as warnings.

Every finding was in a file the fork added. None of the 17 upstream files the
fork edited had a finding, and none of them changed in the three commits
(`git diff --name-only ad7cf9e HEAD` against the `M` entries of the list).
So no finding in an upstream line was left in place.

The three fast frontend suites, before the first change and after the last:

| Suite | Before | After | Test names |
| --- | --- | --- | --- |
| `node --test verify/team_analytics_page.cjs` | 206 pass | 206 pass | the same 206 |
| `node --test verify/team_analytics_logging.cjs` | 55 pass | 55 pass | the same 55 |
| `node --test verify/task_progress.cjs` | 20 pass, 1 skipped | 20 pass, 1 skipped | the same 21 |

Names were compared as the sorted `ok` lines of the TAP reporter's output. The
skipped test is the optional browser check (no `BROWSER_BIN`).

## Stated checks

- **Import cycles.** A script listed the relative imports and re-exports of each
  file in `cvat-ui/src/utils/team-analytics-logging/` (TypeScript's parser,
  type-only imports included) and searched the graph for cycles. Before the move:
  three, `index.ts` with each of `class-change.ts`, `input-summary.ts` and
  `model-creation.ts`. After: none. Upstream's configuration does not enable
  `import/no-cycle`, and an ESLint run with that rule switched on did not find
  these cycles either; why it reported nothing was not looked into.
- **What callers import.** The module was loaded the way seam 2 loads it
  (`loadSource` of `verify/team-analytics-logging/helper.cjs`) and its runtime
  export names listed before and after the move: the same 19 names. The type
  exports (`InputMethod`, `RecordName`, `LoggedObject`, `LoggingJob`) are still
  exported from `index.ts`; the type check covers the nine call sites that import
  from `utils/team-analytics-logging`. No caller file changed.
- **Styles.** The nine style files were compiled with Sass the way the UI build
  resolves them (load path `cvat-ui/src`) before and after the automatic fixes:
  the CSS is byte for byte the same (`rgba(0, 0, 0, 15%)` compiles to the same
  output as `rgba(0, 0, 0, 0.15)`). The fixes by hand and the move touch no style
  file.
- **Visible text.** The two strings split for `max-len` in `freshness.tsx` join to
  the same text as before; the page suite matches the stale warning's whole
  sentence. The full view's summary line only moved to a line of its own, and the
  page suite matches it too. A cell whose content moved to its own line
  in `details-table-card.tsx` gets no extra text: JSX drops whitespace that
  contains a line break.

## Type check and the workspace packages

The plain type check (`tsc -p cvat/cvat-ui/tsconfig.json`) resolves `cvat-core`,
`cvat-canvas`, `cvat-canvas3d` and `cvat-data` through the links in
`cvat/node_modules` (`cvat-core -> ../cvat-core`, ...). In a worktree whose
`cvat/node_modules` is a link to the main checkout's, those relative links resolve
inside the main checkout, so `--listFiles` showed 108 `cvat-core`, 25
`cvat-canvas`, 10 `cvat-canvas3d` and 1 `cvat-data` files from the main checkout
and none from the worktree. The UI files themselves came from the worktree.

To check against the worktree's own packages, a throwaway configuration outside
the repository extended `cvat-ui/tsconfig.json` with `paths` mapping the four
package names to the worktree's directories. With it `--listFiles` showed the
same file counts, all from the worktree, and the check passed before the first
change and after the last. The four package directories were also identical in
both checkouts (`diff -rq`), and this ticket changes none of them.

## Not verified

- The UI image build and the running page: no image was built and no stack
  started. The checks above cover the source, the compiled styles and the suites.
- The type check in a checkout with its own installed dependencies: the merger
  reruns it in the main checkout.

The scripts of the three stated checks (import cycles, runtime exports, Sass
compilation) and the saved tool outputs stay in the defect fixes' shared notes
directory, outside the repository, as `t05/cycles.cjs`, `t05/exports.cjs` and
`t05/sass.cjs`.
