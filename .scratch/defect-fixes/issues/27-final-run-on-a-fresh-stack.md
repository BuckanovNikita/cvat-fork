# 27: Final run on a fresh stack

**What to build:** One run on a stack built from nothing shows the fixes of this spec and replaces the evidence that rested on stand-ins and in-place upgrades. See "Testing Decisions" in the spec (`../spec.md`).

**Blocked by:** 01 to 26 (every ticket before this one).

**Status:** resolved

- [x] `up`, `up`, `down` from an empty namespace, with all three images built from the integrated branch, passes and leaves nothing behind.
- [x] The full service suite passes on both ClickHouse versions; the three fast frontend suites and the gate pass.
- [x] Each fix is seen on the stack along the path that failed: a direct call for an unprocessed period (the period made unprocessed by a marker event while the refresh lease was held); status as a maintainer and as an administrator; the technical account's project in the details table; the cutover read at once after a restart of the service with its stored cutover emptied; a redo and two group moves (a selection moved by its label, a pasted selection dragged) made in the browser and read back from the events table; a frame-navigation key held for four seconds, counted once per frame shown, nothing at the last frame or for the slider (the browser held back any request for frame data; the final run made none during the hold, and a probe in which four were held back saw the frame move on every key-down all the same).
- [ ] A repeat of a held frame-navigation key that arrives while the frame change still waits counts nothing; and CVAT's own drag of a grabbed member of a group carries the grabbed mark: neither was reached in the browser (the frame change does not wait for the frame's data; no gesture produced a grabbed drag). Shown by the logging suite only.
- [x] The split bars and the definitions were measured and looked at in a browser on the stack at 1400 px and at 400 px, and compared with the prototype's source and the design text.
- [ ] The prototype rendered beside the page: not done (its sources need the design canvas's runtime, which is not in the repository).
- [x] The number of sessions that reached the one-day limit is recorded.
- [x] The fork specification states the limits that remain: counts lost on tab close; tags and objects made with the interactive AI or OpenCV tools are not counted; a session is at most a day long; in 3D jobs only sessions and working time are measured; a shape-tagged event with a wrongly early date. Limits that were fixed are gone from it.
- [x] The ten acceptance criteria of the Team Analytics tickets that were ticked on a reading are restated in their tickets as what was shown, and ticked again only where this run shows them.
- [x] One dated evidence file separates live outcomes from tests with supplied boundaries and lists what remains unverified.
- [x] The integrated branch gets an independent review, with the access rules and the policies reviewed on their own. Findings are fixed or recorded.
- [x] The stack is torn down unless the owner asks to keep it.

## Comments

2026-11-15: Part one done without a stack; nothing is ticked. `run.sh check-fixes` (`fixes_run.py`, `fixes_browser.cjs`) adds the fixes along the path that failed, the look at 1400 and 400 px and the count of sessions at the one-day limit; it has not run against a stack. The fork specification states the remaining limits (criterion 6 is ticked only after the run, with the rest). The plan of the run, its coverage, and what each of the ten criteria ticked on a reading must show before a tick, with its restated wording, are in `docs/evidence/2026-11-15-final-run-on-a-fresh-stack.md`.

2026-11-15: Part two run; evidence in `docs/evidence/2026-11-15-final-run-on-a-fresh-stack.md`. Images built from the integrated branch at `b8521e3f`. The first fresh `up` passed on its second attempt: the first stopped at a 429 from CVAT's sign-in throttle after the volume's hundred sign-ins (fixed in the launcher, `d61dd877`; the namespace was deleted and `up` repeated from an empty one). The second `up` passed on its second attempt: the first failed the seed check on a stack holding the volume (fixed, `abb02a10`). `run.sh check-fixes` needed changes to five of its steps on first contact with the stack (commits `c61ec366`, `674ab90c`); it then passed end to end. Two criteria were split under the accepted ticking rule: criterion 3's two paths the browser could not reach, and criterion 4's side-by-side rendering. Criterion 9 is left unticked: the reviews named in the evidence cover the branch up to `de181cd7` and the three follow-ups; whether the last follow-up (`b8521e3f`) and this ticket's stack tooling get an independent review is the orchestrator's call. `down` left nothing behind.

2026-11-15: The gate: `prek run --all-files` with hook skips cleared passed on `20d9e45b` (ESLint, stylelint, the type check, ruff, both policy tests, the three fast frontend suites); the integration branch at `b8521e3f` is merged.

2026-11-15 (last): The review criterion is ticked. The policies and the access rules were each reviewed on their own, the other parts in turn, and the whole branch by a code review; a fresh reviewer then covered what came after the last of those (`de181cd7..02e5423d`: the answers to the last review, this run's tooling, and the answers to the security review), in two passes. Its seven low findings on this run's tooling are fixed or recorded, the fixed ones shown on a live stack (`docs/evidence/2026-11-15-integrated-branch-review.md`, the last two sections); the security review is ticket 28. Resolved on `feat/team-analytics-page` by merges `ba33aeb4` and `02e5423d`, with two lines left unticked on purpose: the two paths a browser did not reach, and the prototype rendered beside the page. Both are listed for the owner as not shown.
