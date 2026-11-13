---
status: accepted
---

# A thin analytics service reads stored totals computed in SQL

Team Analytics gets its figures from a small dedicated service, not from the existing events export and not from Grafana. The service does three things: it asks CVAT who the caller is and what role they hold, it runs a fixed set of read queries pinned to the caller's organization, and it triggers a refresh of stored hourly totals every ten minutes. Every calculation (sessions, time per operation, alignments, hotkey counts) is SQL kept in this repository; the service holds no aggregation logic.

## Considered Options

- **Events export, aggregated in the browser.** Needs no new component and inherits the stock server's access filter, but it ships raw rows. At about 100,000 events a day, a Year period or a twelve-month trend means tens of millions of rows per page open.
- **Queries sent through Grafana.** Grafana already holds the ClickHouse connection, so nothing new would be deployed. Access to it is a per-user flag, and anyone who has it can run any query over every organization. Owners and maintainers must get in by role, and organizations must not see each other, so this was rejected.
- **A service that aggregates in application code.** Exact on every rule, but it duplicates in code what ClickHouse does in well under three seconds for a year of events, and it is more to write, test and review.
- **Direct queries on raw events at every page open, without stored totals.** Fast for one viewer; four concurrent year-long queries took about fifteen seconds each in the measurement.

## Consequences

- Access control is this fork's own code. The stock events policy no longer protects these figures, so the role and organization check needs negative tests and an independent review.
- The session gap and the idle pause are fixed when totals are computed. Changing either means recomputing history.
- A refresh must read a few minutes before its window, or sessions and time per operation break at the window edge. History is filled one day at a time; a single year-long fill that reads event payloads exhausts memory with default settings.
- "Changed since the last run" cannot be a timestamp cut-off. Events carry the browser's clock and a failed batch is resent later, so rows can land behind any cut-off. Each refresh therefore redoes a trailing window and replaces those hours; older days are redone when their raw row count no longer matches.
- Totals are stored per task although the page stops at projects, so a task or job view can be added without recomputing history.
- Working time and operation time come from different records: the server stamps working time with the first event of a batch and the job of the preceding event, while an operation carries its own time and job. Over a narrow slice (one hour, one project) operations can therefore exceed working time. Other is computed for the scope being displayed and is never shown below zero.
- One rule is approximate in SQL: time spent on navigation while a box is being drawn goes to that drawing only when the navigation lies wholly inside one drawing or alignment.
- ClickHouse in this deployment cannot schedule a refresh itself, which is why the service triggers it.

Measured on a synthetic year of 36 million events: [design measurements, 2026-11-13](../evidence/2026-11-13-team-analytics-design-measurements.md).
