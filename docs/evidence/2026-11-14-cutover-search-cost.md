# Cost of the cutover's long-range search (2026-11-14)

Ticket 17 of the defect fixes lets the service look for the cutover in the recorded events
at start and in the daily check. That is one aggregate over the raw events from the first
event on. The defect-fix spec asks for its cost to be measured on a loaded volume before
it is adopted, and names a fallback if it is too costly.

Files: [`2026-11-14-cutover-search-cost/`](2026-11-14-cutover-search-cost/) (`run.sh` is
the whole procedure; `search.sql` is the statement as it ran; `setup.txt` and `report.txt`
are its output).

## What counts as acceptable

Written before the figures were read.

- **At start.** The search runs before the service opens its port. The liveness probe of
  `team-analytics/k8s/deployment.yaml` first looks 30 seconds after the container starts
  and restarts it after three failures 20 seconds apart, so a start that lasts about 70
  seconds is killed. The search is acceptable at start when the slowest cold run over the
  full range takes at most a third of that, 23 seconds. Above that it is reported as too
  costly at start, and the fallback of the spec applies.
- **In the daily check.** The search runs under the refresh lease, so a due ten-minute
  refresh waits for it. It is acceptable when it takes at most a tenth of the refresh
  interval, 60 seconds.
- **Memory.** Peak memory of at most 512 MiB, a quarter of the 2 GiB the seam 1 ClickHouse
  runs with. The design measurements' long-range queries that failed did so at the 9 GiB
  server limit.

The deciding figure is the slowest cold run over the full range.
