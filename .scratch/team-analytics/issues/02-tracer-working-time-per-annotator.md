# 02: Tracer: working time per annotator for the last week

**What to build:** The thinnest complete path through the feature. A maintainer of an organization opens Team Analytics from the header and sees each annotator's working time for the last seven days; an ordinary annotator is refused. This puts every part in place once: stored totals with their refresh, the analytics service with its first access rule, and the page. See the spec (`../spec.md`), ADR 0001 and the prototype.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] The header shows a Team Analytics link to owners and maintainers of the current organization and to members of the admin group, and only when analytics is enabled on the server.
- [ ] The existing link to the stock dashboards reads Grafana; where it leads and how it opens are unchanged.
- [ ] The page address does not start with the Grafana prefix, and neither does the service's.
- [ ] The page loads on demand. When it fails, or the service cannot be reached, an error panel appears on that page and the rest of CVAT keeps working.
- [ ] The page lists the organization's annotators with their working time for the last seven days, largest first. Each figure equals the server's job-bound working time for that person and span.
- [ ] Figures are read from stored hourly totals kept per organization, project, task and annotator, in a database of their own; the events table is only read.
- [ ] Totals are refreshed every ten minutes by recomputing a trailing window and replacing whole hours; the computation reads a few minutes before the window; only one refresh runs at a time.
- [ ] The service asks CVAT, with the caller's own credentials, who the caller is and what role they hold. Members of the admin group, owners and maintainers get figures; everyone else is refused.
- [ ] The organization a query is limited to comes from CVAT's answer. An organization identifier sent by the browser cannot widen what is returned.
- [ ] All calculations are SQL kept in the repository; the service contains no aggregation logic.
- [ ] No new package is added to the UI.
- [ ] Tests reach the behaviour through the service's read interface against a real ClickHouse, and through the page with supplied service responses.
