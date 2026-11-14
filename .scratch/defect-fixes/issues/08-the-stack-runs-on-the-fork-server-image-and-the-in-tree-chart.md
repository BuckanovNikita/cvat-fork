# 08: The stack runs on the fork server image and the in-tree chart

**What to build:** A fresh test stack comes up from the repository alone: the chart from the import, the backend on the fork server image, and a check that the server really serves both patched policies. See "Stack and removals" in the spec (`../spec.md`).

**Blocked by:** 04 (Re-import the release with the widened filter), 07 (Fork server image).

**Status:** ready-for-agent

- [x] The launcher takes the chart from the import. The download of the upstream source archive, its cache and its settings are gone.
- [x] Chart dependencies are still built from the fork-owned lock and checked against the recorded hashes.
- [ ] The release's backend image is the fork server image, for the server and every worker. The launcher refuses to start when that image is not present locally.
- [x] The render guard still refuses cluster-wide objects and pulls outside the approved list.
- [ ] The run fetches the served policy bundle and checks each of the two policies by itself for the patch. It fails if either is the stock one.
- [ ] A fresh `up` from an empty namespace passes every existing check, and `down` leaves nothing behind.
- [ ] The captured logs of that run contain no local path.
- [x] The stack's own description matches what the launcher now does.
- [ ] The run is recorded in a dated evidence file.

## Comments

2026-11-14, part one (no cluster install). Evidence: `docs/evidence/2026-11-14-stack-fork-image-in-tree-chart.md`.

- Ticked from checks run: the chart built from the import with a fresh cache (no download left in the launcher), the seven archives matching `chart-deps.sha256`, the guard refusing a cluster-wide kind, an unapproved image and a forced pull in doctored renders, the README against the launcher.
- Criterion 3, not ticked: the render puts `cvat/server:v2.82.0-fork-policies` in all 11 backend containers (server, eight workers, initializer) and the launcher stops first thing when the image is absent (shown with `TA_SERVER_IMAGE=cvat/server:v0.0.0-absent run.sh preflight`), but no release ran, so the running pods' images are not seen.
- Criterion 5, not ticked: `check_policies` is called from `up`; its bundle code passed on the fork image's bundle and failed on the stock bundle and on both mixed bundles (`run.sh check-bundle` on `verify/policy_bundle.sh from-image` output), but no served bundle was fetched.
- `cvat/server:v2.82.0` stays in `TA_APPROVED_PULLS`: it is the base of the fork server and service images and the service suite runs it. The render check refuses it in the release.
- Criteria 6, 7, 9 and the outstanding parts of 3 and 5 are part two, which needs a UI image build and a stack `up`:
  1. `IMAGE=cvat/ui:v2.82.0-team-analytics ./build-ui.sh` and `IMAGE=cvat/team-analytics:v2.82.0 ./build-team-analytics-service.sh` from this branch; both images are local afterwards.
  2. `kubectl --context docker-desktop get ns cvat-ta-it-$USER` reports it absent; then `verify/team-analytics-stack/run.sh up 2>&1 | tee <log>` exits 0, with "policy bundle check passed" right after the port-forward and every later check passing (criteria 5, 6).
  3. While it is up, `kubectl --context docker-desktop -n cvat-ta-it-$USER get pods -l tier=backend -o jsonpath='{..image}'` shows only `cvat/server:v2.82.0-fork-policies` (criterion 3).
  4. `verify/team-analytics-stack/run.sh down` prints "nothing of ... remains"; afterwards `get ns` finds no namespace and `get pv` no volume bound to it (criterion 6).
  5. `grep -c -i -F "$HOME" <log>` and `grep -c -i -F "/home/$(id -un)" <log>` print 0 (criterion 7).
  6. The run is added to the evidence file above (criterion 9).
