# 01: Administrators only

**What to build:** Team Analytics (the page, its API and later its settings) is for administrators only. An administrator with an organization selected reads Organization scope; with none selected, Instance scope. Owners, maintainers and everyone else are refused with a plain 403; a signed-out caller gets 401. Decided by the owner on 2026-11-15 (item 6 of the spec). It comes first because it simplifies the rest: the organization rule, the `organization_required` answer, the `admin` flag in the scope, the cache key and the reduced status block all go.

Backend: the organization rule leaves the app's policy (`cvat/apps/team_analytics/rules/team_analytics.rego`), whose one remaining rule is the administrator check; the policy test configuration (`rules/tests/configs/team_analytics.csv`) follows, and the generated rego tests are regenerated with `verify/policy_generated.sh`. `READING_ROLES` and the `organization_required` branch leave `views.py` (the 401 branch stays; `scope_of` stays). The `admin` flag leaves `core/scope.py`, the cache key in `reads.py`, `jobs.py` and the status history.

Page: `access.ts` admits the admin group only; the fork's `currentOrganizationRole` plumbing in the header and the `select-organization` state and its parsing in `service.ts` and `team-analytics-view.tsx` go.

Tracker: issue 19 of `.scratch/team-analytics/` is closed as `wontfix`, an accepted risk.

**Blocked by:** none.

**Status:** ready-for-agent

- [ ] The policy tests (generated and hand-written) show administrators allowed for every Team Analytics action, with and without an organization, and every other role (owner, maintainer, supervisor, worker, `user` with no organization) refused.
- [ ] No code path returns `{"error": "organization_required"}`; a refused caller gets the plain 403 and a signed-out caller 401.
- [ ] The `admin` flag is gone from the core's scope, the read cache key and the status answer, and the calculation and read-path suites (`verify/team-analytics-backend/tests/`) pass with the changed stand-ins.
- [ ] Page suite (`verify/team-analytics-page/`): only an administrator sees the header link and the page; an owner or maintainer sees neither, and the "select an organization" state no longer exists.
- [ ] On the live stack (checked in ticket 08): an owner and a maintainer get 403 on every endpoint; an administrator gets figures for a selected organization and for Instance scope.
- [ ] Docs handoff recorded for the integration pass: Organization scope and Instance scope in `GLOSSARY.md`, TA-1 access and IAM-2's reason in `docs/fork-specification.md`, `README.fork.md`, and the comment beside the app's wiring in `cvat/settings/base.py`.

## Comments
