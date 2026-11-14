# 14: Unprocessed periods carry no figures

**What to build:** A maintainer, a script or anyone else who asks for a period that is not fully processed gets no figures, only the statement that it is still being processed. Today the service returns the partial figures with a flag and only the page hides them. See Processed history in `GLOSSARY.md` and "Service: what a read returns" in the spec (`../spec.md`).

**Blocked by:** 05 (First lint run on the fork's UI code).

**Status:** ready-for-agent

- [ ] Test first, through the service's read interface: for a period that is not fully processed, the overview, the full-view list and the details table answer with their envelope, `processed: false` and every figure-bearing field null. The existing tests that expect figures there are changed and seen to fail before the fix.
- [ ] A trend bucket that is not fully processed has a null value; processed buckets beside it are unaffected.
- [ ] Answers for a fully processed period are unchanged.
- [ ] The legacy flags stay in the envelope.
- [ ] Test first, on the page with supplied answers: an answer without figures shows the "being processed" state in the overview, the full view, the details table and the trends, and no card fails on a null.
- [ ] The fork specification no longer lists partial figures through a direct call as a known limit.
