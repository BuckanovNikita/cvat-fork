# 01: The legend hides the progress bar when a task has many buckets

**What was seen:** On the tasks list, a task whose jobs cover all twelve stage and state pairs shows a legend that wraps onto five lines, runs past the bottom edge of its card, and leaves no progress bar visible. A task with one bucket shows its bar as designed. Seen on 2026-11-15 on the Kubernetes test stack with the fork's UI image, in a 1400 px wide window, in the run of ticket 10 of the defect fixes (`docs/evidence/2026-11-14-task-progress-on-stack.md`, part two).

The stack's task-progress check passes on that card: it reads each segment's computed style, colour, weight and tooltip, not whether the segment is on screen.

This is outside the defect-fix spec, which only moved the check from Compose to the stack. Nothing was changed.

**Status:** needs-triage

**Open questions for triage:**

- How many buckets must the card show at once before the legend should change shape (wrap inside a taller card, shorten, move to a tooltip)?
- Should the check also look at what is visible, for a card with every bucket?

## Comments

2026-11-15: Filed by the agent that ran the defect-fix tickets, from the screenshot of ticket 10's live run. The screenshot itself was not committed.
