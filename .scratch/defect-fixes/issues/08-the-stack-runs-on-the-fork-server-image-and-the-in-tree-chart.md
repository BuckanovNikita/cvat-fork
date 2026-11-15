# 08: The stack runs on the fork server image and the in-tree chart

**What to build:** A fresh test stack comes up from the repository alone: the chart from the import, the backend on the fork server image, and a check that the server really serves both patched policies. See "Stack and removals" in the spec (`../spec.md`).

**Blocked by:** 04 (Re-import the release with the widened filter), 07 (Fork server image).

**Status:** resolved

- [x] The launcher takes the chart from the import. The download of the upstream source archive, its cache and its settings are gone.
- [x] Chart dependencies are still built from the fork-owned lock and checked against the recorded hashes.
- [x] The release's backend image is the fork server image, for the server and every worker. The launcher refuses to start when that image is not present locally.
- [x] The render guard still refuses cluster-wide objects and pulls outside the approved list.
- [x] The run fetches the served policy bundle and checks each of the two policies by itself for the patch. It fails if either is the stock one.
- [x] A fresh `up` from an empty namespace passes every existing check, and `down` leaves nothing behind.
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

2026-11-15: Part two merged into `feat/team-analytics-page` as `be348e32`; on the merged tree `bash -n verify/team-analytics-stack/run.sh`, `py_compile` of `final_run.py` and `prek run --all-files` pass, the launcher was not run. Criterion 6 is outstanding (an `up` from an empty namespace passing end to end, and `down` leaving nothing behind), shown at the end of the live work, so the ticket stays open. Evidence: `docs/evidence/2026-11-14-stack-fork-image-in-tree-chart.md`.

2026-11-15: Changed by the follow-up to the independent review of the delivery change (branch `fix/delivery-review`, findings 1, 3, 5, 6 and 9). The render is made with CRDs included and judged as objects (`render_guard.py` on kubectl's reading of it): namespaced kinds only, the stack's namespace only, every image field on the stack's list (approved pulls, `TA_LOCAL_IMAGES`, the launcher's four images), no untagged or `latest` image, no forced pull, the fork server image as the only server image. `check-bundle` extracts only an archive the bundle check accepted. `preflight`, and so `up`, runs `check-issue-policies` on both sides. The seed scripts receive the password through standard input. A namespace created before the cluster's last restart (the sweeper's `restart_at`) is recreated. Shown without a cluster change: the reviewer's doctored renders refused, the genuine render accepted, `preflight` passed. Criterion 4 (the guard) still holds as written. Ticket 27's final run on a fresh stack exercises for the first time: the new guard on a real `up` render with CRDs included, the password passed the new way to a real backend pod, `check-issue-policies` inside `up`, the guard on the Ingress inside `apply_ingress`, and the restart reading on a second `up` of the same namespace (a namespace created after the restart is kept; the recreate path itself stays unrun). Evidence: `docs/evidence/2026-11-15-compose-removed.md`, "Independent review of the delivery change".

2026-11-15: Changed by the follow-up to the review of the follow-ups (branch `fix/last-review`, findings 1 and 4). The render guard also refuses a Service other than ClusterIP or with external IPs, host networking, PID or IPC, a host port, a host path volume, privileged mode, added capabilities, and a RoleBinding to a ClusterRole or to a subject other than a ServiceAccount of the namespace; the genuine render holds none and is accepted, the reviewer's three doctored renders are refused. The service's and the proxy's manifests now pass the guard before they are applied (`render-service` and `render-proxy` print them); each, judged alone as those functions judge it, is accepted and a copy with a NodePort or LoadBalancer Service is refused; the functions themselves were not run inside an `up`. `check-bundle` refuses a link anywhere in a bundle and two spellings of one name. Criterion 6 stays outstanding. Evidence: `docs/evidence/2026-11-15-integrated-branch-review.md`, "Review of the follow-ups".

2026-11-15: Criterion 6 shown in ticket 27's final run (evidence: `docs/evidence/2026-11-15-final-run-on-a-fresh-stack.md`). From an empty namespace, with the three images built from `b8521e3f`, a fresh `up` passed every existing check from start to finish on its second attempt; the first stopped at a 429 from CVAT's sign-in throttle after the volume's hundred sign-ins, a fault in the launcher fixed in `d61dd877`, after which the namespace was deleted and `up` repeated from an empty one. `down` then left nothing behind: no namespace, no Ingress for the host, none of the five volumes, no port-forward or listener on 8490, no state directory.

2026-11-15: Resolved on `feat/team-analytics-page` by merge `ba33aeb4` (ticket 27's final run); the fresh `up` that passed from start to finish and the `down` that left nothing are in `docs/evidence/2026-11-15-final-run-on-a-fresh-stack.md`.
