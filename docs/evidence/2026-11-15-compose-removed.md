# Compose and the copied policies removed, 2026-11-15

Ticket 12 of the defect fixes (plan rows 1.4 and 1.5). Branch `ticket/12-remove-compose`,
from `feat/team-analytics-page` at `775ff76e`, merged with it again at `ccef1cc2`. The
removal is commit `2ad619ca`, the documents `d05adde1`.

## What went and what stayed

Each file was kept only if the stack (`verify/team-analytics-stack/run.sh`), the check
pipeline (`prek.toml`) or another kept file calls it. The callers were found by a search of
the tree for each name before the removal.

| Path | Decision | Why |
| --- | --- | --- |
| `docker-compose.override.yml` | removed | The Compose overlay; it mounted `opa/rules` into `cvat_server`. The import has no Compose file since the widened re-import |
| `verify/docker-compose.verify.yml` | removed | Overlay of `verify/run.sh` only |
| `verify/docker-compose.opa-issues.yml` | removed | Overlay of `verify/opa_issues.sh` only |
| `verify/docker-compose.opa-patch.yml` | removed | Mount overlay of `verify/opa_issues.sh` only |
| `verify/run.sh` | removed | Compose launcher (task progress); cannot run without the import's Compose file |
| `verify/opa_issues.sh` | removed | Compose launcher (issue permissions); same |
| `verify/seed.py` | removed | Called only by `verify/run.sh`; the stack seeds task progress with `task_progress.py` |
| `verify/mkimg.py` | removed | Called only by `verify/run.sh` and `verify/opa_issues_seed.py`; the stack makes its images in `stack_api.py` |
| `verify/opa_issues_seed.py` | removed | Called only by `verify/opa_issues.sh`; replaced by `seed_users.py` with `issue_accounts.json` |
| `verify/opa_issues_check.py` | removed | Called only by `verify/opa_issues.sh`; its matrix rows are in `issue_matrix.py` (`2026-11-14-stack-issue-matrix.md`, "Reuse of the Compose-era scripts") |
| `opa/` (`README.md`, `rules/issues.rego`, `rules/comments.rego`) | removed | The copied policies; the policies are patched in place in the import and delivered in the fork server image (ADR 0004). Nothing read `opa/` but the two Compose overlays |
| `verify/opa_issues_test.rego` | stays | The policy test's cases, run by `verify/policy_test.sh` |
| `verify/policy_test.sh` | stays | The policy test; hooks `policy-patched` and `policy-stock` |
| `verify/policy_bundle.sh` | stays | The bundle check; called by the stack (`check-policies`, `check-bundle`) |
| `verify/task_progress.cjs` | stays | Hook `task-progress` |
| `verify/team_analytics_logging.cjs`, `verify/team-analytics-logging/` | stay | Hook `ta-logging` |
| `verify/team_analytics_page.cjs`, `verify/team-analytics-page/` | stay | Hook `ta-page` |
| `verify/browser-environment.cjs` | stays | Loaded by both Team Analytics suites' helpers |
| `verify/package.json`, `verify/package-lock.json` | stay | The harness's dependencies (jsdom) |
| `verify/team_analytics_service.sh` | stays | The service seam |
| `verify/team-analytics-stack/` | stays, whole | The stack, its seeds and its checks |

## Checks with supplied boundaries

The name search runs from the worktree root over every tracked and untracked file except
`node_modules`, `.venv` and git's own directory, with history (`.scratch/`) and dated evidence
(`docs/evidence/`) excluded; the ledger is under `.scratch/`. One `grep -rnF` per name:
`docker-compose.override.yml`, `docker-compose.opa-issues.yml`,
`docker-compose.opa-patch.yml`, `docker-compose.verify.yml`, `verify/run.sh`,
`opa_issues.sh`, `verify/seed.py`, `mkimg.py`, `opa_issues_seed.py`, `opa_issues_check.py`,
`opa/rules`, `opa/README`, `` `opa/` ``, `OPA_RULES`. Run at the final commit of the ticket,
it found one hit: `docs/adr/0004-…md`, line 18, "the copied `opa/` directory and the Compose
overlay that mounted it go away". An accepted decision record, which states the removal; not
edited. `INFRA_MIGRATION.md` listed the files by name in "What is affected here"; that list is
replaced by a summary that points at the table above.

