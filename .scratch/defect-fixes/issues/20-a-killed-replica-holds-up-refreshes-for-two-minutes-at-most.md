# 20: A killed replica holds up refreshes for two minutes at most

**What to build:** When a replica dies in the middle of a refresh, the figures go stale for at most two minutes, not thirty. The lease tests first move to a supplied clock, because one of them already had to be loosened for slow hosts. See "Service: refresh" in the spec (`../spec.md`).

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] First, without changing behaviour: the lease tests run on a supplied clock, the hanging-renewal test no longer depends on how fast the host is, and all of them pass on both ClickHouse versions.
- [ ] Test first: a holder killed in mid-step is overtaken by another replica once the lease has run out. This fails with the thirty-minute lease.
- [ ] The lease is 120 seconds and is renewed every 40. This is a default the owner was not asked about.
- [ ] The rules from the reviews still hold: the lease is released on every failure, a replica that cannot prove it holds the lease stops before its next write, an expired claim is never revived, and two replicas never write at once.
- [ ] A step longer than the lease keeps it through its renewals.
- [ ] The fork specification's limit on a killed replica is updated.
- [ ] The change gets an independent review; this lease was reworked twice in review.
