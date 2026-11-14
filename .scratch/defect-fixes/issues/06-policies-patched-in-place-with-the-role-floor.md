# 06: Policies patched in place with the role floor

**What to build:** An organization member with at least the `worker` global role can do everything with the issues and comments of their organization. An account below that floor gets exactly what stock CVAT gives it, for every action. The patch lives as an ordinary edit of the imported stock policies, and the policy test runs from this repository alone. See "Policies and the fork server image" in the spec (`../spec.md`).

**Blocked by:** 04 (Re-import the release with the widened filter).

**Status:** resolved

- [x] Test first: the policy test gains cases for a caller with no global role, one who is staff of the issue and one who is not. For each, the patched policies must decide as the stock ones for every action and for the list filter. These cases fail against the patch as it is today.
- [x] Both imported policies carry the patch. The added member rule and the added branch of the list filter require the `worker` global role, and the stock member branch of the list filter is restored after the patched one.
- [x] The existing expectations still hold: workers and supervisors are unrestricted inside their organization; non-members, removed members and other organizations are refused; sandbox behaviour is stock.
- [x] The policy test reads the policies and their helper policies from the import. It passes against the stock release tag with the stock expectations and against the patched tree with the patched ones. No outside checkout is used.
- [x] The difference between the patched policies and the stock ones, taken against the import's tag, is exactly the patch.
- [x] The fork specification's section on issue and comment permissions states the floor and the invariant.
- [x] The copied policy directory is not edited; it is removed in ticket 12.
- [x] The policy change gets an independent review.

## Comments

- 2026-11-14: Shown in `docs/evidence/2026-11-14-policies-role-floor.md`. The new cases were run on the stock tag (pass), against the old copies under `opa/rules/` (3 fail), then on the patched tree and the stock tag (all pass). Commands: `verify/policy_test.sh` (patched) and `verify/policy_test.sh stock`, from the repository root. The marker in each patched policy is the comment text `Local patch (role floor)`.
- 2026-11-14: The independent review is not the implementer's; it follows the merge, so that criterion stays unticked.
- 2026-11-14: Merged into `feat/team-analytics-page` in merge `ff0c4a9`; evidence `docs/evidence/2026-11-14-policies-role-floor.md`. On the merged tree `verify/policy_test.sh` and `verify/policy_test.sh stock` each pass 17 of 17 tests; against `cvat-v2.82.0-widened` both patched policies show 12 added lines and none deleted, and the iam `utils.rego` and `organizations.rego` are identical to the tag's. The ticket stays open: the independent review of the policy change is outstanding.
- 2026-11-14: Reviewed independently after merge `ff0c4a9`: no defect in the policies. The findings and what was done about each are under "Independent review" and "Cases added after the review" in `docs/evidence/2026-11-14-policies-role-floor.md`. The coverage gaps it found are closed by the cases in commit `9a22568`; both runs pass 27 of 27.
- 2026-11-14: Resolved. The policy change was merged in `ff0c4a9` and the review follow-up in `b41bec3`; evidence `docs/evidence/2026-11-14-policies-role-floor.md`. On the merged tree `verify/policy_test.sh` and `verify/policy_test.sh stock` each pass 27 of 27 tests, and `cvat/cvat/apps` and `opa/` are unchanged against `ff0c4a9`.
