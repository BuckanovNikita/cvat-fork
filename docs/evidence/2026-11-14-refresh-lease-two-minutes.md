# Refresh lease of two minutes, 2026-11-14

Ticket 20 of the defect fixes (`.scratch/defect-fixes/issues/20-…`). A replica killed inside a
step releases nothing, so the others waited for its claim to run out: 1800 s. The lease is now
120 s, renewed every 40 s (a default the owner was not asked about).

## Commits

| Commit | What |
| --- | --- |
| `4e29fee` | The lease's time comes from a `LeaseClock` (`team_analytics/refresh.py`): the replica's own seconds, the wait between renewals, and the instant ClickHouse stamps and judges claims by. The service's clock is real seconds and no instant, so ClickHouse's `now64()` stays the judge, as before. The lease tests supply a clock that stands still until the test moves it, and run on the default lease. No change of behaviour; the lease was still 1800 s. |
| `4d25d4b` | `refresh_lease_s` 1800 → 120; renewals every third of it (40 s), as before. New `KilledHolderTest`. The fork specification's limit on a killed replica is updated. |

## Checks with supplied boundaries (seam 1)

Each run used a frozen copy of the named tree, on the default image
`cvat/clickhouse:23.12.2-debian-11-r0` and on `clickhouse/clickhouse-server:23.11-alpine`.

| Tree | Tests | Default image | 23.11 |
| --- | --- | --- | --- |
| `4e29fee` (clock only) | `tests.test_lease` | 6 tests, OK | 6 tests, OK |
| `4e29fee` | `tests.test_refresh`, `tests.test_shutdown` (real lease clock) | 8 tests, OK | not run |
| `4e29fee` + `KilledHolderTest`, lease still 1800 s | `tests.test_lease.KilledHolderTest` | **2 failures** (below) | not run |
| `4d25d4b` | `tests.test_lease` | 8 tests, OK | 8 tests, OK |
| `4d25d4b` | `tests.test_refresh`, `tests.test_history`, `tests.test_shutdown` | 24 tests, OK | 24 tests, OK |
| `d36dc53` (merge with `feat/team-analytics-page`) | `tests.test_lease` | 8 tests, OK | 8 tests, OK |
| `d36dc53` | whole seam 1 suite | 271 tests, OK | not run |
| `c927eb6` (second merge; it brought only the details-table SQL and test into the service) | `tests.test_lease` | 8 tests, OK | 8 tests, OK |
| `c927eb6` | `tests.test_refresh`, `tests.test_history`, `tests.test_shutdown`, `tests.test_details_table` | 49 tests, OK | not run |

Red before the fix, with the thirty-minute lease:

- `test_a_holder_killed_in_mid_step_is_overtaken_once_its_lease_has_run_out`: "replica B is
  still held up two minutes after the holder was killed".
- `test_a_holder_killed_after_a_renewal_is_overtaken_two_minutes_after_that_renewal`: "replica A
  did not renew its lease 40 seconds on" (with 1800 s the first renewal is due at 600 s).

Both pass after the fix: replica B is refused at 119 s and gets the lease at 120 s, after the
claim and after the last renewal alike.

The hanging-renewal test no longer needs a longer lease: it ran on the default lease, and its
only real-time bound is the 60 s patience for something that should happen at once.

### The review rules still hold

Each rule the two review rounds added was broken in a copy of `4d25d4b`, and the test that
guards it was run on the default image. Each failed:

| Rule broken | Test | Failure |
| --- | --- | --- |
| A failed check of the claim releases the claim | `FailureTest.test_a_failed_check_of_the_claim_leaves_no_claim_behind` | the other replica got no lease |
| A failed release is tried again | `FailureTest.test_a_failed_release_is_tried_again` | the other replica got no lease |
| The lease is renewed while a step runs | `LongStepTest` | "replica A did not renew its lease" |
| A replica that cannot prove its lease stops before its next write | `LostLeaseTest…renewals_failed_past_the_lease_stops_its_step` | "replica A finished a refresh after losing the lease" |
| An expired claim is never revived (`lock_holder.sql`) | `LostLeaseTest…lands_after_the_claim_expired…` | "the expired claim of replica A came back to life" |
| The wait for a hanging renewal is bounded | `LostLeaseTest…hangs_does_not_hold_up_the_release` | "replica A's step waited for a hanging renewal" |

Two replicas never writing at once rests on the same tests: B is refused for as long as A can
prove its lease, and A stops writing once it cannot.