Nothing else: no script, hook, configuration, README or evergreen document names a removed
file. A case-insensitive search for `compose` over the same files outside `cvat/` and
`tools/` finds, besides that one, the ADR 0003 text and its amendment, the outcome lines of
`INFRA_MIGRATION.md` and of the root README, the fork specification's line that says the
Compose files are gone, and `docs/design/team-analytics/design.md` line 107 (below).
`grep -n -i 'compose\|mount' docs/upstream-upgrade.md` finds nothing.

The check pipeline, `nice -n19 prek run --all-files` with no hook skipped, at `130c3696` and
again at the ticket's final commit:
all nine hooks passed (ESLint, stylelint, type check, ruff, the policy test on the patched and
on the stock policies, the three frontend suites). No hook referred to a removed file.

## Not verified here

- A stack `up` after the removal. The stack was in use by another ticket; the run is
  outstanding. The removed files were not called by the stack (above), which is a reading,
  not a run.
- The documents were read against the tree, not executed: the upgrade procedure's commands
  for a next release (merge, scope review, `build-server.sh`, the bundle check against
  `cvat-${TARGET}`) have not been run for any release after v2.82.0.
- `docs/design/team-analytics/design.md` still says "two custom images" (line 95) and that the
  Compose checks "are migrated separately" (line 107). It is the feature's design record and
  not among this ticket's documents; left as written.
- The independent review of the delivery change as integrated is not part of this ticket's
  work. It followed; see the next section.

## Independent review of the delivery change, 2026-11-15

A fresh agent that had not written the changes reviewed the delivery change as integrated
(tickets 02, 03, 04, 06 on its delivery side, 07 to 13 and 25), given the owner's documents
and those merges and not the implementers' conclusions. It read and probed the tree at
`f43b8a08`, changed no tracked file, built no image and touched no cluster object. Its
doctored renders, bundles and small local upstream were reused below as failing cases.

Verdict: nothing serious for a disposable stack, but the render guard, the server image build
and the bundle check each let through inputs they were meant to stop, and the documents
overstated two checks. Nine findings, most severe first, and what the follow-up on branch
`fix/delivery-review` did (commits `da4515d8`, `c2d5bcc5`, `e7310b11`, `343933c9` and the
ticket records):

1. **The render guard misses several forms** (`- image:`, a quoted, `List`-wrapped or JSON
   kind, another namespace, a single-quoted `Always`, untagged or `latest` images, any local
   image, CRDs never rendered). Fixed. The chart is rendered with `--include-crds`; kubectl
   reads the render as objects (`kubectl label --local -f RENDER -o json` parses every YAML or
   JSON document and flattens Lists, without contacting the server), and the new
   `verify/team-analytics-stack/render_guard.py` (standard library only) judges each object:
   only an (API group, kind) the cluster lists as namespaced, no namespace other than the
   stack's, every `image` field at any depth a string on the stack's list (the approved pulls,
   the new `TA_LOCAL_IMAGES` for OPA and Vector, and the four images the launcher names), none
   untagged or `latest`, no pull policy but `IfNotPresent` or `Never`, and no image of the
   fork server image's repository other than it. `pull_images` pulls only the guard's images
   and only approved ones. No new host prerequisite: kubectl and python3 were already
   required. PyYAML and jq are on this machine but declared nowhere, so neither is used.
2. **The fork server image can be built and saved with stock policies in force.** Fixed.
   `build-server.sh` builds untagged, checks the build's bundle (the server's own builder)
   against the import's two patched files and the base's bundle against the four policy files
   of `STOCK_TAG`, and tags `IMAGE` only when both pass. On failure it removes an earlier
   image under `IMAGE` (only the tag when the image has another), removes the new build
   unless another tag names it, saves nothing and exits 1; the build cache stays.
