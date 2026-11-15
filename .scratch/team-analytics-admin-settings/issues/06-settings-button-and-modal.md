# 06: Settings button and modal

**What to build:** A "Settings" button in the page header opens "Team Analytics settings", where an administrator edits the Technical accounts list (items 4 and 5 of the spec).

- The header of `team-analytics-view.tsx` becomes a row with a 36px "Settings" button with a gear icon at the right.
- A new `settings-modal.tsx` (antd `Modal`) shows the list (a deleted CVAT user reads "deleted account, id N"), a remote-search picker in the pattern of the jobs page's distribute-jobs modal, pointed at the `settings/users` action of ticket 05, and one sentence saying that a change applies to all past periods on the next page load. Saving sends the whole list with `PUT settings`.
- `service.ts` gains `requestSettings` beside `requestService`, through `core.server.request`, including `PUT`; tests replace it as they replace `requestService`.

**Blocked by:** 01, 05.

**Status:** ready-for-agent

- [ ] New `verify/team-analytics-page/settings.test.cjs`: the Settings button opens the modal, which lists the accounts from `GET settings`, including a deleted one as "deleted account, id N".
- [ ] Typing in the picker calls `settings/users` with the text, and choosing a user adds it to the list shown.
- [ ] Saving sends `PUT settings` with the whole list of user ids; after a successful save the modal closes and the page reloads its data; a 400 answer shows its `detail` sentence without closing the modal.
- [ ] Removing an account (including a deleted one) and saving sends the list without it.
- [ ] The modal states that a change applies to all past periods on the next page load.
- [ ] On the live stack (ticket 08): the Settings button is 36px tall in the header row at the right (it is not on the filter row's centre line), and the modal saves a change that the next page load reflects.

## Comments
