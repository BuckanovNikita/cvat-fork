# 06: Policies patched in place with the role floor

**What to build:** An organization member with at least the `worker` global role can do everything with the issues and comments of their organization. An account below that floor gets exactly what stock CVAT gives it, for every action. The patch lives as an ordinary edit of the imported stock policies, and the policy test runs from this repository alone. See "Policies and the fork server image" in the spec (`../spec.md`).

**Blocked by:** 04 (Re-import the release with the widened filter).

**Status:** ready-for-agent

- [ ] Test first: the policy test gains cases for a caller with no global role, one who is staff of the issue and one who is not. For each, the patched policies must decide as the stock ones for every action and for the list filter. These cases fail against the patch as it is today.
- [ ] Both imported policies carry the patch. The added member rule and the added branch of the list filter require the `worker` global role, and the stock member branch of the list filter is restored after the patched one.
- [ ] The existing expectations still hold: workers and supervisors are unrestricted inside their organization; non-members, removed members and other organizations are refused; sandbox behaviour is stock.
- [ ] The policy test reads the policies and their helper policies from the import. It passes against the stock release tag with the stock expectations and against the patched tree with the patched ones. No outside checkout is used.
- [ ] The difference between the patched policies and the stock ones, taken against the import's tag, is exactly the patch.
- [ ] The fork specification's section on issue and comment permissions states the floor and the invariant.
- [ ] The copied policy directory is not edited; it is removed in ticket 12.
- [ ] The policy change gets an independent review.
