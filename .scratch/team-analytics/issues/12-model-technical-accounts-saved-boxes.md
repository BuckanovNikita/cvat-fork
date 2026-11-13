# 12: Model, technical accounts and saved boxes

**What to build:** A team lead sees boxes that no person drew, beside the boxes people made, and never mixed in with them. Scripts stop appearing as people. For a legacy period the team lead gets the one box figure it can give: saved boxes. See Model, Technical account and Saved boxes in `GLOSSARY.md` and the spec (`../spec.md`).

**Blocked by:** 11 (Creation methods by people).

**Status:** ready-for-agent

- [ ] Technical accounts are a configured list that a fork maintainer can change without changing code.
- [ ] A technical account is absent from annotator lists, sessions and working time.
- [ ] Every single-frame rectangle a technical account saves counts as Model for the project it was saved in.
- [ ] A re-upload by a technical account counts again, and the page says so next to the figure.
- [ ] Boxes made with the built-in detector in the annotation view are recorded by the UI, inside an event type the stock server accepts, and count as Model for the annotator who ran it and for the project.
- [ ] Model appears as a fourth creation method with a count and a share and no time, and is never part of the Creation operation or its average.
- [ ] The headline figure for boxes created shows Model boxes beside it, not inside it.
- [ ] Saved boxes are counted per annotator and per project from what the server recorded when jobs were saved.
- [ ] For a legacy period the page shows saved boxes, labelled as all methods together.
- [ ] A failure inside the detector recording never affects the detector's result.