## Live outcome on real clocks

A throwaway check (not committed) started the service as `python -m team_analytics` on the tree
of `4d25d4b`, let it work through 300 days of history, killed it with SIGKILL and started a
second one on the same databases.

| Image | Unreleased claim left by the killed replica | Second replica's history moved on |
| --- | --- | --- |
| default | one claim, 119.5 s left | 122.8 s after the kill |
| 23.11 | one claim, 119.6 s left | 122.6 s after the kill |

The extra seconds over 120 are the second replica's retry pause of 5 s and its poll.

## Not verified

- A replica killed on the Kubernetes test stack. The live check is a killed process against the
  seam 1 ClickHouse, not a pod.
- That 120 s is long enough on a loaded production ClickHouse. A replica keeps 12 s of its
  lease in hand, so when two renewals in a row fail or stall (about 70 s) it stops its step
  before the next write, writes nothing, and tries again later. How often that happens under
  load was not measured.
- The independent review the ticket asks for; it follows the merge (done: "Independent review" below).

## Independent review

A fresh agent that had not written the changes reviewed the refresh package (tickets 17,
18 and 20) after it was merged, given the owner's documents and the three merges
(`2fc75b4d`, `f5d1f6a5`, `8eda4153`) and not the implementers' conclusions. It read and
probed the tree at `35f820d0`, each merge as its own diff and as the merged tree, and
changed no tracked file.

Verdict: no high-severity defect. Nothing it found lets two replicas write at once,
revives an expired claim, moves the cutover later outside the documented correction, or
marks an hour processed that nobody computed. One medium robustness finding, plus
documentation and test findings.

What the reviewer ran: `tests.test_lease`, `tests.test_history`, `tests.test_cutover` and
a probe module of its own (56 tests, default image, OK). Its probes: a late record with a
one-hour window (p1), two replicas finding different cutover hours (p2), the documented
correction of a wrongly early event with a replica running (p3), midnight with a one-hour
window (p4), two replicas whose clocks straddle midnight (p5), and a killed holder on the
production lease clock with a 6 s lease (p6: refused from 1.0 to 5.1 s, lease taken at
6.25 s).

### Findings and what was done

The follow-up is on branch `fix/refresh-review`, from `0d2661d6` on.

