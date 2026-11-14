# 08: The stack runs on the fork server image and the in-tree chart

**What to build:** A fresh test stack comes up from the repository alone: the chart from the import, the backend on the fork server image, and a check that the server really serves both patched policies. See "Stack and removals" in the spec (`../spec.md`).

**Blocked by:** 04 (Re-import the release with the widened filter), 07 (Fork server image).

**Status:** ready-for-agent

- [ ] The launcher takes the chart from the import. The download of the upstream source archive, its cache and its settings are gone.
- [ ] Chart dependencies are still built from the fork-owned lock and checked against the recorded hashes.
- [ ] The release's backend image is the fork server image, for the server and every worker. The launcher refuses to start when that image is not present locally.
- [ ] The render guard still refuses cluster-wide objects and pulls outside the approved list.
- [ ] The run fetches the served policy bundle and checks each of the two policies by itself for the patch. It fails if either is the stock one.
- [ ] A fresh `up` from an empty namespace passes every existing check, and `down` leaves nothing behind.
- [ ] The captured logs of that run contain no local path.
- [ ] The stack's own description matches what the launcher now does.
- [ ] The run is recorded in a dated evidence file.
