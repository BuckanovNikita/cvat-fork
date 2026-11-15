# 18: A short refresh window leaves no hour falsely processed

**What to build:** With a refresh window shorter than a day, today's earlier hours are either computed or reported as not processed. Today they count as processed without anyone having computed them. See Processed history in `GLOSSARY.md` and "Service: refresh" in the spec (`../spec.md`).

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Test first, through the service's read interface: with a one-hour window, an event from earlier today, before the window, is either in the figures or its period reads as not processed. This fails today.
- [x] With the default window nothing changes: the same hours are computed and no extra work is done.
- [x] The existing tests that set a one-hour window to exercise the edge between two refreshes still pass; short windows stay possible.
- [x] History is still processed newest first, and the daily recount is unchanged.
- [x] The fork specification no longer lists this as a known limit.

## Comments

2026-11-14: Done on branch `ticket/18-short-window`: `167598c` (the tests), `e6eeebc` and `996e486` (the fix). Everything observed, and what was not verified, is in `docs/evidence/2026-11-14-short-refresh-window.md`.

What the service does now. While hours of today lie before the latest ten-minute refresh and have not been computed since they left the window, today is the newest day of history: it reads as not processed, and the history step computes those hours before any older day. It records how far it got in a new table, `history_today`. When the window moves on by an hour, the step computes that hour once more, which counts the work of the hour's last minutes. A window of a day or longer never leaves such hours.

How each criterion was shown (seam 1, the modules named in the evidence file; the whole suite was not run, by instruction, and is left for the integration branch):

1. On `e1d92b8` with only the new tests, the four `ShortWindowTest` tests of `tests.test_history` failed: the week read as processed while the event from 10:00 was in no figure. They pass with the fix.
2. `FillTest.test_with_the_default_window_today_takes_no_step_of_its_own` passes before and after the fix (nine working steps, then waiting), and `FillTest.test_history_is_processed_one_day_at_a_time_most_recent_first` passes unchanged.
3. `AlignmentWindowTest` and `RedoAcrossWindowEdgeTest` pass unchanged, and still pass after ticket 19 changed the second (run on the merge `55c8de0c`).
4. The new order test puts today's hours first and then the days before, most recent first. `History.check` and `control/history_changed_days.sql` are not touched, and the tests of `LateEventTest` and `LateEventInASessionTest` pass.
5. No edit was needed. The fork specification did not list this limit: not at `e1d92b8`, not after merging the integration branch at `fabc1cb`, and not at any point of the file's history. Its two known limits are about the stored cutover and the input summary.

Three things a reader should know:

- An event that reaches ClickHouse after the history step has computed its hour is counted when its day is computed as a whole, after midnight. Until then its period reads as processed without it. The spec asks for these hours to be computed, which they are; it does not ask for a recount within the day.
- For the moment between a refresh that moved the window and the history step that follows, every period reads as not processed.
- With a one-hour window, a test that only calls `stack.refresh()` never runs the history step, so its periods read `processed: false`. `AlignmentWindowTest` and `RedoAcrossWindowEdgeTest` do that and read figures; they pass today because figures are still returned for such a period. Ticket 14 removes them. It then has to make these two tests call `self.stack.service.step()` until it returns a wait of a second or more before they read. The edge they exercise stays the same.

For the merge: ticket 17 works in `team_analytics/history.py` too. The new tests and the first `FillTest` test count the service's steps, with the daily check as the step after history; a ticket that adds a step changes those counts.

2026-11-14: Merged into `feat/team-analytics-page` as `2fc75b4d`. On the merged tree, seam 1 `tests.test_history tests.test_status tests.test_details_table` ran 52 tests, OK. Evidence: `docs/evidence/2026-11-14-short-refresh-window.md`.

2026-11-14: The independent review of tickets 17, 18 and 20 (recorded in `docs/evidence/2026-11-14-refresh-lease-two-minutes.md`, "Independent review") found the two behaviours this ticket disclosed missing from the fork specification, and the header of `schema/041_history_today.sql` wrong about replicas whose clocks straddle midnight. The follow-up on branch `fix/refresh-review` adds both behaviours to the fork specification's known limits, corrects the header, and adds two tests from the reviewer's probes: midnight with a one-hour window, and two replicas whose clocks straddle midnight. The behaviour did not change.

2026-11-15: The code review of the integrated branch (recorded in `docs/evidence/2026-11-15-integrated-branch-review.md`) found three things in this ticket's work, all on branch `fix/code-review`. Finding 1, fixed: with a short window, each hour that left the window made every period, the day count and the percentage read as nothing processed until the next history step. The history state now keeps the newest missing earlier day apart from where today's waiting hours begin. A period or trend bucket that ends before those hours stays processed, the percentage keeps the days before today, and a period that holds them still reads as not processed (story 6). The new test `ShortWindowTest.test_an_hour_waiting_for_the_history_step_leaves_the_days_before_today_processed` failed first, at 0 of 25 days. This ticket's tests and the midnight and two-clock tests pass unchanged. The same test also pins that a trend candidate's working time takes nothing from the unprocessed current bucket meanwhile; that assertion failed first at 7 minutes, against the fix's first form, and passes since `fecba133`. What still flips for that hour (status offers no month and counts no complete week) is written into the fork specification's short-window limit. Finding 6, fixed: the history step ran its due query twice. That query is cheap, though: over a million raw events it read 5 rows in about 8 ms, since the count and the earliest timestamp come from table metadata. It now runs once, under the lease, and the step counts are unchanged. Finding 8, recorded: the today logic lives in both `read/history_state.sql` and `control/history_next_day.sql`, and the SQL loader cannot share a fragment. Each file now names the other and the parts that must stay in step. `ShortWindowTest.test_an_hour_that_left_the_window_is_computed_again_before_it_reads_as_processed` pins their agreement: it fails when either file's today condition alone is broken.
