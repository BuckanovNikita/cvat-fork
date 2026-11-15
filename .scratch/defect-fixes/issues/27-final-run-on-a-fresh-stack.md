# 27: Final run on a fresh stack

**What to build:** One run on a stack built from nothing shows the fixes of this spec and replaces the evidence that rested on stand-ins and in-place upgrades. See "Testing Decisions" in the spec (`../spec.md`).

**Blocked by:** 01 to 26 (every ticket before this one).

**Status:** ready-for-agent

- [ ] `up`, `up`, `down` from an empty namespace, with all three images built from the integrated branch, passes and leaves nothing behind.
- [ ] The full service suite passes on both ClickHouse versions; the three fast frontend suites and the gate pass.
- [ ] Each fix is seen on the stack along the path that failed: a direct call for an unprocessed period; status as a maintainer and as an administrator; the technical account's project in the details table; the cutover read at once after an in-place upgrade; a redo and a group drag made in the browser and read back from the events table; a frame-navigation key held on a slow frame.
- [ ] The split bars and the definitions are compared with the prototype in a browser at 1400 px and at 400 px.
- [ ] The number of sessions that reached the one-day limit is recorded.
- [ ] The fork specification states the limits that remain: counts lost on tab close; tags and objects made with the interactive AI or OpenCV tools are not counted; a session is at most a day long; in 3D jobs only sessions and working time are measured; a shape-tagged event with a wrongly early date. Limits that were fixed are gone from it.
- [ ] The ten acceptance criteria of the Team Analytics tickets that were ticked on a reading are restated in their tickets as what was shown, and ticked again only where this run shows them.
- [ ] One dated evidence file separates live outcomes from tests with supplied boundaries and lists what remains unverified.
- [ ] The integrated branch gets an independent review, with the access rules and the policies reviewed on their own. Findings are fixed or recorded.
- [ ] The stack is torn down unless the owner asks to keep it.

## Comments

2026-11-15: Part one done without a stack; nothing is ticked. `run.sh check-fixes` (`fixes_run.py`, `fixes_browser.cjs`) adds the fixes along the path that failed, the look at 1400 and 400 px and the count of sessions at the one-day limit; it has not run against a stack. The fork specification states the remaining limits (criterion 6 is ticked only after the run, with the rest). The plan of the run, its coverage, and what each of the ten criteria ticked on a reading must show before a tick, with its restated wording, are in `docs/evidence/2026-11-15-final-run-on-a-fresh-stack.md`.
