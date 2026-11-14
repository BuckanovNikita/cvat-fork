# 20: A killed replica holds up refreshes for two minutes at most

**What to build:** When a replica dies in the middle of a refresh, the figures go stale for at most two minutes, not thirty. The lease tests first move to a supplied clock, because one of them already had to be loosened for slow hosts. See "Service: refresh" in the spec (`../spec.md`).

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [x] First, without changing behaviour: the lease tests run on a supplied clock, the hanging-renewal test no longer depends on how fast the host is, and all of them pass on both ClickHouse versions.
- [x] Test first: a holder killed in mid-step is overtaken by another replica once the lease has run out. This fails with the thirty-minute lease.
- [x] The lease is 120 seconds and is renewed every 40. This is a default the owner was not asked about.
- [x] The rules from the reviews still hold: the lease is released on every failure, a replica that cannot prove it holds the lease stops before its next write, an expired claim is never revived, and two replicas never write at once.
- [x] A step longer than the lease keeps it through its renewals.
- [x] The fork specification's limit on a killed replica is updated.
- [ ] The change gets an independent review; this lease was reworked twice in review.

## Comments

2026-11-14: Done in `4e29fee` (supplied lease clock, lease still 1800 s; `tests.test_lease` passed on both ClickHouse images at that tree) and `4d25d4b` (120 s, renewed every 40 s). `KilledHolderTest` failed first with the 1800 s lease. Each review rule was broken in a copy of the tree, and the test that guards it failed. A real process killed with SIGKILL held the next one up for about 123 s on both images. After the merge of the integration branch, `tests.test_lease` passed on both images and the whole seam 1 suite on the default image. Evidence: `docs/evidence/2026-11-14-refresh-lease-two-minutes.md`. Not shown: a kill on the Kubernetes stack, and the lease under production load.

2026-11-14: The independent review criterion is open. The reviewer reads this change after it is merged; it was not reviewed in this branch.
