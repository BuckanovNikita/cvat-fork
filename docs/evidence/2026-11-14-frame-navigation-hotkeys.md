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
  CVAT's own click and user-activity events, is unchanged. (Replaced on
  2026-11-15 by one `listenForInput(window)` call, below.)
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
  by lint and the type check only (gone on 2026-11-15, below). That antd's
  `Slider` changes the frame on mousedown is read, not observed.
- A pending hotkey that moved nothing lasts until the next mouse press, click or
  hotkey. A frame change that starts in between without any of them (none was
  found by reading) would be credited to it. (The review of 2026-11-15 found
  such changes; the pending hotkey was replaced, see below.)
- A late repeated request that finishes after a newer frame is shown moves the
  frame back. That is a real frame change and counts.

## For the browser run (ticket 27)

Hold a next-frame key on a slow frame. Compare the summary's `NEXT_FRAME` count
with the frames actually advanced, which CVAT's `change:frame` events show. Then
press the key at the last frame and drag the player slider back: that should add
no hotkey action. Watch for the frame jumping back when held requests finish out
of order. A jump back is a real frame change and counts.

## Independent review, 2026-11-15

A fresh agent that had not written the changes reviewed the counting changes of
tickets 19, 21 and 22 after their merges (`ff5dda4`, `1f97c696`, `50895e77`),
given the owner's documents and not the implementers' conclusions. It read and
probed the tree at `3dc1a7bc` and changed no tracked file.

Verdict: the operations rule holds. No sequence it found counts a creation, an
alignment or their time twice, loses one, or makes time negative, and the
service tests show it through the read interface. The defects were in frame
navigation and in how the fixes would survive upstream changes and stored data.

What the reviewer ran: 72 service tests on a copy of the merged tree (0
failures) and seven service probes (a group record and its grabbed drag either
side of a window or hour edge, a redo across a window edge, a duplicated group
record, and others); the UI logging suite (70 pass, 0 skipped); two probes on
this suite's harness, driving the real top bar, `changeFrameAsync` and the
logging module.

Findings, and what was done about each (branch `fix/logging-review`):

1. **A navigation key that moves nothing could be credited with a later frame
   change** (low to medium, reproduced). The key stayed pending until a mouse
   press, a click or another hotkey, so the next playback step, a frame typed
   into the frame number field, or a search already running was counted under
   its name. Fixed: the key now owns only a frame change that starts in its own
   turn (its handler and the microtasks after it, bounded by
   `TURN_MICROTASKS`); the mouse press and click no longer end anything.
   The reviewer's two probes and the opposite cases are tests in
   `verify/team-analytics-logging/frame-navigation.test.cjs`, and the search
   keys now run through the real `searchAnnotationsAsync`.
