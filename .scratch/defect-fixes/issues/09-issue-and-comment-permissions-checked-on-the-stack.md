# 09: Issue and comment permissions checked on the stack

**What to build:** The issue and comment patch is seen working with real accounts on Kubernetes. Until now it was checked only by the policy test; the live matrix was written for Compose and never run against the corrected delivery. See "Stack and removals" in the spec (`../spec.md`).

**Blocked by:** 08 (The stack runs on the fork server image and the in-tree chart).

**Status:** ready-for-agent

- [ ] The stack seeds an organization with an owner, a maintainer, a supervisor, workers, a member with no global role, a non-member and a member of another organization, and an issue with comments on a job none of the workers is assigned to.
- [ ] Through the real API, an unassigned worker and an unassigned supervisor create, view, update and delete issues and comments of their organization, and list all of them.
- [ ] The member with no global role gets what stock CVAT gives: it cannot act on issues it is not staff of, and its list holds only its own.
- [ ] The non-member and the member of another organization are refused, and nothing crosses organizations.
- [ ] The run judges the matrix itself, pass or fail; it is not left for reading.
- [ ] The existing seed and check scripts are reused where they fit.
- [ ] The matrix is kept in a dated evidence file.
