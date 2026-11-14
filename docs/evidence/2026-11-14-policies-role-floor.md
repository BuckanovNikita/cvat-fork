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

## Independent review

A fresh agent that had not written the change reviewed it after the merge, given
the owner's documents and the diff `ad7cf9e..ff0c4a9` and not the implementer's
conclusions. It read the tree at `e0f4eae` and changed no tracked file.

Verdict: no correctness or security defect in the policy change.

What the reviewer ran:

- `verify/policy_test.sh` and `verify/policy_test.sh stock`: 17 of 17 each.
- A direct comparison of patched against stock `allow` and `filter`, an
  undefined result counted as a value, for both policies, over every combination
  of: the caller's organization (missing, null, without an id, another id, without
  a user, or the resource's with role owner, maintainer, supervisor, worker, null,
  missing or unknown); the resource's organization (same, another, null, missing,
  empty); the global role (admin, user, worker, null, missing, unknown); ten
  scopes, among them create in a job, create on an issue, list, null, missing and
  unknown; `organization_specified` true or false; no staff field, or each of the
  ten staff fields set to the caller, and a null project. With no, a missing or an
  unknown global role there was no difference in either result, in either policy;
  none for admin either. For `user` and `worker` every `allow` difference had the
  caller in the resource's organization with a non-null role, and no input lost
  access. Every filter difference was such a member getting `{}` inside its own
  organization's filter.
- The tag comparison: 12 added lines in each policy, helpers identical.

It also read that the added filter branch comes after the admin, sandbox and
maintainer branches and before the stock member branch, and that the runner uses
no outside checkout and no network.

Findings and what was done:

1. Every delivery path in the tree still serves the old, unfloored copies under
   `opa/rules/`: the Compose override and `verify/docker-compose.opa-patch.yml`
   mount them, `verify/opa_issues.sh` points at them, and its `Local patch` search
   also matches them. Until tickets 07, 08 and 12 land the floor exists only in the
   policy test. Owned by those tickets; nothing changed here.
2. The added allow rule has no scope check, so a member at or above the floor in
   the resource's organization is allowed any scope string, including scopes a
   later upstream release adds to these policies. Intended ("everything") and
   stated in the fork specification ("no scope whitelist"). The upgrade
   consequence is passed to ticket 12, which owns the upgrade procedure.
3. The policy test pinned the invariant on hand-picked inputs only. Closed by new
   cases in `verify/opa_issues_test.rego` (commit `9a22568`), below.
4. The fork specification's wording of the floor matches `has_perm`. Nothing to do.

Not checked by the reviewer: the Python side is not in the import, so how the
server builds the policy input was not seen. Three properties rest on upstream's
permission code: that create in a job and create on an issue carry the resource's
organization, that a removed or inactive membership arrives as role null, and that
organization ids are integers. Nothing was run against a running CVAT.

## Cases added after the review

All with the policy files unchanged:

| Case | Old copies under `opa/rules/` | Stock tag | Patched tree |
| --- | --- | --- | --- |
| Other organization refused, global role `worker` | pass (a pin, never red) | pass | pass |
| List-filter contract, global role `worker` | pass (a pin against the old copies) | pass | pass |
| No global role, staff through the task owner: actions and list filter | fail | pass | pass |
| Missing global role: staff (job assignee, task owner), not staff, list filter | fail | pass | pass |
| Unknown global role (`superuser`): the same three | fail | pass | pass |

The list-filter case for global `worker` does tell stock from patched: run on
the stock files with the patched expectations it fails, as do the two older
cases on member access. Stock gives a global `worker` the staff filter even as
an organization maintainer or owner.

Totals: old copies 16 of 27 pass, 11 fail (the three earlier no-global-role cases
and the eight added below-floor ones, nothing else); stock tag 27 of 27;
patched tree 27 of 27. With every case in one rule, the staff case for all
below-floor roles ran past OPA's default limit of 5 s per test at one core,
which is an error, not a decision. It was split per case, and the runner now
passes `--timeout 60s`.

## Not verified here

- That the server serves the patched files in its bundle (ticket 07 builds the
  image, ticket 08 checks the bundle) and the live API outcome (ticket 09).