2. **Upstream changes could break the counting with every suite green**
   (medium, upkeep). The `mousedown` listener line in `cvat-app.tsx` was run by
   no test. Fixed: the logging attaches its own window listeners with
   `listenForInput(window)`, which `cvat-app.tsx` calls once; the `mousedown`
   listener is gone (finding 1's fix needs it no more) and the call inside
   upstream's listener was removed, so that listener is upstream's again.
   `verify/team-analytics-logging/app-listeners.test.cjs` mounts the real
   application component over a jsdom window; removing the call was seen to
   fail it, and removing the click or the key listener from the module was seen
   to fail tests. The two orders no suite can see (the canvas's group notice
   then grabbed drag in one task; frames shown only through `changeFrameAsync`,
   reached from a handler without a later task) are now in the fork
   specification's list of upstream behaviour the fork depends on and in
   `docs/upstream-upgrade.md` (section 4, Team Analytics), each with what
   breaks and the stack step that catches it. The integration map now names
   both `changeFrameAsync` hooks, the `cvat-app.tsx` call and the group-moved
   hook.
3. **The account of stored hours was incomplete** (low, documents). Added to the
   fork specification: hotkey counts recorded before ticket 21, or by a browser
   still on an old bundle, stay as counted and cannot be recounted; and under
   the old group rule the grabbed drag continues a run, so a group drag of two
   boxes and then a drag of the grabbed box is stored as 2 under the old rule
   and 3 under the new.
4. **A refused group record with the mark already set loses the gesture's
   objects** (low, unlikely; no real path found). Recorded as a known limit in
   the fork specification and in ticket 22. The order of the two records is
   unchanged.
5. **Two small effects on CVAT's own logging** (informational). Recorded in the
   fork specification for the owner: a selection-box move adds one
   `drag:object` where CVAT logged none, which ends the logger's merging of
   frame changes either side of it and shows in CVAT's own analytics; nothing
   is removed, reordered or delayed. Comment in ticket 22.

What held, by the reviewer: the operations rule after both changes (above);
group logging (the group always holds the grabbed shape, the logging is guarded
and does not wait, a failure falls back to the old single drag, 3D jobs send
nothing); frame navigation for held keys while loading, the first and last
frame, blocked navigation, the mouse buttons, the slider, failed changes and
out-of-order completion.

Not checked by the reviewer: a real browser (ticket 27), the second ClickHouse
image, the full service suite (run separately by the orchestrator at that
commit).

## Review follow-up, 2026-11-15

### Observed at seam 2

Seen to fail before the fix, each with one count under the key's name where
nothing was expected:

| Case | Failure seen |
| --- | --- |
| A key while navigation is blocked, then a playback step | `NEXT_FRAME: 1` |
| A search key that finds nothing, then two playback steps | `SEARCH_FORWARD: 1` |
| A next-frame key at the last frame, then a frame entered in the frame number field | `NEXT_FRAME: 1` |
| A search started with the mouse and still running, a blocked key, then the search's frame change | `NEXT_FRAME: 1` |

Written with the fix, a pin that also passed before it: a search key counts the
frame it found, and a key pressed while that frame loads counts its own
(`SEARCH_FORWARD: 1, PREV_FRAME: 1`). The reviewer's "second key during a slow search" cannot happen
as described in the browser: cvat-core's annotation search is synchronous inside
a resolved promise, so nothing runs between the key and the search's change.
The case that can happen, a second key while the search's frame loads, is the
test above. Every earlier frame-navigation test passes with its assertions
unchanged, the slider test among them, now without any `mousedown` listener in
the harness.

The harness's window listeners are now the module's own (`listenForInput`). A
new test in `keyboard-mouse.test.cjs`, a key press that is no shortcut writing a
due summary, was seen to fail with the key listener removed from the module.

### Read, and measured with a replica

The turn bound: from a shortcut handler to the start of `changeFrameAsync`, the
deepest chain (a filtered next-frame key: the frame search, then
`searchAnnotationsAsync`'s annotation search) took 9 microtasks with the real
cvat-core plugin wrapper (`plugins.ts`, loaded through the harness) and the
session wrappers and `findFrame`'s await copied in shape, with no plugins and
with three registered. The replica was a throwaway script run once and not
kept. The harness transpiles to ES2020 with native `async`; the UI bundle keeps
native `async` too (`tsconfig.json` targets ESNext, and Babel's preset-env
targets browsers that all have it), so the count should carry over, though it
was not measured in the bundle. `TURN_MICROTASKS` is 100. A frame search waits for the
server only while cvat-core fetches or saves the frame meta (`getFramesMeta`
reloading it, `saveMeta`); a key pressed then counts nothing for its change.
This limit is in the fork specification.

### Checks at the head of the branch

Seam 2 `node --test verify/team_analytics_logging.cjs`, seam 3
`node --test verify/team_analytics_page.cjs` and the check pipeline
(`prek run --all-files`) are recorded with their results in ticket 21's
comments.

### Not verified

- A real browser. Ticket 27's final run holds a navigation key on a slow frame;
  for this follow-up it should also press a search key that finds nothing (or
  a key-frame key with no further key frame) while playback runs, and see no
  hotkey action for the playback steps after it; and press a search key that
  finds a frame and see one.
- That no plugin a deployment registers adds a wait to the frame or annotation
  search (cvat-core's plugin wrapper awaits a plugin's `enter`).
- Order against CVAT's own records: the logging's listeners are now attached
  before upstream's, so a summary that falls due at a click is handed to the
  logger just before CVAT's click record for it, where it used to follow it.
  The harnesses stub CVAT's own event recorder, so no test sees this.
- For the owner: the task asked that a second key pressed during a slow search
  not take the count from the search. Under the own-turn rule a search that
  answers in a later task counts nothing for its own change, with or without a
  second key; stock cvat-core's searches answer within the turn, so this
  happens only in the frame meta case above or with a plugin that waits. Lifting
  it would need hooks around the searches in upstream files.
- The canvas's dispatch order and the single frame-change path, beyond reading
  the target release (see the fork specification).
