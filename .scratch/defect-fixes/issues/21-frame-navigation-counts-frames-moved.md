# 21: Frame navigation counts frames moved

**What to build:** A frame-navigation hotkey counts as a hotkey action only when the frame actually changes. Today every invocation counts, so holding the key on a slow frame inflates the hotkey share. See Hotkey action in `GLOSSARY.md` and "UI logging" in the spec (`../spec.md`). Counting nothing at the first or last frame is the spec's reading of the glossary, not a separate answer from the owner.

**Blocked by:** 05 (First lint run on the fork's UI code).

**Status:** ready-for-agent

- [ ] Test first, at the boundary where the UI sends events: a frame-navigation hotkey pressed or held while a frame is loading adds nothing to the summary. This fails today.
- [ ] One pressed at the first or last frame, or while navigation is blocked, adds nothing.
- [ ] Each frame change that a hotkey causes counts one hotkey action under that action's name.
- [ ] A frame change made with the mouse does not become a hotkey action.
- [ ] Every other held key is still one hotkey action, and mouse counting is unchanged.
- [ ] CVAT's own logging is unchanged, and a failure in the counting never reaches the code that called it.
