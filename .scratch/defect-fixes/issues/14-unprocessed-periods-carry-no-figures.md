# 14: Unprocessed periods carry no figures

**What to build:** A maintainer, a script or anyone else who asks for a period that is not fully processed gets no figures, only the statement that it is still being processed. Today the service returns the partial figures with a flag and only the page hides them. See Processed history in `GLOSSARY.md` and "Service: what a read returns" in the spec (`../spec.md`).

**Blocked by:** 05 (First lint run on the fork's UI code).

**Status:** resolved

- [x] Test first, through the service's read interface: for a period that is not fully processed, the overview, the full-view list and the details table answer with their envelope, `processed: false` and every figure-bearing field null. The existing tests that expect figures there are changed and seen to fail before the fix.
- [x] A trend bucket that is not fully processed has a null value; processed buckets beside it are unaffected.
- [x] Answers for a fully processed period are unchanged.
- [x] The legacy flags stay in the envelope.
- [x] Test first, on the page with supplied answers: an answer without figures shows the "being processed" state in the overview, the full view, the details table and the trends, and no card fails on a null.
- [x] The fork specification no longer lists partial figures through a direct call as a known limit.

## Comments

2026-11-14: Done on branch `ticket/14-no-figures`. Tests first: `fb65b41` (service), `89bcbb8` (page); fixes `85bcfae` (service), `a931f28` (page); the fork specification `7eab11a`; repairs of existing tests that read an unprocessed period `3f5367a` and `adf4d38` (the latter applies the ticket 18 note). Runs and what stays unverified: `docs/evidence/2026-11-14-unprocessed-periods-carry-no-figures.md`.

How each criterion was shown:

- Envelope and null figures for the overview, list and table: seam 1, the four changed tests failed against the unchanged service on the figures it still sent, and pass after the fix. The existing processed-flag tests were the ones that expected figures there.
- Trend buckets: seam 1, `test_trends.ProcessedTest` (eleven unprocessed weeks null, the processed week beside them with its hour; all twelve with figures once processed).
- Fully processed answers unchanged: seam 1, every module that reads the four endpoints passes; `test_full_view.ProcessedTest` adds a processed list with its figures.
- Legacy flags: asserted in the same four tests (`legacy`, `partly_legacy`, `cutover`, `shapes`; `legacy` and `hotkey_recorded` on trend points).
- Page: seam 3, with answers shaped as the service sends them; 8 tests failed before the fix (the loaders refused the answers, the annotator label and two name lookups read null rows) and all pass after. The details and trends cards already held up with nulls.
- Fork specification: a stated check. It listed no such limit at the base of this branch or after the last merge (searched for "partial", "processed" and "direct call"); it now states the rule.

The whole seam 1 suite was not run, by instruction; it is left for the integration branch.

2026-11-14: Merged into `feat/team-analytics-page` as `35f820d0`, after tickets 22 (`50895e77`) and 15 (`5fae08e9`). One conflict, in `verify/team-analytics-page/history.test.cjs`, kept both sides: this ticket's `NO_FIGURES` answer and ticket 15's note on the administrator's history block. On the merged tree `node --test verify/team_analytics_logging.cjs` ran 70 tests and `node --test verify/team_analytics_page.cjs` 217, 0 failed and 0 skipped each; the skip-gate grep finds nothing; `prek run --all-files` passed all nine hooks. The service suite was not run by the merger. Evidence: `docs/evidence/2026-11-14-unprocessed-periods-carry-no-figures.md`.

2026-11-14: Follow-up to the independent review of tickets 14 to 16 (branch `fix/reads-review`; the review and what was done about each finding are in `docs/evidence/2026-11-14-status-for-maintainers.md`, "Independent review"). Three findings touch this ticket:

- Trend candidates carried figures from unprocessed time: a candidate's `working_time_ms` summed every computed hour of the twelve buckets and ranked the candidates. It now sums only the fully processed buckets, is null while none is, and candidates are ranked by it and then by id (`tests.test_trends.ProcessedTest.test_a_candidate_has_working_time_only_from_processed_buckets`, seen failing first). The withholding tests of the four endpoints now also assert that every key outside the stated envelope is null (per point for the trends, per candidate while nothing is processed).
- Figures were read before `processed` was decided, so a history step finishing in between could send partial figures marked processed. Every endpoint now reads the history state once per request, before any figure. Shown with a probe, not a test (it lands a step mid-request through the service's SQL layer, which no public boundary allows).
- Recorded limit, behaviour unchanged by decision of the owner: the legacy flags of an answer that is not fully processed (`legacy`, `partly_legacy`, `shapes`, and `hotkey_recorded` on a trend point) describe only the part already processed and can change, even to the opposite, once processing completes. A caller must not read them as final while `processed` is false. The page hides the shape switch from `operations.legacy`, so the switch can appear or vanish when processing completes. Written into `docs/fork-specification.md` ("Known limit of unprocessed periods") and beside the switch in `team-analytics-view.tsx`; `test_trends.ProcessedTest` and `test_full_view.ProcessedTest` keep pinning today's values, with a comment that they pin this limit. Changing the flags is the owner's decision.

2026-11-15: Recorded limit from the independent review of tickets 23 and 24 (branch `fix/page-review`; the review is in `docs/evidence/2026-11-14-overview-bars-split-by-operation.md`, "Independent review, 2026-11-15", finding 1). Behaviour unchanged. Who is a trends comparison candidate comes from every computed hour of the twelve buckets, processed or not, so the list tells who has work in buckets not yet processed, which every other read withholds; once any bucket is processed, a candidate's `working_time_ms` of 0 (not null) marks exactly those whose only work lies in unprocessed buckets. It stays inside the caller's scope (the selected organization, or the whole instance for an admin with none selected). This was the implementer's choice, made so the comparison can be offered while history is processed, not the owner's. Written into `docs/fork-specification.md` where the candidates are described. Keeping it, sending null for a counted 0, or listing only candidates with work in processed buckets is an open decision for the owner.

2026-11-15: The code review of the integrated branch (recorded in `docs/evidence/2026-11-15-integrated-branch-review.md`) found two things in this ticket's work, both fixed on branch `fix/code-review`. Finding 3: a period not fully processed had every figure read and then nulled. Now the overview reads only its envelope's sections, and the full view's hotkeys and the details table's rows are not read at all. The reads that give the legacy flags still run: the overview's operations, the list's rows by annotator or project, the details summary and the trends. Every envelope is exactly as before; the withholding tests, which assert every key, pass unchanged. Finding 7: the status section read the history state by its own path. It now takes the request's one reading.

2026-11-15: Changed by the follow-up to the review of the follow-ups (branch `fix/last-review`, findings 2 and 3). The hotkeys list again answers 400 for a bad annotator, project or shapes value when the period is not processed (it answered 200 with null figures); a new test in `tests.test_full_view` failed before the fix and passes after it. The short-window limit in `docs/fork-specification.md` now says such a period reads as not processed yet, and what a person sees for the waiting hour: no month offered and the trends card saying none are ready, while an earlier month or week asked for directly still answers as processed. The limit's behaviour is unchanged. Evidence: `docs/evidence/2026-11-15-integrated-branch-review.md`, "Review of the follow-ups".
