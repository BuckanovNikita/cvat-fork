# 05: First lint run on the fork's UI code

**What to build:** ESLint, stylelint and the type check run on the fork's UI code with upstream's own configuration for the first time, and the code passes. The findings are fixed without changing behaviour. The import cycles in the UI logging module go away by moving the function that writes a Team Analytics record into a module of its own. Every later ticket that edits UI files waits for this one, so that it is not rebased over a formatting sweep. See "Tooling" and "UI logging" in the spec (`../spec.md`).

**Blocked by:** 04 (Re-import the release with the widened filter).

**Status:** ready-for-agent

- [ ] ESLint runs with upstream's configuration on every UI file the fork added or edited, and exits clean.
- [ ] stylelint runs on the fork's style files and exits clean.
- [ ] The type check passes, resolving the workspace packages from this checkout.
- [ ] Automatic formatting fixes are committed separately from fixes made by hand.
- [ ] A finding in an upstream line the fork did not write is left alone and listed in this ticket.
- [ ] The UI logging module has no import cycle, and its callers import what they imported before.
- [ ] The three fast frontend suites pass before and after with the same tests. Nothing an annotator or a maintainer sees changes.
- [ ] The commands used are written where the fork's checks are described.
