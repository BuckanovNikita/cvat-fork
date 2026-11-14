# Compose and the copied policies removed, 2026-11-15

Ticket 12 of the defect fixes (plan rows 1.4 and 1.5). Branch `ticket/12-remove-compose`,
from `feat/team-analytics-page` at `775ff76e`, merged with it again at `ccef1cc2`. The
removal is commit `2ad619ca`, the documents `d05adde1`.

## What went and what stayed

Each file was kept only if the stack (`verify/team-analytics-stack/run.sh`), the check
pipeline (`prek.toml`) or another kept file calls it. The callers were found by a search of
the tree for each name before the removal.

| Path | Decision | Why |
| --- | --- | --- |
| `docker-compose.override.yml` | removed | The Compose overlay; it mounted `opa/rules` into `cvat_server`. The import has no Compose file since the widened re-import |
| `verify/docker-compose.verify.yml` | removed | Overlay of `verify/run.sh` only |
| `verify/docker-compose.opa-issues.yml` | removed | Overlay of `verify/opa_issues.sh` only |
| `verify/docker-compose.opa-patch.yml` | removed | Mount overlay of `verify/opa_issues.sh` only |
| `verify/run.sh` | removed | Compose launcher (task progress); cannot run without the import's Compose file |
| `verify/opa_issues.sh` | removed | Compose launcher (issue permissions); same |
| `verify/seed.py` | removed | Called only by `verify/run.sh`; the stack seeds task progress with `task_progress.py` |
| `verify/mkimg.py` | removed | Called only by `verify/run.sh` and `verify/opa_issues_seed.py`; the stack makes its images in `stack_api.py` |
| `verify/opa_issues_seed.py` | removed | Called only by `verify/opa_issues.sh`; replaced by `seed_users.py` with `issue_accounts.json` |
| `verify/opa_issues_check.py` | removed | Called only by `verify/opa_issues.sh`; its matrix rows are in `issue_matrix.py` (`2026-11-14-stack-issue-matrix.md`, "Reuse of the Compose-era scripts") |
| `opa/` (`README.md`, `rules/issues.rego`, `rules/comments.rego`) | removed | The copied policies; the policies are patched in place in the import and delivered in the fork server image (ADR 0004). Nothing read `opa/` but the two Compose overlays |
| `verify/opa_issues_test.rego` | stays | The policy test's cases, run by `verify/policy_test.sh` |
| `verify/policy_test.sh` | stays | The policy test; hooks `policy-patched` and `policy-stock` |
| `verify/policy_bundle.sh` | stays | The bundle check; called by the stack (`check-policies`, `check-bundle`) |
| `verify/task_progress.cjs` | stays | Hook `task-progress` |
| `verify/team_analytics_logging.cjs`, `verify/team-analytics-logging/` | stay | Hook `ta-logging` |
| `verify/team_analytics_page.cjs`, `verify/team-analytics-page/` | stay | Hook `ta-page` |
| `verify/browser-environment.cjs` | stays | Loaded by both Team Analytics suites' helpers |
| `verify/package.json`, `verify/package-lock.json` | stay | The harness's dependencies (jsdom) |
| `verify/team_analytics_service.sh` | stays | The service seam |
| `verify/team-analytics-stack/` | stays, whole | The stack, its seeds and its checks |

## Checks with supplied boundaries

The name search runs from the worktree root over every tracked and untracked file except
`node_modules`, `.venv` and git's own directory, with history (`.scratch/`) and dated evidence
(`docs/evidence/`) excluded; the ledger is under `.scratch/`. One `grep -rnF` per name:
`docker-compose.override.yml`, `docker-compose.opa-issues.yml`,
`docker-compose.opa-patch.yml`, `docker-compose.verify.yml`, `verify/run.sh`,
`opa_issues.sh`, `verify/seed.py`, `mkimg.py`, `opa_issues_seed.py`, `opa_issues_check.py`,
`opa/rules`, `opa/README`, `` `opa/` ``, `OPA_RULES`. Run at the final commit of the ticket,
it found one hit: `docs/adr/0004-…md`, line 18, "the copied `opa/` directory and the Compose
overlay that mounted it go away". An accepted decision record, which states the removal; not
edited. `INFRA_MIGRATION.md` listed the files by name in "What is affected here"; that list is
replaced by a summary that points at the table above.

Nothing else: no script, hook, configuration, README or evergreen document names a removed
file. A case-insensitive search for `compose` over the same files outside `cvat/` and
`tools/` finds, besides that one, the ADR 0003 text and its amendment, the outcome lines of
`INFRA_MIGRATION.md` and of the root README, the fork specification's line that says the
Compose files are gone, and `docs/design/team-analytics/design.md` line 107 (below).
`grep -n -i 'compose\|mount' docs/upstream-upgrade.md` finds nothing.

The check pipeline, `nice -n19 prek run --all-files` with no hook skipped, at `130c3696` and
again at the ticket's final commit:
all nine hooks passed (ESLint, stylelint, type check, ruff, the policy test on the patched and
on the stock policies, the three frontend suites). No hook referred to a removed file.

## Not verified here

- A stack `up` after the removal. The stack was in use by another ticket; the run is
  outstanding. The removed files were not called by the stack (above), which is a reading,
  not a run.
- The documents were read against the tree, not executed: the upgrade procedure's commands
  for a next release (merge, scope review, `build-server.sh`, the bundle check against
  `cvat-${TARGET}`) have not been run for any release after v2.82.0.
- `docs/design/team-analytics/design.md` still says "two custom images" (line 95) and that the
  Compose checks "are migrated separately" (line 107). It is the feature's design record and
  not among this ticket's documents; left as written.
- The independent review of the delivery change as integrated is not part of this ticket's
  work.
