# 25: The detector record comes from the real UI on the stack

**What to build:** On the test stack an annotator uses the detector in the real UI, and the UI itself sends the detector record. Until now the run posted a hand-made record through the API. The model's answer is supplied at the HTTP boundary in the browser; a deployed model function stays unverified. That is a default the owner was not asked about. See Model in `GLOSSARY.md` and "Testing Decisions" in the spec (`../spec.md`).

**Blocked by:** 08 (The stack runs on the fork server image and the in-tree chart).

**Status:** resolved

- [x] In the stack's browser run the annotator opens the detector in the real UI. Only the model list and the model's answer are supplied; nothing else is replaced.
- [x] The UI creates the objects and sends the detector record through the real events API. The record that arrives in ClickHouse has the number of objects created and how many are bounding boxes.
- [x] After a refresh, the Model figures of that project equal the objects created, with counts and no time.
- [x] When the detector returns nothing, no record is sent.
- [x] The run no longer posts a hand-made detector record.
- [x] The evidence says plainly that the model's answer was supplied and that a deployed model function was not exercised.

## Comments

2026-11-15: One `run.sh check-final` on the running stack showed all six criteria (project
54 in `ta-org-c`; the whole final run passed). The evidence is in
`docs/evidence/2026-11-15-detector-record-from-real-ui.md`. The browser supplies three
requests: `HEAD /api/lambda/functions`, `GET /api/lambda/functions` and
`POST /api/lambda/functions/<id>`. One other `/api/lambda/` request was made,
`GET /api/lambda/requests` from the tasks page, and it went to the real server. "Model
figures equal the objects created" is read as follows: the project's Model is the detector's
objects plus the technical account's boxes, and `ta-worker-c`'s Model in the details holds
the detector's objects alone. A deployed model function stays unverified (spec default
(e)). New narrow subcommand: `run.sh check-final-ui`.
- 2026-11-15: Merged into `feat/team-analytics-page` as `1a45bdec`, with no conflict. On the merged tree `bash -n` on `run.sh`, `py_compile` on `final_run.py` and `node --check` on `final_browser.cjs` passed; no launcher command was run by the merger. All six criteria were ticked from live runs; the ticket is resolved. Evidence: `docs/evidence/2026-11-15-detector-record-from-real-ui.md`.
