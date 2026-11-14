# 18: A short refresh window leaves no hour falsely processed

**What to build:** With a refresh window shorter than a day, today's earlier hours are either computed or reported as not processed. Today they count as processed without anyone having computed them. See Processed history in `GLOSSARY.md` and "Service: refresh" in the spec (`../spec.md`).

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Test first, through the service's read interface: with a one-hour window, an event from earlier today, before the window, is either in the figures or its period reads as not processed. This fails today.
- [ ] With the default window nothing changes: the same hours are computed and no extra work is done.
- [ ] The existing tests that set a one-hour window to exercise the edge between two refreshes still pass; short windows stay possible.
- [ ] History is still processed newest first, and the daily recount is unchanged.
- [ ] The fork specification no longer lists this as a known limit.
