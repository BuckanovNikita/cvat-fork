# Frame navigation counts frames moved, 2026-11-14

Ticket 21 of the defect fixes
(`.scratch/defect-fixes/issues/21-frame-navigation-counts-frames-moved.md`).

Every invocation of a frame-navigation hotkey counted as a hotkey action. While a
frame loads, the top bar still holds the old frame number, so each repeat of a
held key asks again for the same next frame, and each repeat counted. At the
first or last frame, or with navigation blocked, the press moved nothing and
still counted.

## Changed

- `cvat/cvat-ui/src/utils/team-analytics-logging/input-summary.ts`: a
  frame-navigation hotkey is no longer counted when it is pressed. It is kept as
  pending. `frameRequested()` hands it to the frame change that starts next.
  `frameShown(hotkey, from, to)` counts it when that change shows a frame other
  than the one last shown. A mouse button press, a click or another hotkey ends
  a pending one. Every other hotkey and mouse rule is as before.
- `cvat/cvat-ui/src/actions/annotation-actions.ts` (`changeFrameAsync`): one call
  at the start (`frameRequested`) and one just before `CHANGE_FRAME_SUCCESS`
  (`frameShown`), plus the import. CVAT's frame-change event is untouched.
- `cvat/cvat-ui/src/components/cvat-app.tsx`: one capture `mousedown` listener
  that goes only to the logging module. The upstream listener, which records
  CVAT's own click and user-activity events, is unchanged.
- All ten names in `FRAME_NAVIGATION_ACTIONS` reach `changeFrameAsync` (read):
  next/previous frame, forward/backward and chapter navigation through the top
  bar, search forward/backward through `searchAnnotationsAsync`, and the key-frame
  shortcuts through the objects list and the attribute annotation sidebar.

## Observed at seam 2 (the events the UI logging sends)

`verify/team-analytics-logging/frame-navigation.test.cjs` drives a key through
the shortcut dispatcher (`utils/mousetrap-react.tsx`), the real top bar
container and the real `changeFrameAsync`, over a store that shows the frame it
is given. Frames load only when the test lets them. The batch the real cvat-core
logger would POST comes out. These are supplied boundaries: no browser and no
server.

Seen to fail before the fix:

| Case | Failure seen |
| --- | --- |
| A key pressed and held for nine repeats while the next frame loads | `NEXT_FRAME: 10`, not 1 |
| A key at the last frame, at the first frame, and with navigation blocked | `NEXT_FRAME: 3, PREV_FRAME: 2`, not nothing |
| A key pressed while a mouse-started frame change loads | `NEXT_FRAME: 1`, not nothing |
| A key at the last frame, then the player slider, which changes the frame on mousedown | `NEXT_FRAME: 1`, not nothing (seen after the first commit, fixed in the second) |

Written with the fix and passing: a held key on frames that load in time
counts each frame moved; another held key is still one action, and CVAT's own
frame-change events are as before (3 -> 4 twice, then 4 -> 5, compressed by the
logger into `[3 -> 4, 1]` and `[3 -> 5, 2]`; this list was also seen before the
fix); a failure in the counting never reaches the shortcut or the frame change.
The test for a failure at the frame shown was checked by removing the guard
around `frameShown` once; it then failed, and the guard was restored.

Three existing tests used the next-frame key as a stand-in for any hotkey with no
frame change behind it. They now use undo, and the old "every invocation counts"
test now says that a navigation key that moves no frame counts nothing.

Checks at the head of the branch: seam 2 `node --test verify/team_analytics_logging.cjs`
62 pass, 0 skipped; `verify/team_analytics_page.cjs` 207 pass; `verify/task_progress.cjs`
20 pass, 1 skipped (the optional browser check). ESLint (`--max-warnings 0`) on the
four UI files touched and the UI type check pass in this worktree. The type check
read the workspace packages from the main checkout through the linked
`node_modules`.

## Not verified

- No browser run. The `mousedown` listener in `cvat-app.tsx` is not run by the
  seam test, which wires its own listeners as `cvat-app.tsx` does. It is checked
  by lint and the type check only. That antd's `Slider` changes the frame on
  mousedown is read, not observed.
- A pending hotkey that moved nothing lasts until the next mouse press, click or
  hotkey. A frame change that starts in between without any of them (none was
  found by reading) would be credited to it.
- A late repeated request that finishes after a newer frame is shown moves the
  frame back. That is a real frame change and counts.

## For the browser run (ticket 27)

Hold a next-frame key on a slow frame. Compare the summary's `NEXT_FRAME` count
with the frames actually advanced, which CVAT's `change:frame` events show. Then
press the key at the last frame and drag the player slider back: that should add
no hotkey action. Watch for the frame jumping back when held requests finish out
of order. A jump back is a real frame change and counts.
