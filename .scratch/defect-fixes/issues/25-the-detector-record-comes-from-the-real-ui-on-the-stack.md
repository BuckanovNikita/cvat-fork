# 25: The detector record comes from the real UI on the stack

**What to build:** On the test stack an annotator uses the detector in the real UI, and the UI itself sends the detector record. Until now the run posted a hand-made record through the API. The model's answer is supplied at the HTTP boundary in the browser; a deployed model function stays unverified. That is a default the owner was not asked about. See Model in `GLOSSARY.md` and "Testing Decisions" in the spec (`../spec.md`).

**Blocked by:** 08 (The stack runs on the fork server image and the in-tree chart).

**Status:** ready-for-agent

- [ ] In the stack's browser run the annotator opens the detector in the real UI. Only the model list and the model's answer are supplied; nothing else is replaced.
- [ ] The UI creates the objects and sends the detector record through the real events API. The record that arrives in ClickHouse has the number of objects created and how many are bounding boxes.
- [ ] After a refresh, the Model figures of that project equal the objects created, with counts and no time.
- [ ] When the detector returns nothing, no record is sent.
- [ ] The run no longer posts a hand-made detector record.
- [ ] The evidence says plainly that the model's answer was supplied and that a deployed model function was not exercised.
