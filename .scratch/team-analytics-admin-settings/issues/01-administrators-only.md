# 01: Administrators only

**What to build:** Team Analytics (the page, its API and later its settings) is for administrators only. An administrator with an organization selected reads Organization scope; with none selected, Instance scope. Owners, maintainers and everyone else are refused with a plain 403; a signed-out caller gets 401. Decided by the owner on 2026-11-15 (item 6 of the spec). It comes first because it simplifies the rest: the organization rule, the `organization_required` answer, the `admin` flag in the scope, the cache key and the reduced status block all go.

Backend: the organization rule leaves the app's policy (`cvat/apps/team_analytics/rules/team_analytics.rego`), whose one remaining rule is the administrator check; the policy test configuration (`rules/tests/configs/team_analytics.csv`) follows, and the generated rego tests are regenerated with `verify/policy_generated.sh`. `READING_ROLES` and the `organization_required` branch leave `views.py` (the 401 branch stays; `scope_of` stays). The `admin` flag leaves `core/scope.py`, the cache key in `reads.py`, `jobs.py` and the status history.

Page: `access.ts` admits the admin group only; the fork's `currentOrganizationRole` plumbing in the header and the `select-organization` state and its parsing in `service.ts` and `team-analytics-view.tsx` go.

Tracker: issue 19 of `.scratch/team-analytics/` is closed as `wontfix`, an accepted risk.

**Blocked by:** none.

**Status:** resolved

- [x] The policy tests (generated and hand-written) show administrators allowed for every Team Analytics action, with and without an organization, and every other role (owner, maintainer, supervisor, worker, `user` with no organization) refused.
- [x] No code path returns `{"error": "organization_required"}`; a refused caller gets the plain 403 and a signed-out caller 401.
- [x] The `admin` flag is gone from the core's scope, the read cache key and the status answer, and the calculation and read-path suites (`verify/team-analytics-backend/tests/`) pass with the changed stand-ins.
- [x] Page suite (`verify/team-analytics-page/`): only an administrator sees the header link and the page; an owner or maintainer sees neither, and the "select an organization" state no longer exists.
- [x] On the live stack (checked in ticket 08): an owner and a maintainer get 403 on every endpoint; an administrator gets figures for a selected organization and for Instance scope.
- [x] Docs handoff recorded for the integration pass: Organization scope and Instance scope in `GLOSSARY.md`, TA-1 access and IAM-2's reason in `docs/fork-specification.md`, `README.fork.md`, and the comment beside the app's wiring in `cvat/settings/base.py`.

## Comments

2026-11-16: Done in `e3fb1e7d0` (backend) and `1f1776e55` (page), with the stack's reads moved to an administrator in `213010452`; the first review's medium page finding (a non-administrator briefly saw Settings and the filter row) was fixed in `09ac22a85`, so the page decides from the account's group and sends no Team Analytics request at all. Shown: the policy tests (patched, stock and upstream's generated suite) and the page and calculation suites passed in a fresh clone's `prek` at `0bf2f41cd`; the calculation suite passed whole (370 tests, `5dea1cc89`, server image `7ead6d1cec4b`); `organization_required` and the scope's `admin` flag are gone from the app and the page (only page tests name the old body, as one no longer sent). On the stack, `up` of the final run: `ta-admin` 200 on all five read endpoints for three organizations and for instance scope, every owner, maintainer, supervisor, worker and outsider 403 on all five, signed out 401, and `revoked-admin` refused on its next 8 requests. Record: `docs/evidence/2026-11-16-open-lines-closed-and-admin-settings.md`.
