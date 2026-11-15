# Definitions at the end of the overview, 2026-11-14

Ticket 24 of the defect fixes
(`.scratch/defect-fixes/issues/24-definitions-at-the-end-of-the-overview.md`).

The design asks for short definitions at the end of the overview and the
prototype shows four. The page had none.

## Changed

- `cvat/cvat-ui/src/components/team-analytics-page/definitions.tsx`: the
  block, with Session, Working time, Time per operation and Model, worded from
  `GLOSSARY.md`.
- `cvat/cvat-ui/src/components/team-analytics-page/definitions.scss`: its
  styles.
- `cvat/cvat-ui/src/components/team-analytics-page/team-analytics-view.tsx`:
  one import and one line that mounts the block after the details table, in
  the overview only.
- `verify/team-analytics-page/definitions.test.cjs`: the seam 3 tests.
- No service code and no new package.

## Observed at seam 3, with supplied service answers

`node --test verify/team_analytics_page.cjs` mounts the whole page in jsdom
against supplied answers. Both new tests were written first and seen to fail:

| Test | Failure seen before the block | After |
| --- | --- | --- |
| The overview ends with the definitions, after the details table, with the exact text of each | "the definitions are on the overview" | passes |
| The overview has them; a full view by annotator and a trend's full view show none | "the overview has them" | passes |

The whole seam 3 suite passes after the change, with nothing skipped.

## Stated checks

- Wording: a one-off script compared each rendered sentence with
  `GLOSSARY.md`. Seven are verbatim. Two are composed from glossary entries:
  "A pause longer than five minutes ends it" (Session with the session gap
  inlined) and "A pause longer than 100 seconds before an action belongs to no
  operation" (Idle pause). The differences from the prototype are listed in the
  ticket.
- ESLint on `definitions.tsx` and `team-analytics-view.tsx`, stylelint on
  `definitions.scss`, and the UI type check, with the commands of section 4
  of `docs/upstream-upgrade.md`: no finding. The type check ran in a worktree,
  so it read the workspace packages from the main checkout.

## Not verified

- The stylesheet was not compiled. Seam 3 loads stylesheets as empty modules
  and stylelint only parses them. The variables it uses come from `base`, and
  the page's other stylesheets use them too.

- The narrow window. The block is the last child of the overview grid. Its
  styles span the grid, set `min-width: 0`, lay the items out with
  `repeat(auto-fit, minmax(min(100%, 280px), 1fr))`, and wrap long words. No
  browser rendered it. Ticket 27 compares the page with the prototype at
  1400 px and 400 px. It should check that at 400 px the definitions are one
  column, inside the page's column, with no sideways scroll, and that at
  1400 px they sit in several columns below the details table.

## Independent review, 2026-11-15

This ticket was reviewed together with ticket 23; the review, its findings and
what was done are in
`docs/evidence/2026-11-14-overview-bars-split-by-operation.md`
("Independent review, 2026-11-15"). For this ticket: the definitions held
(worded from the glossary, no figures, overview only). One finding is recorded,
not changed: a row whose operation time exceeds its working time draws parts
that add up to more than its working time, beside the definition that every
breakdown of time adds up to it. The limit is in `docs/fork-specification.md`
("Known limit of the split by operation"); the wording is an open decision for
the owner.
