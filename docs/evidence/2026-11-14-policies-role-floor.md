# Policies patched in place with the role floor, 2026-11-14

Ticket 06 of the defect fixes. The patched issue and comment policies admitted
any member of the owning organization whatever its global role, including none,
and the patch had replaced the stock member branch of the list filter. The
patch is now an edit of the imported stock files
`cvat/cvat/apps/engine/rules/{issues,comments}.rego`, with the added member
rule and the added filter branch requiring `utils.has_perm(utils.WORKER)`, and
the stock member branch of the filter following the added one.

Every run below is the policy test (`verify/opa_issues_test.rego`) evaluated by
the local image `openpolicyagent/opa:1.12.2` with `--network none --cpus=1`
and read-only mounts of the test file and the four policy files only. These are
checks with supplied inputs: synthetic OPA inputs, no CVAT server, no bundle
delivery, no HTTP API.

## Commands

From the repository root:

- Patched tree, patched expectations: `verify/policy_test.sh`
- Stock tag, stock expectations: `verify/policy_test.sh stock`. It extracts the
  four policies from `cvat-v2.82.0-widened` with `git show` into a temporary
  directory, adds `{"expected":{"patched":false}}`, and removes it afterwards.

## Observed, in order

1. New cases added (a caller with no global role: staff of the issue through
   the job assignee, not staff, every organization role, the list filter,
   sandbox and non-member), run against the stock tag before any patch:
   17 of 17 pass. The written-out expectations are stock's decisions.
2. The same test against the old patch, the copies under `opa/rules/`, with the
   in-tree helpers: 14 pass, 3 fail:
   `test_no_global_role_staff_gets_stock_actions`,
   `test_no_global_role_nonstaff_gets_stock_actions`,
   `test_no_global_role_member_gets_stock_list_filter`.
3. Patch applied to the imported files (commit `4d6251d`). Patched tree:
   17 of 17 pass.
4. Stock tag again: 17 of 17 pass.

The no-global-role cases do not branch on the patched flag, so the same literal
expectations passing on both runs is the invariant: for such a caller the
patched policies decide as stock for every action and for the list filter.

## Static checks

- `git diff cvat-v2.82.0-widened HEAD:cvat` over the three rule directories:
  12 added and 0 removed lines in each resource policy; `utils.rego` and
  `organizations.rego` identical to the tag.
- Marker: the comment text `Local patch (role floor)` appears twice in each
  patched file, never in the tag's files and never in the old copies under
  `opa/rules/` (which say `Local patch:` without the floor).
- `opa/` and the Compose files are unchanged against `feat/team-analytics-page`.

## Not verified here

- That the server serves the patched files in its bundle (ticket 07 builds the
  image, ticket 08 checks the bundle) and the live API outcome (ticket 09).
- The independent review of the policy change, which follows the merge.
