# 13: One gate for a change

**What to build:** One command checks a change the same way every time: the linters, the type check, the policy test and the fast suites. A hook pipeline holds the commands. The owner chose how the lint configuration arrives but was not asked whether the gate should be a hook pipeline; that is a default. See "Tooling" in the spec (`../spec.md`).

**Blocked by:** 02 (Frontend tests fail without their browser environment), 05 (First lint run on the fork's UI code), 06 (Policies patched in place with the role floor).

**Status:** resolved

- [x] A hook pipeline configuration holds ESLint, stylelint and the type check on the fork's UI code, ruff on the fork's Python, the policy test, and the three fast frontend suites.
- [x] The pipeline's all-files run passes on the branch.
- [x] It fails when a lint error is introduced, when a policy expectation is broken and when a frontend test fails. Each is shown once and noted in this ticket.
- [x] Hooks check and change only files the fork owns or edited; they never reformat untouched upstream files of the import.
- [x] Tool versions come from the project's dependency configuration.
- [x] The suites that need ClickHouse or the stack are not in the pipeline; they are documented as separate commands with their prerequisites.
- [x] The invocation and its prerequisites are written in one place.

## Comments

2026-11-14: Built on branch `ticket/13-gate`. The pipeline is `prek.toml` with
`tools/gate/ui-lint.sh`. ruff is declared in `pyproject.toml` and locked in
`uv.lock`; its settings and rule set are in `ruff.toml`. Evidence:
`docs/evidence/2026-11-14-check-pipeline.md`. The invocation, its prerequisites
and the commands kept out are in section 4 of `docs/upstream-upgrade.md`
("Check pipeline"). The hook pipeline stays a default nobody was asked about.

Failure demonstrations. Each was a throwaway working-tree edit, run with
`prek run --all-files` and then reverted; `git status` was empty afterwards:

- Lint error: a double-quoted string in the fork's `record.ts`. Exit 1, hook
  `eslint` failed (`quotes`); every other hook passed.
- Broken policy expectation: `result == patched` changed to `!=` in
  `verify/opa_issues_test.rego`. Exit 1, hooks `policy-patched` and
  `policy-stock` failed (`test_unassigned_member_actions`).
- Failing frontend test: an expected duration changed in
  `verify/team-analytics-logging/guarding.test.cjs`. Exit 1, hook `ta-logging`
  failed (54 pass, 1 fail).

Fork files only: the UI linters take only the files whose content differs from
the import tag. Untouched upstream files that have 10 ESLint warnings never
reached the linter. An edit with ruff findings in
`cvat/components/analytics/clickhouse/init.py` passed the pipeline, because
ruff excludes `cvat/`. No hook writes files.

Tool versions: the UI tools come from the import's lock through
`cvat/node_modules`, jsdom from `verify/package.json`, ruff from
`pyproject.toml` and `uv.lock`, and the OPA image from `verify/policy_test.sh`.
Node, prek, uv and Docker themselves are host prerequisites and are not pinned.

Outstanding:

- Formatting is not gated. `ruff format --check` would reformat 45 of the
  fork's 69 Python files, 43 of them in the service and its tests, and that
  sweep was not done here.
- ruff's rule set is held at `E4`, `E7`, `E9` and `F`. The larger default of
  ruff 0.16 and later finds 50 issues with the locked ruff: 5 in the service,
  22 in its tests and 23 in `verify/`.
- A fresh clone was not tried. The import tag is local only (section 1 of the
  upgrade procedure), so a fresh clone must recreate it before the UI linters
  and the stock policy test can run.

2026-11-14: Resolved by merge `868ccf5f` into `feat/team-analytics-page`; evidence in `docs/evidence/2026-11-14-check-pipeline.md`. On the merged tree `prek run --all-files` exited 0 with all nine hooks passed (ESLint, stylelint, type check, ruff, both policy tests, the task progress, UI logging and page suites); `.venv` is ignored by git; nothing under `cvat/` changed.
