# 08: Stack checks on the new rules

**What to build:** The stack checks under `verify/team-analytics-stack/` follow the new access rule and the new home of the Technical accounts list. Nearly every check reads figures as an owner or a maintainer today.

- One `reader(org)` helper in `stack_api.py`; every figure read in `final_run.py`, `fixes_run.py`, `acceptance.py`, `access_cases.py`, `org_creation.py` and in `final_browser.cjs`, `fixes_browser.cjs` and `browser_check.cjs` goes through an administrator. Owners keep creating projects and tasks.
- `check-cross-org` becomes: an administrator's answer for one organization is not served for another organization or for Instance scope.
- Seeding sets the list through the API (`set_technical_accounts`); `run.sh` no longer sets `TEAM_ANALYTICS_TECHNICAL_ACCOUNTS`.
- A new `run.sh check-settings`.
- Browser steps in `fixes_browser.cjs`: the filter bar's heights and centre line, the operations card's width sweep, the two selectors and a tooltip.

Stacks for verification use their own namespace and port (`TA_RUN_ID`, port 8491) and the work images, never the owner's stack.

**Blocked by:** 01, 05.

**Status:** ready-for-agent

- [ ] On a fresh stack, `up` passes, and every figure read is made by an administrator; the access cases show owners, maintainers and other roles refused with 403 on every endpoint, including the settings.
- [ ] `check-cross-org` passes in its new form.
- [ ] `check-settings` passes: a non-administrator is refused on read and on write; a save moves the generation by exactly one; adding an account changes last week's figures and removing it restores them; a deleted user stays listed.
- [ ] Seeding sets the technical accounts through `PUT settings`, and nothing in the stack sets the removed variable.
- [ ] Browser step: every filter-bar control and the Settings button measure 36px with one shared centre line.
- [ ] Browser step: a width sweep from 1024px to 1920px (including the width that gives a 420px card) finds no sideways scroll in the operations card and prints the other cards that scroll.
- [ ] Browser step: a project and an annotator are picked through the selectors, and a term's tooltip shows on hover.

## Comments
