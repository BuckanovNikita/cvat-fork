# 11: The Ingress route and four access cases on the stack

**What to build:** The service's Ingress route is shown to work, and four access cases that were only ever seen against a stand-in are seen against a real CVAT. See "Stack and removals" in the spec (`../spec.md`) and story 106 of the Team Analytics spec.

**Blocked by:** 08 (The stack runs on the fork server image and the in-tree chart).

**Status:** ready-for-agent

- [ ] The service's Ingress manifest is applied in the stack's namespace beside the proxy, under the cluster's Ingress class, and adds no cluster-wide object.
- [ ] One status request through the Ingress with a real session is answered; the same request without a session is refused as signed out.
- [ ] A member removed from the organization is refused once the service's identity cache has expired.
- [ ] An administrator by group who is not a superuser reads instance scope and a named organization.
- [ ] Job work done in a personal workspace appears under instance scope and under no organization.
- [ ] Credentials sent as an authorization header get the same decisions as a session cookie.
- [ ] The run judges each case itself, and the results are kept in a dated evidence file.
- [ ] Teardown removes the Ingress with the namespace.
