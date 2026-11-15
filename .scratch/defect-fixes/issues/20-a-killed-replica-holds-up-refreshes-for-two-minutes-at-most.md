# 20: A killed replica holds up refreshes for two minutes at most

**What to build:** When a replica dies in the middle of a refresh, the figures go stale for at most two minutes, not thirty. The lease tests first move to a supplied clock, because one of them already had to be loosened for slow hosts. See "Service: refresh" in the spec (`../spec.md`).

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] First, without changing behaviour: the lease tests run on a supplied clock, the hanging-renewal test no longer depends on how fast the host is, and all of them pass on both ClickHouse versions.
- [x] Test first: a holder killed in mid-step is overtaken by another replica once the lease has run out. This fails with the thirty-minute lease.
- [x] The lease is 120 seconds and is renewed every 40. This is a default the owner was not asked about.
- [x] The rules from the reviews still hold: the lease is released on every failure, a replica that cannot prove it holds the lease stops before its next write, an expired claim is never revived, and two replicas never write at once.
- [x] A step longer than the lease keeps it through its renewals.
- [x] The fork specification's limit on a killed replica is updated.
- [x] The change gets an independent review; this lease was reworked twice in review.

## Comments

2026-11-14: Done in `4e29fee` (supplied lease clock, lease still 1800 s; `tests.test_lease` passed on both ClickHouse images at that tree) and `4d25d4b` (120 s, renewed every 40 s). `KilledHolderTest` failed first with the 1800 s lease. Each review rule was broken in a copy of the tree, and the test that guards it failed. A real process killed with SIGKILL held the next one up for about 123 s on both images. After the merge of the integration branch, `tests.test_lease` passed on both images and the whole seam 1 suite on the default image. Evidence: `docs/evidence/2026-11-14-refresh-lease-two-minutes.md`. Not shown: a kill on the Kubernetes stack, and the lease under production load.

2026-11-14: The independent review criterion is open. The reviewer reads this change after it is merged; it was not reviewed in this branch.

2026-11-14: Merged into `feat/team-analytics-page` as `f5d1f6a5`; ticket 17 followed as `8eda4153`. On the tree of both, seam 1 `tests.test_lease tests.test_cutover tests.test_history tests.test_refresh tests.test_shutdown tests.test_status tests.test_entry_point tests.test_concurrency` ran 65 tests on the default image, OK. Evidence: `docs/evidence/2026-11-14-refresh-lease-two-minutes.md`. The independent review stays open.

2026-11-14: The independent review ran after the merge, over tickets 17, 18 and 20 together: no high-severity defect, one medium finding (the cutover search had no enforced limit), and documentation and test findings. Its findings and what the follow-up on branch `fix/refresh-review` did about each are in "Independent review" in `docs/evidence/2026-11-14-refresh-lease-two-minutes.md`. For this ticket: the killed-holder tests now fail when the kill stops nothing, a holder that is alive is shown keeping the lease past its length, work done after losing the lease is shown absent from status and figures, an expiry test runs on the production lease clock, and the lease clock's time is bound through an explicit marker. The fork specification's wording on the takeover after a kill and the stop signal's limit during a long step were corrected. The six guarding tests still fail when their rule is broken.

2026-11-15: The review follow-up was merged into `feat/team-analytics-page` as `3dc1a7bc`, after the ticket itself as `f5d1f6a5`. With the independent review done and recorded, every criterion is met. On the merged tree `prek run --all-files` passed all nine hooks. Evidence: `docs/evidence/2026-11-14-refresh-lease-two-minutes.md`.

2026-11-15: The code review of the integrated branch (finding 9, recorded in `docs/evidence/2026-11-15-integrated-branch-review.md`) is fixed on branch `fix/code-review`. `control/lock_claim.sql` and `control/lock_release.sql` now take the supplied-clock expression once, as `stamp`, through `INSERT ... SELECT`. `lock_holder.sql` names it once and is unchanged. Behaviour is unchanged: `tests.test_lease` passes on both ClickHouse images, and each of the six rule-guarding tests this ticket named still fails when its rule is broken.
