# 17: The cutover is known at start and can move earlier

**What to build:** Periods are labelled legacy only when they are. The cutover is known from the first answer after the service starts, and it moves to an earlier hour when an earlier shape-tagged event turns up, never to a later one. See Cutover, Legacy period and Partly legacy period in `GLOSSARY.md` and "Service: refresh" in the spec (`../spec.md`).

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [x] Before the change is adopted, the cost of the long-range search is measured, in time and memory, on data of the scale of the design measurements (about 36 million event rows, built with the benchmark fixture under `docs/evidence/`), and recorded. The test stack's few thousand rows are not a measurement. If it is too costly, the fallback of the spec is used and this ticket says so.
- [x] Test first, through the service's read interface: a service started on stored shape-tagged events knows the cutover on its first answer, before any refresh.
- [x] Shape-tagged work that exists only in the recorded events, not yet in the stored totals, yields a cutover.
- [x] An earlier shape-tagged event that arrives after the cutover was stored moves it to that event's hour at the next daily check. A later event never moves it.
- [x] After a move, the periods between the two hours are relabelled.
- [x] An instance with no shape-tagged event has no cutover, and every period with job work is legacy, as today.
- [x] It holds with several replicas: two of them finding the cutover at once leave one value.
- [x] A table's legacy content with its own dimension's filter set is pinned by a test. Its behaviour does not change.
- [x] The fork specification's limits of the stored cutover are rewritten: a shape-tagged event with a wrongly early date moves the cutover, and the correction is to remove that event and then the stored value.

## Comments

2026-11-14: Done on branch `ticket/17-cutover`. The measurement is in `docs/evidence/2026-11-14-cutover-search-cost.md`, the test runs and what was not verified in `docs/evidence/2026-11-14-cutover-at-start.md`.

**The search is adopted at service start and in the daily check. The fallback is not used.** The figure that decided it: on the benchmark fixture at its full scale (36,326,651 rows, the generator's `base_n` found to be 325), the slowest cold run of the shipped statement over the full range took 6.49 s and 64 MiB of peak memory. The limits were written and committed before the figures were read (`49021b8`): 23 s at start, a third of the pod's liveness window, because the search runs before the service opens its port; 60 s in the daily check; 512 MiB. The measurement ran in a ClickHouse 23.12.2 container with 2 CPUs on a machine in use, not with the 6 CPUs and 23.11.5 of the design measurements, so the two are not compared as equals. Once a cutover is stored, the search reads only the events before it.

How it is built:

- The `cutover` table keeps its shape and needs no migration. It now holds every hour a search found, and a read takes the earliest. That is what makes the cutover move only earlier, and what leaves one value when replicas search at once.
- At start the search runs in `Service.setup`, after the schema and before the service answers, without the refresh lease. A search that fails there is logged and the service starts, as it did before when CVAT's `events` table was not there yet. That can happen: `verify/team-analytics-stack/run.sh` applies the service right after installing the chart and only then waits for the chart's initializer job. This order was read in the script, not observed on a stack.
- In the daily check the search runs after the check is recorded, under the lease. A search that fails there is tried again by the next daily check, not thirty seconds later.
- The refresh still finds the cutover when it first stores a shape-tagged hour while none is stored, as before. Without it an instance whose first tagged event arrives during the day would wait for the next daily check.
- While no cutover is stored the search stops at the end of the current hour, so an event dated in the future does not become the cutover.

Shown first to fail on the old service, then to pass: the first answer after a start; tagged work that has not reached the stored totals; two replicas started at once; the move at the next daily check with its relabelled periods; the correction of a wrongly early event. Passing before and after, because they state what must not change: a later event never moves the cutover; no shape-tagged event means no cutover and legacy periods; a table under its own filter. The last one was also run against a throwaway copy of the service in which the tables apply their own filter, and failed there in all four cases, so it can fail.

Notes on single criteria:

- Several replicas: the test starts two instances at the same moment on stored events and both report the one hour, then and after a refresh and a daily check by one of them. Both find the same hour. Two searches that find different hours at once were not produced; that case rests on the read taking the earliest stored hour.
- The fork specification: only the bullet on the limits of the stored cutover is rewritten, as this ticket was told. The bullet before it, "Legacy rule", still says that the step that first stores a shape-tagged hour finds the cutover and that the stored value never moves. Both sentences are now out of date and are left for whoever next edits that section.
- The correction of a wrongly early event is exercised by a test, which the final run of Team Analytics had recorded as not exercised. It showed one thing the spec does not say: after the event and the stored rows are removed, the cutover comes back at the next service start or daily check, not at the next refresh, because the stored totals still hold the removed event's hour until its day is counted again. The fork specification says so.

Not run: the whole seam 1 suite (eleven modules ran on the default image, `test_cutover` also on the second one), and nothing on the stack.

Found on the way, not part of this ticket: `verify/team_analytics_service.sh` removes its ClickHouse container without its anonymous volumes, so every run on `clickhouse/clickhouse-server:23.11-alpine` leaves two unused volumes behind. The two from this ticket's run were removed by hand.
