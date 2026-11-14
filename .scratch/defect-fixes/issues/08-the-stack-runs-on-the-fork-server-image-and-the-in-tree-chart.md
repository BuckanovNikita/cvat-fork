# 08: The stack runs on the fork server image and the in-tree chart

**What to build:** A fresh test stack comes up from the repository alone: the chart from the import, the backend on the fork server image, and a check that the server really serves both patched policies. See "Stack and removals" in the spec (`../spec.md`).

**Blocked by:** 04 (Re-import the release with the widened filter), 07 (Fork server image).

**Status:** ready-for-agent

- [x] The launcher takes the chart from the import. The download of the upstream source archive, its cache and its settings are gone.
- [x] Chart dependencies are still built from the fork-owned lock and checked against the recorded hashes.
- [x] The release's backend image is the fork server image, for the server and every worker. The launcher refuses to start when that image is not present locally.
- [x] The render guard still refuses cluster-wide objects and pulls outside the approved list.
- [x] The run fetches the served policy bundle and checks each of the two policies by itself for the patch. It fails if either is the stock one.
- [ ] A fresh `up` from an empty namespace passes every existing check, and `down` leaves nothing behind.
- [x] The captured logs of that run contain no local path.
- [x] The stack's own description matches what the launcher now does.
- [x] The run is recorded in a dated evidence file.

## Comments

2026-11-14, part one (no cluster install). Evidence: `docs/evidence/2026-11-14-stack-fork-image-in-tree-chart.md`.

- Ticked from checks run: the chart built from the import with a fresh cache (`git grep` finds no download, archive URL, commit pin or `fetch-chart` left in the stack directory; the network was not traced), the seven archives matching `chart-deps.sha256`, the guard refusing a cluster-wide kind, an unapproved image and a forced pull in doctored renders, the README against the launcher.
- Criterion 3, not ticked: the render puts `cvat/server:v2.82.0-fork-policies` in all 11 backend containers (server, eight workers, initializer) and the launcher stops first thing when the image is absent (shown with `TA_SERVER_IMAGE=cvat/server:v0.0.0-absent run.sh preflight`), but no release ran, so the running pods' images are not seen.
- Criterion 5, not ticked: `check_policies` is called from `up`; its bundle code passed on the fork image's bundle and failed on the stock bundle and on both mixed bundles (`run.sh check-bundle` on `verify/policy_bundle.sh from-image` output), but no served bundle was fetched. Read, not run: the proxy's `/api` location has no auth subrequest and the server's `RulesView` allows anyone without authentication; with no stack, `run.sh check-policies` fails closed.
- `cvat/server:v2.82.0` stays in `TA_APPROVED_PULLS`: it is the base of the fork server and service images and the service suite runs it. The render check refuses it in the release.
- Criteria 6, 7, 9 and the outstanding parts of 3 and 5 are part two, which needs a UI image build and a stack `up`:
  1. `IMAGE=cvat/ui:v2.82.0-team-analytics ./build-ui.sh` and `IMAGE=cvat/team-analytics:v2.82.0 ./build-team-analytics-service.sh` from the final head; both images are local afterwards.
  2. `verify/policy_bundle.sh from-image cvat/server:v2.82.0-fork-policies | verify/team-analytics-stack/run.sh check-bundle` prints "policy bundle check passed" (the server image is not older than the import's policies).
  3. `verify/team-analytics-stack/run.sh preflight` on the final head prints "preflight passed"; it downloads the seven dependency archives (network; the default cache holds no build of the in-tree chart) and checks them against `chart-deps.sha256`.
  4. `kubectl --context docker-desktop get ns cvat-ta-it-$USER` reports it absent; then `verify/team-analytics-stack/run.sh up 2>&1 | tee <log>` exits 0, with "policy bundle check passed" right after the port-forward and every later check passing (criteria 5, 6).
  5. While it is up, `kubectl --context docker-desktop -n cvat-ta-it-$USER get pods -l tier=backend -o jsonpath='{..image}'` names no `cvat/server` image other than `cvat/server:v2.82.0-fork-policies`; `busybox:1.36.1` init containers also appear. Pods exist only for the server, the utils and webhooks workers and the initializer (criterion 3).
  6. `verify/team-analytics-stack/run.sh down` prints "nothing of ... remains"; afterwards `get ns` finds no namespace and `get pv` no volume bound to it (criterion 6).
  7. `grep -c -i -F "$HOME" <log>` and `grep -c -i -F "/home/$(id -un)" <log>` print 0 (criterion 7).
  8. The run is added to the evidence file above (criterion 9).

2026-11-14: Part one merged into `feat/team-analytics-page` as `220b3aa7`; `bash -n verify/team-analytics-stack/run.sh` passes on the merged tree, the launcher was not run. Part two, the fresh `up` and `down` of the live criteria, is outstanding, so the ticket stays open. Evidence: `docs/evidence/2026-11-14-stack-fork-image-in-tree-chart.md`.

2026-11-14, part two (live run, same evidence file).

- Criterion 3 shown: every backend pod of the release runs `cvat/server:v2.82.0-fork-policies` (the only other image in them is the `busybox:1.36.1` init container).
- Criterion 5 shown: `check_policies` fetched `/api/auth/rules` through the proxy on both `up` runs and found both policies patched, each by itself. The failing verdicts are part one's stock and mixed bundles; a stock bundle was not served on the stack.
- Criterion 6 not ticked. The fresh `up` from the empty namespace stopped at `check_final` on two expectations the service had outgrown (null rows of an unprocessed period, ticket 14; operation parts in each row, ticket 23); `final_run.py` is fixed in `1333fd89`. Every check then passed on that stack by its subcommand, and a second `up` on the same stack passed every check in one run. Still outstanding: an `up` from an empty namespace passing end to end, and `down` leaving nothing behind. `down` is kept for the end of the live work, since tickets 09, 10, 11, 25 and 26 use the running stack.
- Criterion 7 shown on the passing run's log. The first `up` log held the home directory in the failure's Python traceback; the launcher's stderr now passes through `redact_paths`, checked on a provoked traceback.
