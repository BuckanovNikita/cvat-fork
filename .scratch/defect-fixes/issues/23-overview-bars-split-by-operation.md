# 23: Overview bars split by operation

**What to build:** The overview's bars for working time by annotator and by project are split by operation, with a legend, as the prototype shows. Today they are single-colour bars and the split exists only in the full view. See Overview and Full view in `GLOSSARY.md` and "Page" in the spec (`../spec.md`).

**Blocked by:** 05 (First lint run on the fork's UI code), 14 (Unprocessed periods carry no figures).

**Status:** ready-for-agent

- [ ] Test first, through the service's read interface: each overview row by annotator and by project carries its operation parts, and they equal that row in the full view.
- [ ] The remainder row carries the parts of the rows it stands for.
- [ ] For a period that is not fully processed the parts are null like every other figure.
- [ ] In a legacy period the split follows what the full view shows for that period.
- [ ] The overview asks no extra question per row.
- [ ] Test first, on the page with supplied answers: the two cards draw each bar as segments in the full view's colours, with a legend, and still show the row's working time.
- [ ] The look beside the prototype is checked in a browser in ticket 27.
