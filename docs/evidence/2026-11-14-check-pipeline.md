# The fork's check pipeline, 2026-11-14

Ticket 13 of the defect fixes. `prek.toml` at the repository root holds the
pipeline; `prek run --all-files` runs it. The invocation, its prerequisites and
the suites kept out of it are written in section 4 of
`docs/upstream-upgrade.md` ("Check pipeline"). A hook pipeline is default (a)
of the defect fixes' plan: the owner was not asked whether the gate should be
one.

Run on one host with prek 0.5.10, uv 0.11.32, Node 22.22.1 and Docker, from a
worktree whose `cvat/node_modules` and `verify/node_modules` link to the main
checkout's installed copies. The pipeline was not installed as git hooks, and
no git configuration was changed.

## What the pipeline holds

| Hook id | Command | Selects |
| --- | --- | --- |
| `eslint` | `tools/gate/ui-lint.sh eslint` | tracked `.ts`/`.tsx` under `cvat/` whose content differs from the import tag |
| `stylelint` | `tools/gate/ui-lint.sh stylelint` | tracked `.scss` under `cvat/` likewise |
| `type-check` | `tsc -p cvat/cvat-ui/tsconfig.json` | the whole UI, as upstream's `type-check` |
| `ruff` | `uv run --locked --only-group lint ruff check` | the Python outside `cvat/` and `tools/git-filter-repo` (`ruff.toml`) |
| `policy-patched` | `verify/policy_test.sh` | the patched policies of the tree |
| `policy-stock` | `verify/policy_test.sh stock` | the stock policies of the import tag |
| `task-progress`, `ta-logging`, `ta-page` | `node --test verify/<suite>.cjs` | the three fast frontend suites |

Every hook passes no file names from prek and runs on every invocation. No
hook takes `--fix` or writes a file. The hooks run one after another (shown
with two sleeping hooks before the real configuration was written); ruff runs
with `RAYON_NUM_THREADS=1`.

## Choices

- **ruff's version** is declared in a dependency group of a root
  `pyproject.toml` (`ruff==0.17.3`) and locked with hashes in `uv.lock`; the
  hook runs it through `uv run --locked`, which fails when the lock is out of
  date. 0.17.3 is the newest release older than two weeks. `ruff.toml` keeps
  its settings.
- **ruff's rule set** is stated in `ruff.toml` (`E4`, `E7`, `E9`, `F`, ruff's
  default before 0.16). With no `select`, ruff 0.16 and later enable a larger
  default: 51 findings on the fork's Python, against 3 with the stated set.
  Those 51 are mostly in the service tests that other tickets edit now; they
  were not taken on here.
- **The three findings** of the stated set were fixed with `ruff check --fix`
  in a commit of their own (`c4171a0`): one unused import, two lines with
  several imports.
- **Formatting is not checked.** `ruff format --check` would reformat 45 of
  the fork's 69 Python files (about 3,300 changed lines, most in the service).
  The fork's Python was never formatted with ruff; a sweep is a decision of its
  own, and would conflict with the tickets editing the service now.
- **`cvat/` is excluded in `ruff.toml`** with `force-exclude`, so a ruff run by
  hand on a path under `cvat/` skips it too: the widened import proof records
  that a formatter run once rewrote the import's ClickHouse setup file.
- **The fork's UI files** are found by blob comparison of the working tree with
  the import tag, not by a list in the configuration, so files that other
  tickets add are checked once tracked. On this branch before the merge of the
  integration branch the script selected the same 75 files as the `git diff`
  list of section 4 of the upgrade procedure (compared as sorted lists).

## Live outcomes

| Run | Change | Exit | Failed hook |
| --- | --- | --- | --- |
| all files, `d800703` | none | 0 | none |
| all files | a double-quoted string added to `cvat-ui/src/utils/team-analytics-logging/record.ts` (fork file) | 1 | `eslint` (`quotes`, 1 error) |
| all files | `result == patched` changed to `!=` in `verify/opa_issues_test.rego` | 1 | `policy-patched` and `policy-stock` (`test_unassigned_member_actions`: FAIL, 1/17 each) |
| all files | an expected duration changed in `verify/team-analytics-logging/guarding.test.cjs` | 1 | `ta-logging` (54 pass, 1 fail) |
| all files | `import os, sys` appended to `cvat/components/analytics/clickhouse/init.py` | 0 | none |
| all files, after the merge of `789a1e8` | none | 0 | none |

Each throwaway edit was made in the working tree, not committed, and reverted
with `git checkout`; `git status --short` was empty after each revert and
after each passing run. In each failing run every other hook passed.

The `init.py` edit is a finding for ruff (two errors with ruff run on the file
with `--isolated`); the pipeline's ruff did not read the file.

Untouched upstream UI files: ESLint run by hand with the pipeline's flags on
the 546 tracked `.ts`/`.tsx` files under `cvat/cvat-ui/` outside the fork's list
exits 1 with 10 warnings in 8 files
(`@typescript-eslint/explicit-function-return-type`). The pipeline passed at
the same time, so none of them reached the linter.

After the merge of the integration branch the run selected 67 script and 10
style files, the policy test passed 27 of 27 on each side, and the suites
reported 20 pass and 1 skipped (the browser check, no `BROWSER_BIN`), 63 pass
and 209 pass, with no failure.

## Not verified

- A fresh clone. The run created `.venv` from nothing and installed ruff from
  the lock, but `cvat/node_modules` and `verify/node_modules` were links to
  installed copies, and the import tag was already present.
- The type check against the worktree's own workspace packages: in a worktree
  it reads them from the main checkout (see the first lint run's evidence).
- The pipeline on the integration branch after the tickets built in parallel
  are merged; the orchestrator reruns it.
- The suites kept out (service seam, stack, browser check, legacy launchers)
  were not run for this ticket.