3. **The bundle check passes duplicate entries and links.** Fixed. `verify/policy_bundle.sh`
   reads the archive's listing before extracting and refuses two entries of one name and a
   compared policy that is not a regular file; `check-stock REF` is added for the four files.
   `run.sh check-bundle` extracts only an archive that check accepted.
4. **The removal was merged before a fresh `up` and `down` on the integrated delivery.**
   Recorded in ticket 12: merged after the two live checks it waited for (tickets 09 and 10)
   had passed on the stack, and before a fresh `up` and `down`, which ticket 27's final run
   shows.
5. **Coverage the Compose launcher had and the stack lacks; `check-issue-policies` called by
   nothing.** Fixed and recorded. `preflight`, and so every `up`, runs
   `check-issue-policies patched` and `stock`; the upgrade procedure names both where the
   policies are merged. The lost live run against a stock server is recorded in ticket 09 and
   in the fork specification; no second stack was built for it.
6. **Stack sharing and the sweeper.** Sharing recorded (stack README, fork specification:
   one stack per machine user by default, `TA_RUN_ID` separates runs). The restart rule fixed
   from supported reads: the k8s-infra sweeper records the restart time of its last tick in
   `infra-janitor/last-run` (`restart_at`); `ensure_namespace` recreates a namespace created
   before it, and `status` prints the verdict. Limits: that time can lag a restart by one
   tick, k8s-infra does not yet count restart detection as proven, and without a readable
   time only the age rule applies.
7. **Stale or overstated statements.** Fixed: the upgrade procedure's "pinned upstream
   commit" and "stack's policy check" default, the fork specification's BUILD-A citation of
   the render check for content; and, of the same kind, "nowhere else fails" under Policies,
   BUILD-1's "raises no error", the render-check sentence under "Packaging and integration",
   the import tag missing from the list of defaults, and the launcher's `preflight` and `up`
   usage lines.
8. **The mirror script replaces the mirror with an empty one.** Fixed. `mirror-cvat.sh`
   refuses the swap when the filtered result has no tag, no default branch, or lacks a path
   of its `REQUIRED` list.
9. **Identifying details and secrets in tracked files.** The seed password no longer goes on
   a command line: the four `kubectl exec` seed calls pass it, with the accounts, in the seed
   script's standard input. Recorded in the fork specification: what the public repository
   shows (the seed password's default, upstream's chart passwords, the user's name in the
   namespace of older evidence, a platform path in `INFRA_MIGRATION.md`) and that gate output
   is not redacted and must not be pasted into evidence. Older evidence is not edited.

### Failing cases before, outcomes after (checks with supplied boundaries)

Each was run on the integration tip's scripts first and on this branch's after, except where
a case says its "before" was read or shown another way. The machine user's namespace in these
runs is written `cvat-ta-it-<user>`.

