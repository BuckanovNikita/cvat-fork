# 16: A project with only technical-account boxes appears in the details table

**What to build:** A project whose only job work is boxes saved by a technical account has a row in the details table by project. Today it is missing, so automated work is invisible there. See Technical account and Saved boxes in `GLOSSARY.md` and "Service: what a read returns" in the spec (`../spec.md`).

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Test first, through the service's read interface: such a project has a row with no working time, its saved boxes and its Model boxes.
- [ ] A technical account still never appears in the details table by annotator or in any list of people.
- [ ] Paging, search and the project filter treat the new row like any other.
- [ ] A project of another organization with only technical-account boxes does not appear.
- [ ] On the page with supplied answers, such a row renders without a division by zero or an empty cell where a figure belongs.
