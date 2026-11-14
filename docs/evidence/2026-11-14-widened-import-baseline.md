# The import re-filtered with the widened path list, 2026-11-14

CVAT v2.82.0 was imported again into `cvat/`, from a mirror filtered with the
widened path list of `mirror-cvat.sh` (proven in
[the widened import proof](2026-11-14-widened-import-proof.md)). The release
is the same; the import gains upstream's lint configuration, the Helm chart
and the four stock policy files, and loses the Compose file. This file records
the identifiers before and after and what was checked. The
[baseline of 2026-11-13](2026-11-13-fork-baseline.md) still describes the
earlier filter.

## Identifiers

| Item | Before (narrow filter) | After (widened filter) |
| --- | --- | --- |
| Upstream release and raw commit | `v2.82.0`, `02bd74fde78e00f770b7dfc3c33761ad9ab00095` | the same |
| Filtered upstream commit | `6545b83e7f340c3f16bc37094eeee398cdbfb76b` | `361a0e643e61537fee55bef2fab90d736c6c9ec9` |
| Local tag of the filtered commit | `cvat-v2.82.0` and `v2.82.0` (unchanged) | `cvat-v2.82.0-widened` (new, local, not pushed) |
| Tree of the filtered commit | `6d4ee564079fdc5670e8f04733a2603cad9b2049` | `f09b92afccae160a840162d78ab5500285d55c2a` |
| History of the filtered commit | one commit, no parent, as stored in this repository (the old mirror's `packed-refs` and filter records name only `v2.74.1`; its other refs were not read) | 2834 commits, in the new mirror |
| Squashed snapshot | `5e5af81d59b9883f33d4d5f4c2c65dd0bf9e0af2` | `2137ba86d292f167f30b3335041f2d480b2e587d` (parent `5e5af81`) |
| Subtree merge | `7ba828c4d095a6e4b3947087e89c7b0912fcc4d0` | `a135a65d047da5748b026ebc5a212478a236dc61` |
| Import tree (`HEAD:cvat`) just before and after the merge | `8dbf3057a9b0ba1b84b9128f832f0bc87588ad54` | `de6c7244623d03725b08b34ecfab46e3d51385d3` |
| Entries in the import | 984 | 1033 |

Raw-to-filtered mapping, read from the new mirror's own record
(`filter-repo/commit-map` and `ref-map`):
`02bd74fde78e00f770b7dfc3c33761ad9ab00095` to
`361a0e643e61537fee55bef2fab90d736c6c9ec9`, `refs/tags/v2.82.0`. The 2026-11-13
baseline had the raw commit only as recorded provenance; here it comes from
the filter run on a fresh clone of upstream.

The widened tag was created by
`git fetch --no-tags .cvat-mirror.git refs/tags/v2.82.0:refs/tags/cvat-v2.82.0-widened`.
The name sits beside `cvat-v2.82.0` and says which filter it belongs to.

## What ran

### The mirror

`mirror-cvat.sh` with the new `PATHS` (the proven list, compared line by line,
same order) built `.cvat-mirror.git` in the ticket's worktree from a full clone
of upstream, at low priority with two pack threads. It exited 0 and left
nothing beside the mirror. The mirror is 56 MB and holds 173 branches and 164
tags.

| Check in the mirror | Result |
| --- | --- |
| Root tree of `v2.82.0` | `f09b92af…`, the id computed in the proof from upstream's own listing |
| `git ls-tree -r v2.82.0` against the upstream commit's listing for the 24 paths (mode, blob id, path) | identical, 976 entries |
| `helm-chart/analytics` | mode 120000, target `../components/analytics/` |

### The pull

The documented command was tried first, on a detached HEAD, so the branch did
not move:

- `git subtree pull --prefix cvat .cvat-mirror.git v2.82.0 --squash` accepted
  the re-filtered mirror. Its snapshot had the expected tree, parent `5e5af81`
  and `git-subtree-split: 361a0e64…`, and the merge left the same import tree
  as the one recorded above. A second pull of the same tag printed
  `Subtree is already at commit 361a0e643e61537fee55bef2fab90d736c6c9ec9.`
  and changed nothing. The local tags were unchanged.
- But its snapshot message was 2841 lines, the subject of every commit of
  the re-filtered history (the old split is not an ancestor of the new one),
  and `git subtree` writes that message itself, so it cannot carry the commit
  trailers the repository requires. That trial was discarded.

On the branch the snapshot was written the way `git subtree` writes it
(`git commit-tree` of the new tree with the previous snapshot as parent, the
two `git-subtree-` lines and the trailers), then merged with
`git merge --no-ff -Xsubtree=cvat`, as `git subtree` merges. The procedure is in
[the upgrade procedure](../upstream-upgrade.md), section 2. Afterwards the
documented `git subtree pull --prefix cvat .cvat-mirror.git v2.82.0 --squash`
printed `Subtree is already at commit 361a0e643e61537fee55bef2fab90d736c6c9ec9.`,
exit 0, with no new commit and a clean tree. So later pulls find this snapshot
and start from it.

### Checks after the merge

| Check | Result |
| --- | --- |
| `git diff --name-status HEAD^1 HEAD` | 1 deleted (`cvat/docker-compose.yml`), 50 added, nothing modified, nothing outside `cvat/` |
| The 983 entries the import held before, without the Compose file (mode and blob id, the fork's edits included) | all 983 unchanged |
| The 50 new entries against the upstream commit's listing (mode and blob id) | all 50 equal |
| The 50 checked-out files against the scratch copy of upstream's archive, byte for byte (a link by its target) | all 50 identical |
| `git diff --name-status cvat-v2.82.0-widened HEAD:cvat` against `git diff --name-status cvat-v2.82.0 HEAD:cvat` before the pull | identical: 74 lines, 57 added and 17 modified UI files, all under `cvat-ui/` |
| `cvat/helm-chart/analytics` | mode 120000 in the index, a link in the working tree, target `../components/analytics/`, resolves to `cvat/components/analytics`; the only link in the import |
| `git show-ref --tags` before and after | one line added (`cvat-v2.82.0-widened`); `v2.82.0` and `cvat-v2.82.0` still at `6545b83e…`, `v2.74.1` and `cvat-v2.74.1` still at `eb9eca2f…` |
| The new files searched for e-mail addresses | none |
| UI build inputs (`cvat-ui`, `cvat-core`, `cvat-data`, `cvat-canvas`, `cvat-canvas3d`, `package.json`, `yarn.lock`, `Dockerfile.ui`, `.dockerignore`) | unchanged by the merge |

### Frontend checks, same results before and after the pull

| Check | Result |
| --- | --- |
| `node --test verify/team_analytics_page.cjs` | 206 pass, 0 skipped |
| `node --test verify/team_analytics_logging.cjs` | 55 pass, 0 skipped |
| `node --test verify/task_progress.cjs` | 20 pass, 1 skipped (the browser check, no `BROWSER_BIN`) |
| `tsc -p cvat-ui/tsconfig.json` from `cvat/` | exit 0, no output |

## Supplied boundaries

- The suites and the type check ran with `cvat/node_modules` and
  `verify/node_modules` linked to the main checkout's installed packages; the
  workspace packages resolve through that link to the main checkout's copies.
  The pull changed no file they read.
- The upstream listing compared against is the one ticket 03 fetched from the
  hosting service's API for the raw commit; the archive copy is the one ticket
  03 checked against it.

## Not verified

- The two Compose launchers (`verify/run.sh`, `verify/opa_issues.sh`) no
  longer have `cvat/docker-compose.yml` and cannot run. That is expected; they
  are removed later and their checks move to the Kubernetes stack.
- ESLint and stylelint with the imported configuration, the policy test with
  the imported policies, and an install of the in-tree chart: later tickets.
- That a mirror rebuilt later, or elsewhere, gives the same filtered commit id.
  The tree id depends only on the paths; the commit id also depends on the
  history the clone held. Compare both with the table above before tagging.
- Pushing: the new tag and the mirror are local. The branch carries only the
  snapshot and the merge, not the 2834-commit filtered history behind the tag.

## UI image build, 2026-11-15

Run after the machine was free, from the integration branch at `3dc1a7bc`
(the import as re-pulled, with the fork's later UI changes):
`IMAGE=cvat/ui:v2.82.0-team-analytics ./build-ui.sh`. It exited 0 on
`node:24.19.0-slim` and left image `sha256:310e9bbc6a47`. Its log holds no
error line and no local path.

This shows that the image builds from the widened import. It does not show the
image in a browser; the stack run of ticket 08 is the first to serve it.
