# 04: Access rules complete

**What to build:** Every person gets exactly the figures their role allows and nobody else's. Ticket 02 allowed and refused the two obvious cases; this ticket settles all of them and gives the page a clear state for each refusal. See the Access control section of the spec (`../spec.md`) and ADR 0001.

**Blocked by:** 02 (Tracer: working time per annotator for the last week).

**Status:** ready-for-agent

- [ ] A member of the admin group who names an organization gets organization scope for it; with none named, instance scope, including job work in personal workspaces.
- [ ] Being an administrator is decided by membership of the admin group, not only by the superuser flag.
- [ ] An owner and a maintainer get organization scope for their own organization.
- [ ] A supervisor, a worker, a user who is not a member and a user removed from the organization are refused.
- [ ] A maintainer of one organization is refused another organization's figures, whatever identifiers the request carries.
- [ ] A maintainer who names no organization is refused, and the page asks them to select an organization.
- [ ] An ordinary annotator sees no header link and, on a direct visit, a "not available" message that names the roles the page is for.
- [ ] When CVAT cannot be reached the service refuses rather than answering from stale knowledge.
- [ ] CVAT's answers are reused for at most one minute per caller, so a removed member loses access within that time.
- [ ] No link is shown on a server where analytics is not enabled.
- [ ] Every case above is tested through the service's read interface; the page states are tested through the page with supplied responses.
