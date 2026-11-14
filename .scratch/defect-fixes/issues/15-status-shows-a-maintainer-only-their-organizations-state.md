# 15: Status shows a maintainer only their organization's state

**What to build:** An organization maintainer sees whether processed history is complete, how far along it is, which periods can be offered, how fresh the figures are and the cutover day. They no longer see when the whole instance first recorded events or how many days of history it holds. Administrators keep the full block. See "Service: what a read returns" and "Page" in the spec (`../spec.md`).

**Blocked by:** 05 (First lint run on the fork's UI code).

**Status:** ready-for-agent

- [ ] Test first, through the service's read interface: a non-administrator's status has the complete flag, a progress percentage, the periods that can be offered, the freshness stamp and the cutover day, and has no first event day and no day counts.
- [ ] An administrator's status has the first event day and the day counts, with and without an organization selected.
- [ ] The percentage agrees with the administrator's day counts.
- [ ] Earlier events of another organization add no field to a maintainer's status.
- [ ] Test first, on the page with supplied answers: the history progress line renders from the percentage when the day counts are absent, and from the days when they are present.
- [ ] The period control still offers only processed periods.
- [ ] The access change gets an independent review.
