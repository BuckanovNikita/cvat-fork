# 08: Stack checks on the new rules

**What to build:** The stack checks under `verify/team-analytics-stack/` follow the new access rule and the new home of the Technical accounts list. Nearly every check reads figures as an owner or a maintainer today.

- One `reader(org)` helper in `stack_api.py`; every figure read in `final_run.py`, `fixes_run.py`, `acceptance.py`, `access_cases.py`, `org_creation.py` and in `final_browser.cjs`, `fixes_browser.cjs` and `browser_check.cjs` goes through an administrator. Owners keep creating projects and tasks.
- `check-cross-org` becomes: an administrator's answer for one organization is not served for another organization or for Instance scope.
- Seeding sets the list through the API (`set_technical_accounts`); `run.sh` no longer sets `TEAM_ANALYTICS_TECHNICAL_ACCOUNTS`.
- A new `run.sh check-settings`.
- The access case `removed-member` is replaced by `revoked-admin` (`access_cases.py`): an administrator taken out of the admin group is refused on its very next request, in its old session and in a fresh one.
- Browser step `page` in `fixes_browser.cjs` (`run.sh check-fixes page`): the filter bar's heights and centre line, the Settings button's height, the operations card's width sweep, the two selectors and a tooltip.

Stacks for verification use their own namespace and port (`TA_RUN_ID`, port 8491) and the work images, never the owner's stack.

**Blocked by:** 01, 05.

**Status:** resolved

- [x] On a fresh stack, `up` passes, and every figure read is made by an administrator; the access cases show owners, maintainers and other roles refused with 403 on every endpoint, including the settings.
- [x] `check-cross-org` passes in its new form.
- [x] `check-settings` passes: a non-administrator is refused on read and on write; a save moves the generation by exactly one; adding an account changes last week's figures and removing it restores them; a deleted user stays listed.
- [x] Seeding sets the technical accounts through `PUT settings`, and nothing in the stack sets the removed variable.
- [ ] Browser step `page`: every filter-bar control measures 36px on one shared centre line, and the Settings button, in the header row at the right, measures 36px.
- [x] Browser step `page`: a width sweep from 1024px to 1920px (including the width that gives a 420px card) finds no sideways scroll in the operations card and prints the other cards that scroll.
- [x] Browser step `page`: a project and an annotator are picked through the selectors, and a term's tooltip shows on hover.

## Comments

2026-11-16: Done in `213010452`, `aa8e07784`, `c3c63c837`, `c42176dbd`, `beec80281`, `4dcef34a8` and `ea7fed8dd`, with the review's fixes `07d362543`, `142fea153` (`revoked-admin`), `0b2942412`, `cfc8e4b31`, `5cce53cf3`, `c7310ce93`, `593154d91`, `4bd1dbea3`, and the fixes found by running the checks: `9f5f188eb`, `a6fa266ac`, `0bf2f41cd` (the page step) and `9a8620e96` (check-load's repeat rule). Final run on its own namespace and port 8491 with the work images: fresh `up` and second `up` exit 0, every figure read as `ta-admin`, owners, maintainers, a supervisor, workers and an outsider 403 on all five read endpoints, and the settings refused to the three accounts the settings check uses (`ta-owner`, `ta-maintainer`, `ta-worker`: 24 requests 403, 4 signed out 401); `check-cross-org` passed in its new form; the settings check, run inside `up`, passed every part (the generation +1 on every save, a retroactive change and its removal, a deleted user kept); the seed sets the list through the settings API (`stack_api.py`'s seed) and the server's log had no warning about the removed variable; `check-fixes page` passed whole (the width sweep of 127 widths with no sideways scroll in the operations card and the other cards printed; both selectors picked a value; 13 tooltips shown on hover and focus). Record: `docs/evidence/2026-11-16-open-lines-closed-and-admin-settings.md`.

Left unticked, the filter-bar criterion, only partly met: all 5 controls and Settings measured 36 px, but the controls share one centre line only at 1400 and 1920 px; at 1024 px the bar wraps onto two lines (centres 148 and 192 px), which the step reports and accepts.
