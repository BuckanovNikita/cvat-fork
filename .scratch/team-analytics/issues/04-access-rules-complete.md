# 04: Access rules complete

**What to build:** Every person gets exactly the figures their role allows and nobody else's. Ticket 02 allowed and refused the two obvious cases; this ticket settles all of them and gives the page a clear state for each refusal. See the Access control section of the spec (`../spec.md`) and ADR 0001.

**Blocked by:** 02 (Tracer: working time per annotator for the last week).

**Status:** resolved

- [x] A member of the admin group who names an organization gets organization scope for it; with none named, instance scope, including job work in personal workspaces.
- [x] Being an administrator is decided by membership of the admin group, not only by the superuser flag.
- [x] An owner and a maintainer get organization scope for their own organization.
- [x] With real accounts on the stack, a supervisor, a worker and a user who is a member of nothing get 403 on every endpoint, and a maintainer removed through CVAT's API gets 403 on the same session once the one-minute reuse has passed, with and without an organization.
- [x] A maintainer of one organization is refused another organization's figures, whatever identifiers the request carries.
- [x] A maintainer who names no organization is refused, and the page asks them to select an organization.
- [x] An ordinary annotator sees no header link and, on a direct visit, a "not available" message that names the roles the page is for.
- [ ] When CVAT cannot be reached the service refuses rather than answering from stale knowledge: shown by the service suite with a stand-in CVAT that stops answering; not seen on the stack.
- [x] A member removed through CVAT's API is refused on the same session after the one-minute reuse has passed (the stack's case waits that time with a margin).
- [ ] CVAT's answers are reused for at most one minute per caller: shown by the service suite with supplied CVAT answers; not seen on the stack.
- [x] No link is shown on a server where analytics is not enabled.
- [x] Every case above is tested through the service's read interface; the page states are tested through the page with supplied responses.

## Comments

2026-11-14: Resolved on `feat/team-analytics-page` by merge `96f5415`. Review fixes that followed are in merge `401576e`. Live results, review outcomes and what remains unverified: `docs/evidence/2026-11-14-team-analytics-final-run.md`.

2026-11-15: Ticket 27 of the defect fixes restated three criteria that were ticked on a reading (decisions ledger, V11), as what was shown, and ticked again only what the fresh stack showed. Original wording: "A supervisor, a worker, a user who is not a member and a user removed from the organization are refused."; "When CVAT cannot be reached the service refuses rather than answering from stale knowledge." (shown with a stand-in only, now unticked); "CVAT's answers are reused for at most one minute per caller, so a removed member loses access within that time." (split: the stack part ticked, the reuse bound unticked). Evidence: `docs/evidence/2026-11-15-final-run-on-a-fresh-stack.md`.
