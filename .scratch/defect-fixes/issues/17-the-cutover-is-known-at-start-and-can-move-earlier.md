# 17: The cutover is known at start and can move earlier

**What to build:** Periods are labelled legacy only when they are. The cutover is known from the first answer after the service starts, and it moves to an earlier hour when an earlier shape-tagged event turns up, never to a later one. See Cutover, Legacy period and Partly legacy period in `GLOSSARY.md` and "Service: refresh" in the spec (`../spec.md`).

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Before the change is adopted, the cost of the long-range search is measured on the large loaded volume, in time and memory, and recorded. If it is too costly, the fallback of the spec is used and this ticket says so.
- [ ] Test first, through the service's read interface: a service started on stored shape-tagged events knows the cutover on its first answer, before any refresh.
- [ ] Shape-tagged work that exists only in the recorded events, not yet in the stored totals, yields a cutover.
- [ ] An earlier shape-tagged event that arrives after the cutover was stored moves it to that event's hour at the next daily check. A later event never moves it.
- [ ] After a move, the periods between the two hours are relabelled.
- [ ] An instance with no shape-tagged event has no cutover, and every period with job work is legacy, as today.
- [ ] It holds with several replicas: two of them finding the cutover at once leave one value.
- [ ] A table's legacy content with its own dimension's filter set is pinned by a test. Its behaviour does not change.
- [ ] The fork specification's limits of the stored cutover are rewritten: a shape-tagged event with a wrongly early date moves the cutover, and the correction is to remove that event and then the stored value.
