# 26: The volume goes through the events API

**What to build:** The large-team data of the test stack reaches ClickHouse the way real work does, through CVAT's events API and Vector. Until now it was inserted straight into ClickHouse. The current week goes through the API; older weeks do too only if the API accepts old timestamps, which is not known. That is a default the owner was not asked about. See "Testing Decisions" in the spec (`../spec.md`).

**Blocked by:** 08 (The stack runs on the fork server image and the in-tree chart).

**Status:** ready-for-agent

- [ ] It is found out and recorded what the events API does with events that carry old timestamps.
- [ ] The current week of the volume, one hundred annotators, is sent through the real events API in each annotator's own session and arrives through Vector. None of it is inserted directly.
- [ ] Older weeks go through the API if it accepts them unchanged; otherwise they stay direct inserts and the evidence says so.
- [ ] The figures of the current week equal the generator's expected values, as before.
- [ ] A second run on the same stack does not load the volume twice.
- [ ] How long the load takes is recorded in the dated evidence.
