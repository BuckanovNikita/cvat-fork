# 04: Re-import the release with the widened filter

**What to build:** The import gains upstream's lint configuration, the Helm chart and the four stock policy files, and loses the Compose file, in one re-import of the current release. From this ticket on the two Compose launchers cannot run: Compose is no longer used, their files are removed in ticket 12, and their checks return on the Kubernetes stack in tickets 09 and 10. See "Import" in the spec (`../spec.md`) and the amendments of ADR 0003.

**Blocked by:** 03 (Prove the widened import's path list).

**Status:** ready-for-agent

- [ ] The mirror is rebuilt with the path list proven in ticket 03, unchanged, and the current release is pulled into the import from it.
- [ ] Every path the import held before, except the Compose file, is unchanged by the pull, the fork's own edits included.
- [ ] Every new path equals the recorded upstream commit byte for byte.
- [ ] The existing release tags still point at the earlier filtered commit. The new filtered commit has its own tag, and the documented way to list the fork's changes inside the import compares against that tag.
- [ ] The old and new identifiers of the import are recorded in a dated baseline evidence file.
- [ ] The UI image builds from the import as before.
- [ ] The three fast frontend suites and the type check pass.
