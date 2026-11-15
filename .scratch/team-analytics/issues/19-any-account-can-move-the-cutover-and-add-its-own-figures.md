# 19: Any account can move the instance's cutover and add figures for itself

**What was seen:** The security review of ticket 28 of the defect fixes (2026-11-15, finding 1, `docs/evidence/2026-11-15-security-review.md`) found that every figure Team Analytics shows comes from client events sent by the browser of the person it describes, and that stock CVAT accepts a client event from any authenticated account. Two things follow:

- An account with no organization and no global role can send one shape-tagged `draw:object` event dated early (the review used 1 January 2020, under a job id that does not exist). At the next daily check or start, the cutover search finds it and that hour becomes the cutover for every organization. Periods after it stop being legacy: in the review's run, an organization's October changed from "all shapes, legacy notice, 2 created" to "bounding boxes, no notice, 0 created", although two objects had been drawn. History was not disturbed.
- An account can add working time, sessions, creations, alignments, Model creations, class changes and hotkey counts for itself, at any past hour and under any project or task id, inside each organization it belongs to. It cannot write under another person's name.

How it is known: the service's half was run on its test harness (the review's probe module, two tests). The CVAT half was read in the stock server image, not run: `events.rego` lets every caller send events; the client events serializer sets the user and organization from the request and takes job, task and project ids, counts, durations, payload and time from the client.

The correction for a wrongly early event is documented (remove the event from the `events` table, then the stored cutover). The trust model is now stated in `docs/fork-specification.md` (TA-1, beside the cutover's limits). Nothing in the code was changed: any remedy overrides the owner's decision in ticket 17 of the defect fixes that the cutover is found by search and can move earlier.

**Status:** wontfix

**Open questions for triage:**

- Should the cutover search ignore events dated before a configured date (when the new UI was deployed)?
- Or should the cutover be an administrator's setting rather than found by search?
- Or does the documented correction stay the only remedy, with the trust model stated?
- Is a self-reported figure acceptable for what the page is used for, or should some figures be checked against what CVAT itself stores (for example, that a job exists and the person is assigned to it)? (Added by the implementer; the review's options are the first two.)

## Comments

2026-11-15: Filed by the implementer answering the security review of ticket 28 of the defect fixes. Waits for the owner.

2026-11-15: Closed as an accepted risk. The owner decided that Team Analytics becomes administrators-only (ticket 01 of `.scratch/team-analytics-admin-settings/`). Any authenticated account can still send events that move the cutover earlier or add figures for itself, but only administrators read the figures. The owner accepts that risk, and no remedy is built: the cutover is still found by search, and no figure is checked against what CVAT stores. The correction procedure for a wrongly early event and the trust model stay as documented in `docs/fork-specification.md` (TA-1).
