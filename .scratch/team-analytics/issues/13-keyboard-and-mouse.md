# 13: Keyboard and mouse

**What to build:** A team lead sees who drives the tool from the keyboard and who with the mouse, which hotkeys are used, and for each operation how it was started. CVAT records none of this today, so the UI starts counting it. See Hotkey action, Mouse action and Hotkey share in `GLOSSARY.md`, the spec (`../spec.md`) and ADR 0002.

**Blocked by:** 09 (Bounding boxes).

**Status:** resolved

- [x] A hotkey action is counted for each use of a shortcut inside a job, under the name of what the shortcut does, so a remapped key is the same action.
- [x] On the stack, a next-frame key held for four seconds counted one hotkey action for each frame it showed, and nothing for a press at the last frame or for a press on the slider. The frame change did not wait for the frame's data, so no repeat arrived while a change was waiting.
- [ ] A held key other than frame navigation counts once, and a repeat that arrives while a frame change waits counts nothing: shown by the logging suite only.
- [x] A mouse action is counted for each click on a button, menu or sidebar control inside a job; clicks on the canvas are counted apart and are not mouse actions.
- [x] Counts are kept in the browser and sent as one summary record at most once a minute, inside an event type the stock server accepts, with the job's project, task and job.
- [x] A summary record is written when the job is closed through the UI and leaves with the closing save (seen on the stack, twice).
- [ ] Otherwise a summary is written only at a moment when the person is active, never on a timer alone: shown by the logging suite only. Counts since the last summary are lost when the tab is closed (fork specification).
- [x] No event is sent for each hotkey action, so the server's compression of frame changes is unaffected.
- [x] Creation, class change and deletion events carry the input method that started them: an action begun with a hotkey and finished with the mouse is a hotkey start.
- [x] The page shows hotkey actions, mouse actions and hotkey share for the scope.
- [x] The page lists the seven most used hotkeys by action with their key, and one line with the count and total of the rest.
- [x] The operations table shows, for creation, class change and deletion, the split between hotkey and mouse starts; alignment is marked as mouse only.
- [x] For a legacy period the card says that hotkey use was not recorded.
- [x] A failure inside the counting never affects the shortcut or the click.

## Comments

2026-11-14: Resolved on `feat/team-analytics-page` by merge `407bb8e`. Review fixes that followed are in merge `401576e`. Live results, review outcomes and what remains unverified: `docs/evidence/2026-11-14-team-analytics-final-run.md`.

2026-11-14: Notes on two criteria. Frame navigation counts every invocation of the shortcut handler, auto-repeats included (the spec's wording), which can differ from "every frame moved" when a repeat arrives while a frame is loading. A summary is written when the job is closed through the UI; counts since the last summary are lost when the tab is closed, which is recorded as a known limitation in `docs/fork-specification.md`.

2026-11-15: Ticket 27 of the defect fixes restated two criteria ticked on a reading (decisions ledger, V11) and split each: the part the fresh stack showed is ticked, the part only the logging suite shows is not. Original wording: "A held key counts once, except for frame navigation, where every frame moved counts."; "A summary record is written only at a moment when the person is active, and when the job is closed; never on a timer alone." Evidence: `docs/evidence/2026-11-15-final-run-on-a-fresh-stack.md`.