1. **Medium: a slow cutover search at start could crash-loop the pod, and the limits of
   ticket 17 were enforced nowhere.** The search ran before the port opened with no
   limit, so a search longer than the liveness window (about 70 s) would end the pod,
   and the interrupted `INSERT ... SELECT` might keep running in ClickHouse.
   Done (`e4da0c70`, tests corrected in `57dda6d7` and `4e2127eb`): the search at start
   and in the daily check runs with ticket 17's limits as settings of the statement
   (`max_execution_time` 23 s at start and 60 s in the daily check, `max_memory_usage`
   512 MiB, `timeout_overflow_mode` throw), through a client of its own for each limit
   (two more clients) whose read timeout is the limit plus 5 s. A search stopped at start lets the service start without
   it, as a failed one did; in the daily check the step now ends without it, and a lost
   lease still stops the step. The refresh's own search (`find_cutover`) keeps no
   limit, since failing it would fail the refresh before its hours are offered.
   Shown by `SlowSearchAtStartTest` and `SlowSearchInDailyCheckTest` in
   `tests/test_cutover.py`: a view over the events sleeps 0.5 s for every event a
   statement reads the payload of, sixteen events of one row each make the search take
   about 4 s, the limit is 1 s; the service answers, reports no cutover, nothing over
   the events is left running in ClickHouse, and the cutover is still absent after
   that. Both failed on the tree before the fix with only the tests and the
   configuration fields added (a stored cutover of 12 November 11:00 and of 14 November
   15:00), and both failed with the limit not sent to ClickHouse while the client still
   waited only the limit plus 5 s. The first version of the fixture was not slow:
   ClickHouse refuses more than 3 s of sleep per block and failed the statement at once,
   so the first red run passed; a second version put the slow work where history
   computes it, so the step under test was not the daily check. Both were caught by
   their red runs and corrected before the fix was counted as shown.
   What was found out, in a throwaway ClickHouse
   ([`2026-11-14-refresh-review-limits/`](2026-11-14-refresh-review-limits/), the probe
   and its output):
   - The client in the service's image is `clickhouse-connect` 1.3.0. Its default wait
     is `send_receive_timeout` 300 s, a read timeout between two reads of the answer,
     not a bound on the whole statement. It asks the server for progress headers every
     `max(10, timeout − 5)` seconds (at most 120), read in the client's source. Observed
     once on each image: a client with a 12 s timeout waited the whole 20 s of a
     statement and got its answer, which fits the headers resetting the read timeout.
     Inferred, not observed: with the service's default, a statement that runs on is
     waited for as long as progress headers keep arriving. The server's limit is
     therefore the bound; the client's read timeout only has to be longer than it, so
     that the client does not give up first. For the 23 s and 60 s limits the progress
     interval equals the limit, shorter than the limit plus 5 s.
   - A client that gives up does not stop an `INSERT ... SELECT`: with a 2 s client
     timeout and no server limit, the statement was still in `system.processes` 8 s
     later.
   - `max_execution_time` does stop an `INSERT ... SELECT`: at 1.0 s (and at 0.5 s), with
     `TIMEOUT_EXCEEDED` (159) in the query log and no row inserted. With the service's
     setup (limit 2 s, client wait 7 s) the client got the error at 2.0 s.
   - Not shown: the memory limit stopping a statement. The probe's statement used too
     little memory to reach even 1 MiB; the setting is accepted, nothing more. The probe
     for a plain `SELECT` had a syntax error and shows nothing.
   - The same on both images, `cvat/clickhouse:23.12.2-debian-11-r0` and
     `clickhouse/clickhouse-server:23.11-alpine` (23.11.5).
   The reviewer's cheaper query was tried: read the events in timestamp order and stop at
   the first match. Every cutover test passed unchanged on it (22 tests, default image,
   tree `57dda6d7` with the statement replaced), and it was adopted in `c3edcd58`. It
   saves reading only on a search while no cutover is stored: every search after that
   finds no match and reads every row before the stored cutover, as the aggregate did.
   Its cost at the benchmark's scale was not measured with this follow-up; it was
   measured on 2026-11-15 (`2026-11-14-cutover-search-cost.md`, section of that date):
   reading in order takes about as long as the aggregate where nothing matches (2.6 %
   longer in the steady state, with more memory), and the
   statement stops after a fraction of a second where the first tagged record is early.
   The related low point, a stop signal during a long daily search leaving the lease
   held: not changed, recorded as a known limit in `docs/fork-specification.md`.
   Releasing the lease from the signal while the step's statement still runs in
   ClickHouse could let another replica write beside it, and stopping the statement
   would mean tracking each statement's query id and killing it; neither is a small
   change. The 60 s limit now bounds the statement itself.
2. **Low to medium: with a short window a late record is left out while the period reads
   as processed, until after midnight; the fork specification said nothing.** Done
   (`0f7a7343`): a known-limits bullet on a refresh window shorter than a day, with the
   moment after each window move when every period reads as being processed, and that
   the default window does not behave so. A document change; checked by reading
   against probe p1 and the ticket 18 evidence.
3. **Low: the header of `schema/041_history_today.sql` said replicas whose clocks
   straddle midnight agree.** Done (`0f7a7343`): it now says they can answer
   differently for a short time, the one that says processed is right, the other only
   cautious, and they agree after the whole-day step. Pinned by
   `ShortWindowTest.test_two_replicas_whose_clocks_straddle_midnight_differ_only_in_caution`
   (below).
4. **Low: several criteria shown only on internals.** Done:
   - (a) `KilledHolderTest` (`afb26449`) now waits for each renewal the killed holder's
     renewal thread tries before asking the other replica, and a new test shows a holder
     that is alive keeping the lease 160 s on the same clock. With `kill()` made to do
     nothing, both killed-holder tests fail ("replica B is still held up …"); the old
     two tests at `a423f824` passed with the same change, which is what the reviewer
     read.
   - (b) `LostLeaseTest.test_work_done_after_the_lease_was_lost_stays_out_of_status_and_figures`:
     a replica computes two more minutes of work, loses the lease before it marks them,
     and status and the overview still show the earlier refresh and one minute. With the
     `lease-always-held` mutation it fails through the reads (the later refresh and
     three minutes show).
   - (c) `ProductionClockTest`: the service's own lease clock, a 4 s lease, the holder
     killed in mid-step; the other replica tries every 0.5 s until it gets the lease, and
     ClickHouse's clock has moved on by at least the lease between before the claim and
     after the takeover. Only a lower bound is asserted, so a slow host only waits
     longer.
   - (d) `tests/test_entry_point.py` `CutoverOnTheFirstAnswerTest` (`02bfdcb3`): the
     service started as `python -m team_analytics`, the only shape-tagged event 300 days
     back behind daily untagged work; its first answer has the cutover. With the start
     search removed from `Service.setup` it fails (no cutover on the first answer).
   - (e) `tests/test_history.py` (`a67ca5ca`): midnight with a one-hour window (from
     p4) and two replicas whose clocks straddle midnight (from p5). They pin behaviour
     that did not change, so they passed when written.
   The six guarding tests of ticket 20 still fail when their rule is broken, on
   `57dda6d7` (same mutations as above, default image): a failed claim check releases
   nothing, a failed release is not retried, no renewal, the lease always held, an
   expired claim revived, an unbounded renewal join. Each failed. `refresh.py` and the
   lease's SQL files did not change after `57dda6d7`, so this holds for the head.
