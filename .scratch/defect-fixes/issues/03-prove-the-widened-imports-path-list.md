# 03: Prove the widened import's path list

**What to build:** The import filter can be widened only once without changing the import's identifiers again. Before that happens, the candidate files are shown to be sufficient in a scratch copy taken at the recorded upstream commit, and the mirror script is made safe to rerun. See "Import" in the spec (`../spec.md`); the candidate path list is in `../plan.md`.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] The candidate paths are fetched at the recorded upstream commit of the current release into a scratch directory outside the repository. The import is not touched.
- [ ] ESLint and stylelint load upstream's configuration on the fork's UI paths using only files the widened import will hold. Any further file they turn out to need is added to the path list.
- [ ] The formatting-only change in the imported ClickHouse setup file is reverted, so that file equals upstream's.
- [ ] The chart from the candidate tree, rendered with the stack's values, equals the render of the cached chart the stack uses today. Any difference is explained.
- [ ] The existing policy test passes against the four stock policy files of the candidate tree, with the stock expectations.
- [ ] The mirror script builds the new mirror beside the existing one and replaces it only on success.
- [ ] The final path list and the three results are recorded in a dated evidence file.
- [ ] Nothing else in the import changes in this ticket.
