# 21: Frame navigation counts frames moved

**What to build:** A frame-navigation hotkey counts as a hotkey action only when the frame actually changes. Today every invocation counts, so holding the key on a slow frame inflates the hotkey share. See Hotkey action in `GLOSSARY.md` and "UI logging" in the spec (`../spec.md`). Counting nothing at the first or last frame is the spec's reading of the glossary, not a separate answer from the owner.

**Blocked by:** 05 (First lint run on the fork's UI code).

**Status:** resolved

- [x] Test first, at the boundary where the UI sends events: a frame-navigation hotkey pressed or held while a frame is loading adds nothing to the summary. This fails today.
- [x] One pressed at the first or last frame, or while navigation is blocked, adds nothing.
- [x] Each frame change that a hotkey causes counts one hotkey action under that action's name.
- [x] A frame change made with the mouse does not become a hotkey action.
- [x] Every other held key is still one hotkey action, and mouse counting is unchanged.
- [x] CVAT's own logging is unchanged, and a failure in the counting never reaches the code that called it.

## Comments

2026-11-14: Done on `ticket/21-frame-nav`; evidence in `docs/evidence/2026-11-14-frame-navigation-hotkeys.md`. All criteria were seen at seam 2 (`verify/team-analytics-logging/frame-navigation.test.cjs`), with no browser. Limits: the third criterion was driven for next and previous frame; that the other eight navigation names reach the same frame change was read. For the fourth, the slider's change on mousedown and the `mousedown` listener in `cvat-app.tsx` are not run by a test; ticket 27's browser run should check them (see the evidence).

2026-11-14: Resolved by merge `1f97c696` into `feat/team-analytics-page`; evidence in `docs/evidence/2026-11-14-frame-navigation-hotkeys.md`. On the merged tree: ESLint and the type check exit 0, seam 2 63 pass and seam 3 209 pass with 0 skipped, task progress 20 pass and 1 skipped. The browser checks named above go to ticket 27.

2026-11-15: An independent review of tickets 19, 21 and 22 found two defects here: a navigation key that moved nothing could be credited with a later frame change, and a hook was untested. Both are fixed on `fix/logging-review`. The review, its five findings and what was done about each are in `docs/evidence/2026-11-14-frame-navigation-hotkeys.md` ("Independent review, 2026-11-15" and "Review follow-up, 2026-11-15").
- A key now owns only a frame change that starts in its own turn (its handler and the microtasks after it). A playback step, the frame number field or a search already running is no longer credited to a key that moved nothing. The reviewer's two probes, a search key that finds nothing during playback, and a search already running were all seen to fail before the fix, and they pass with it. A search key and a key pressed while the search's frame loads each count their own.
- The `mousedown` listener is gone. The logging attaches its own key and click listeners through `listenForInput(window)`, which `cvat-app.tsx` calls once. A test mounts the real application component, and dropping that call was seen to fail it.
- Known limit, now in the fork specification: a key pressed while cvat-core is fetching or saving the frame meta starts its change after its turn and counts nothing. This happens during cvat-core's hourly reload during a frame load, or during a save after frames were deleted or restored.
- On the branch head after merging `feat/team-analytics-page` (`bd1d00d9`), seam 2 passed 77 with 0 skipped and seam 3 passed 223 with 0 skipped. ESLint and the type check passed on the UI files touched.
- For ticket 27's final run, in addition to the held key on a slow frame: while playback runs, press a search key that finds nothing (or a key-frame key with no further key frame), and see no hotkey action for the playback steps after it. Press a search key that finds a frame and see one `SEARCH_FORWARD`.
- 2026-11-15: The review follow-up of tickets 19, 21 and 22 (`fix/logging-review`) merged into `feat/team-analytics-page` as `ae6bbfca`, with no conflict. On the merged tree the logging suite passed 77 and the page suite 223, each with 0 failed and 0 skipped, and the skip-gate grep found nothing. The status is unchanged.

2026-11-15: The code review of the integrated branch (finding 5, recorded in `docs/evidence/2026-11-15-integrated-branch-review.md`) said that an extra await in a handler's chain loses the press. It is partly true, and no code was changed. Measured at seam 2 with a probe that delays the search key's annotation search: up to 40 extra awaits the key is still counted; with 120 extra awaits, or one timer, it is not. The fork specification's limit now says this: a few more awaits change nothing, and a chain past the 100-microtask turn, or one that waits outside the microtask queue, counts nothing. The deterministic remedy needs hooks in upstream handlers.