5. **Nits.** Done: `sql.py` calls a parameter value only when it is wrapped in
   `AtRun`, which the lease clock uses (`0d2661d6`); the fork specification says the
   lease runs out at most 120 s after a kill and the next replica takes over at its next
   try (every 5 s), and the about 123 s measured stays in this file; the `worker.py`
   and `test_history.py` docstrings give the step order and today's step and the
   cutover search in the daily check.

### Runs of the follow-up (seam 1)

Each run used a frozen copy of the named tree (`git archive`), through the shared lock.

| Tree | Tests | Default image | 23.11 |
| --- | --- | --- | --- |
| `a67ca5ca` (before the fix) with `tests/` and `config.py` of `4e2127eb` | the two slow-search tests | **2 failures**: a cutover was stored (12 November 11:00, 14 November 15:00) | not run |
| `4e2127eb` with the limit not sent to ClickHouse | the two slow-search tests | **2 failures**, the same | not run |
| `4e2127eb` with `lease-always-held` | the lost-lease reads test | **failure**: status and figures show the lost refresh | not run |
| `57dda6d7` with `kill()` doing nothing | `KilledHolderTest` | **2 failures**, the alive holder passes | not run |
| `a423f824` (before) with `kill()` doing nothing | its `KilledHolderTest` | 2 tests, OK: the old tests did not notice | not run |
| `57dda6d7` with the start search removed | `CutoverOnTheFirstAnswerTest` | **failure**: no cutover on the first answer | not run |
| `57dda6d7` with each of ticket 20's six mutations | the guarding test of each | **each failed** | not run |
| `57dda6d7` with the in-order search | `tests.test_cutover` | 22 tests, OK | not run |
| `c3edcd58` | `tests.test_lease`, `test_cutover`, `test_history`, `test_refresh`, `test_shutdown`, `test_entry_point`, `test_status` | 73 tests, OK | not run |
| `c3edcd58` | `tests.test_lease`, `tests.test_cutover` | 33 tests, OK | 33 tests, OK |
| `ea7ed078` (merge of `feat/team-analytics-page`, `6a442e9a`) | the seven modules above | 73 tests, OK | not run |
| `ea7ed078` | `tests.test_lease` | 11 tests, OK | 11 tests, OK |
| `ea7ed078` with the limit not sent (the in-order statement) | the two slow-search tests | **2 failures**: a cutover was stored | not run |

`nice -n19 prek run --all-files` passed after the last commit (ruff among its hooks).

### What held, by the reviewer's account

The lease: released on every failure, no write without proof of the lease, an expired
claim stays expired, a step longer than the lease keeps it, the supplied clock does not
change production, and a write in flight when the lease runs out can overlap the next
holder only with unmarked totals rows. The cutover only moves earlier and replicas
leave one value (p2); the documented correction works with a replica running (p3). The
history step does no extra work with the default window, and lease loss before today's
record leaves today missing.

### Not checked

- By the reviewer: a search on data larger than the benchmark or under load, the second
  image, a stopped replica on the Kubernetes stack, windows between 2 and 23 hours, clock
  steps on the ClickHouse host.
- By the follow-up: the limits on a real slow search at scale (the slow search here is a
  sleeping view on small data), the memory limit actually stopping a statement, the
  in-order statement's cost at the benchmark's scale, a pod's start on the stack against
  its liveness probe, and the whole seam 1 suite (the orchestrator runs it on both images
  after the merge).
