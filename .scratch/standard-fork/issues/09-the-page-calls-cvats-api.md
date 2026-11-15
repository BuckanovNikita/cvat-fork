# 09: The page calls CVAT's API

**What to build:** The page's single service boundary calls `/api/team-analytics/` through cvat-core. See "The page" in the spec.

**Blocked by:** 07.

**Status:** resolved

- [x] Requests go through `core.server.request`; cvat-core is not edited.
- [x] The organization is attached by cvat-core; the page sends none of its own.
- [x] 401, 403 and `organization_required` give the states they gave before; a 404 gives "not available"; a 429 that outlives the retries gives the error panel.
- [x] The page and logging suites pass; the tests that assert request addresses assert the new ones.
- [x] ESLint, stylelint and the type check pass.

## Comments

2026-11-15: `74ec38ed`. The boundary is `requestService(endpoint, params)`, returning the status and body. Page suite 240 tests, logging 77, none failed; ESLint, stylelint and the type check pass. cvat-core keeps a response body only as text in the error it throws, so `organization_required` is recognised from that text; the body must not carry a `detail` or `message` key beside `error`.

Every test replaces cvat-core's request function. That cvat-core attaches the organization, retries a 429 and that the error text has the expected form in a real browser are shown by the stack run, not here.
