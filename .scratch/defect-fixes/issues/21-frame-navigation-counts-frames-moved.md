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
