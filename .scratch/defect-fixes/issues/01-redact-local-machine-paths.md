# 01: Redact local machine paths

**What to build:** No tracked file and no captured run log shows a path of the machine the work was done on. The five tracked lines that carry one are redacted, and the stack launcher stops such a path from reaching a captured log. History is not rewritten; that is the owner's decision. See "Tooling" in the spec (`../spec.md`).

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] A search of the whole tracked tree for the local home prefix, binary files included, finds nothing.
- [ ] The four run logs of the 2026-11-14 final run and the infrastructure migration note keep their meaning; only the path is replaced by a placeholder.
- [ ] The launcher filters Helm's symbolic-link warning on every Helm call, not only when it renders the chart.
- [ ] A captured log of one launcher command that calls Helm contains no local path. A full stack run is not needed for this.
- [ ] No commit is rewritten.
