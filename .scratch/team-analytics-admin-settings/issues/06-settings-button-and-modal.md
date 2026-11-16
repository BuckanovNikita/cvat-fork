# 06: Settings button and modal

**What to build:** A "Settings" button in the page header opens "Team Analytics settings", where an administrator edits the Technical accounts list (items 4 and 5 of the spec).

- The header of `team-analytics-view.tsx` becomes a row with a 36px "Settings" button with a gear icon at the right.
- A new `settings-modal.tsx` (antd `Modal`) shows the list (a deleted CVAT user reads "deleted account, id N"), a remote-search picker in the pattern of the jobs page's distribute-jobs modal, pointed at the `settings/users` action of ticket 05, and one sentence saying that a change applies to all past periods on the next page load. Saving sends the whole list with `PUT settings`.
- `service.ts` gains `requestSettings` beside `requestService`, through `core.server.request`, including `PUT`; tests replace it as they replace `requestService`.

**Blocked by:** 01, 05.

**Status:** resolved

- [x] New `verify/team-analytics-page/settings.test.cjs`: the Settings button opens the modal, which lists the accounts from `GET settings`, including a deleted one as "deleted account, id N".
- [x] Typing in the picker calls `settings/users` with the text, and choosing a user adds it to the list shown.
- [x] Saving sends `PUT settings` with the whole list of user ids; after a successful save the modal closes and the page reloads its data; a 400 answer shows its `detail` sentence without closing the modal.
- [x] Removing an account (including a deleted one) and saving sends the list without it.
- [x] The modal states that a change applies to all past periods on the next page load.
- [ ] On the live stack (ticket 08): the Settings button is 36px tall in the header row at the right (it is not on the filter row's centre line), and the modal saves a change that the next page load reflects.

## Comments

2026-11-16: Done in `bfb4230f1` and `ba8ddb396`, with the review's fixes `09ac22a85` (the dialog closes on a refusal), `c9170ac56` (a save in flight, listed users shown disabled, a failed search), `a741d9d4e` (a double click on Save in one go) and `3b682f584` (a save is waited for at most 30 s). Shown: `settings.test.cjs` (the list with "deleted account, id 40", the search, a 400's sentence, removing and adding then Save sending the whole list, the dialog closing and the figures reloading, the sentence about past periods) passed in the page suite through the wrapper (fresh clone at `0bf2f41cd`). On the stack (`check-fixes page`, final run): Settings 36 px at the header's right end; the dialog listed `ta-bot`, offered it disabled, found a user of another organization; Cancel sent no PUT; Save of the unchanged list sent one PUT and closed with no error. Record: `docs/evidence/2026-11-16-open-lines-closed-and-admin-settings.md`.

Left unticked, the live criterion, only partly met: the browser step saved an unchanged list, so a change saved through the dialog and seen on the next page load was not shown in a browser; that a saved change applies to the figures on the next read was shown through the API (the settings check's `retroactive` part).
