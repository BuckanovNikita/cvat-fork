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
- The independent review the ticket asks for; it follows the merge.
