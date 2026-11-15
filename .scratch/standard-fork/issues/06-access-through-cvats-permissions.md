# 06: Access through CVAT's permission system

**What to build:** A policy file and a permission class decide who may read, on every request. See "Access" in the spec and stories 1 to 6.

**Blocked by:** 05.

**Status:** resolved

- [x] Administrators are allowed with and without an organization; owners and maintainers in their organization; everyone else is refused.
- [x] Upstream's generated policy tests cover the rule for every privilege, role and context, and pass.
- [x] An administrator without an organization gets instance scope; with one, that organization.
- [x] An owner or maintainer of some organization who names none gets 403 with the body `{"error": "organization_required"}`; anyone else refused gets a plain 403.
- [x] An unknown organization is CVAT's 404.
- [x] The page's link and refusal states behave as before for every role.

## Comments

2026-11-15: `1bbe8482` (policy and tests), `6e74221c` (permission class, scope mapping, the `organization_required` body). Upstream's generator makes 24 cases for the policy and all pass; with the role condition taken out 9 fail, with the administrator rule taken out 4 fail. The generated tests cannot notice the `view` scope condition being removed, since `view` is the only scope. Upstream's whole generated suite passes with four rows added to each of the issue and comment configurations (29,208 cases; 120 failed before). `verify/policy_test.sh` passes patched and stock.

Open until the stack run: everything a request shows (instance scope for an administrator, the `organization_required` body, the 404, the page's states by role).

2026-11-15: Shown on the stack (`docs/evidence/2026-11-15-backend-acceptance.md`): the bodies as served (403 `organization_required` for an owner or maintainer naming no organization, DRF's 403 for anyone else, 401 signed out, 404 for an unknown organization), an administrator by group with and without an organization, a personal workspace under instance scope only, cookie, Basic and Bearer credentials deciding alike, a removed member refused on the next request, and the page's states by role in a browser.
