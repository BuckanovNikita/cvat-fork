# 14: Unprocessed periods carry no figures

**What to build:** A maintainer, a script or anyone else who asks for a period that is not fully processed gets no figures, only the statement that it is still being processed. Today the service returns the partial figures with a flag and only the page hides them. See Processed history in `GLOSSARY.md` and "Service: what a read returns" in the spec (`../spec.md`).

**Blocked by:** 05 (First lint run on the fork's UI code).

**Status:** ready-for-agent

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