- Render guard, `run.sh check-render` on the reviewer's doctored copies of the real render.
  Before: accepted C (quoted kind), D (`List` of a ClusterRole), E (`- image:` unapproved),
  H (JSON ClusterRoleBinding), I (stock server image in an init container), J (`busybox`
  untagged), M (`'Always'`), N5 (local `:latest`), N6 (ConfigMap in `kube-system`), and a
  copy with a local, tagged, unlisted image. After: every one refused with its reason (B, F,
  G, K, L, N1 to N4 refused before and after). The CRD case's "before" is the render itself:
  `helm template` of the chart with its traefik subchart switched on gives 0 CRDs without
  `--include-crds` and 29 with it, so the old render never held one. A copy of the genuine
  render with one of those CRDs added is refused as a cluster-wide kind. Accepted: the genuine
  render (the reviewer's, and this branch's with CRDs included, which holds none while
  traefik is off). The Ingress render was accepted by `render_guard.py` called directly
  without the backend check, not through `apply_ingress`, which creates the Ingress.
  `run.sh preflight` at the final head passed: both `check-issue-policies` sides ("every
  expectation matches the patched policies", "… the stock policies"), the chart build and the
  render guard. `check-issue-policies` with an absent OPA image stops at once ("is not local")
  where it tried a pull before.
- Build script, on throwaway bases made from the local stock image (no pull, no push,
  network off, removed afterwards): a base whose engine rules directory is elsewhere (the
  server builds the bundle from `engine/opa_rules`) and a base whose `utils.rego` differs
  from the tag's. Before: the integration tip's `build-server.sh` built and tagged both, exit
  0; the first image's bundle has the stock policies under `opa_rules/` and no
  `rules/issues.rego`. After: both exit 1 ("missing rules/issues.rego" for the moved one,
  "DIFFERS rules/utils.rego" for the other); an earlier image placed under the target tag was
  removed, another tag of the same image stayed, and an untagged failed build was removed.
  The real image rebuilt at the merged tip passed both checks and kept its ID,
  `4b38c649ae96` (`cvat/server:v2.82.0-fork-policies`). `SAVE=1` was not run; that saving
  follows the checks was read.
- Bundle check, the reviewer's bundles. Before: `twice` (stock, then patched entries of each
  policy) and `sym` (links to the import's files) passed `policy_bundle.sh check` and
  `run.sh check-bundle`. After: both refused ("TWICE", "NOT FILE … (link)"); the fork bundle
  passes; the stock, mixed, old, one-file, empty and non-archive bundles fail as before;
  `check-stock cvat-v2.82.0-widened` passes the stock bundle and fails the fork one on the two
  policies only.
- Mirror script against small local upstreams. Before: an upstream with none of the paths,
  one without tags and one without the policy files each exited 0 and replaced the mirror
  (the first with an empty one). After: each exits 1 naming what is missing, and the earlier
  mirror stays; a complete upstream still replaces it. Every path of `REQUIRED` is in the
  import tag `cvat-v2.82.0-widened`'s tree.
- Seed password: `backend_shell` with a stand-in kubectl that records its arguments and runs
  its input as `manage.py shell` does. The script read the password and the accounts; the
  arguments held neither. The old call put the password in kubectl's arguments.
- Restart rule: `TA_NAMESPACE=sweeper-canary-20261111 run.sh status` (read only) reports that
  namespace created before the sweeper's recorded restart time; the predicate gives "no" for
  a creation time after it and "unknown" with an unreadable cluster. No "before" was run: the
  old `ensure_namespace` had only the age rule, which was read.

### What held, as the reviewer found it

The fork server image adds exactly one layer with an unchanged configuration, both files
root-owned, mode 644 and equal to the import's, and only those two differ from the stock
bundle; the build refuses an image name equal to the base and a missing base, uses no pull or
network and never pushes. The bundle check failed the stock, mixed, old, one-file, empty and
non-archive bundles and an unknown reference. The gate failed loudly on a bare checkout and
passed with its dependencies; ruff checks only the fork's Python and is pinned with a lock.
The port-forward binds the loopback address and refuses a port in use; the Ingress is
namespaced; chart dependency archives are checked against their hashes. The running stack had
no cluster-wide role or binding and ran only the fork server image and busybox. No removed
file is referenced outside history, evidence and `.scratch`.

### Not checked

- No stack command that creates anything was run by the follow-up. The new guard on a real
  `up` render with CRDs included, the password passed through standard input to a real
  backend pod, `check-issue-policies` inside `up` and the guard on the Ingress inside
  `apply_ingress` are first exercised by ticket 27's final run. The restart rule's recreate
  path was not run and a fresh stack does not run it.
- The mirror script was not run against the real upstream (no clone was allowed). It checks
  the paths on upstream's default branch, so a path moved there refuses a refresh even when
  the import targets an older tag.
- The guard checks the `helm template` render. The chart and its dependencies use
  `.Capabilities` and `lookup`, so what `helm upgrade --install` creates can differ.
- By the reviewer: an actual image build, a cold chart-dependency fetch, any live stack
  command, the policy rules themselves.
