# 16: A project with only technical-account boxes appears in the details table

**What to build:** A project whose only job work is boxes saved by a technical account has a row in the details table by project. Today it is missing, so automated work is invisible there. See Technical account and Saved boxes in `GLOSSARY.md` and "Service: what a read returns" in the spec (`../spec.md`).

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Test first, through the service's read interface: such a project has a row with no working time, its saved boxes and its Model boxes.
- [x] A technical account still never appears in the details table by annotator or in any list of people.
- [x] Paging, search and the project filter treat the new row like any other.
- [x] A project of another organization with only technical-account boxes does not appear.
- [x] On the page with supplied answers, such a row renders without a division by zero or an empty cell where a figure belongs.

## Comments

2026-11-14: Done on branch `ticket/16-details-row` (`f7acd00` the fix and its service tests, `e2c308a` the page test). Everything observed, and what was not verified, is in `docs/evidence/2026-11-14-details-row-technical-account.md`.

The failing observation before the fix, at the service's read interface: with a technical account's boxes saved into a project where no person worked, the details table by project listed two rows, not three.

What changed: the row set of `sql/read/details.sql` by project also holds every project with saved boxes, and `project_ids` of `sql/read/details_scope.sql` follows the same rule, because the page searches project names over that list. No Python changed and no page code changed.

Per criterion:

- 1: seen to fail, then to pass. Under Bounding boxes the row has seven saved boxes and seven Model boxes; under All shapes Model is nine and saved boxes stay seven.
- 2: the table by annotator has a new case (two annotators, no match for the account's name, no row under a filter on the new project); it passes and was never seen failing, since the fix does not touch that path. For the other lists of people there is no new case: the whole suite passed once on the branch (272 cases, default ClickHouse image), with the existing cases for the overview, the sessions, the saved boxes by annotator, the full view and the trends' candidates, and no other read file changed.
- 3: written after the fix; with the old queries the paging case and the search case fail, with the fix they pass. One part was a failing test of its own first: `project_ids` did not hold the project while the row was already listed.
- 4: passes, and was never seen failing for the other organization's project itself; the old queries fail the case only because the own project is missing. The case therefore also shows the same save listed for an administrator in instance scope.
- 5: the page already rendered such a row; the test alone is the result. It was seen to fail once, on `NaN s`, with the card changed for one run to divide working time by sessions; that change was not kept.

Not in the ticket and needed for criterion 2: a test first showed that taking saved boxes as the table counted them listed the technical account's projects under an annotator filter on its id. Under an annotator filter its saved boxes now neither list a project nor count for one.

Left as it is, see "Noticed, not changed" in the evidence file: the legacy flags of a scope that holds nothing but technical-account boxes; a project with only technical-account objects that are not boxes; the full-view list by project, whose rows come from Model objects.

2026-11-14: Merged into `feat/team-analytics-page` in merge `a095b0b`; evidence `docs/evidence/2026-11-14-details-row-technical-account.md`. The merged tree equals the branch head's tree, so the implementer's service runs stand. On the merged tree `node --test verify/team_analytics_page.cjs` passes 207 of 207 and `node --test verify/team_analytics_logging.cjs` 55 of 55, 0 skipped in each.
