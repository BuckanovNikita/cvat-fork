# The widened import's path list, proven in a scratch copy, 2026-11-14

The import filter is to be widened once (decision 4 of
`.scratch/defect-fixes/plan.md`). Before that, the candidate paths were taken
at the recorded upstream commit into a scratch directory outside the
repository and tried with the tools that will use them. This file records the
final path list and what the trial showed. The filter itself was not run: the
mirror, the import's tags and the `cvat/` subtree are as they were, except for
one file restored to upstream's content (below).

| Item | Value |
| --- | --- |
| Upstream commit (tag `v2.82.0`) | `02bd74fde78e00f770b7dfc3c33761ad9ab00095` |
| Fork branch and commit the trial ran on | `ticket/03-import-proof`, `65e2221` |
| Import tree of that commit (`HEAD:cvat`) | `8dbf3057a9b0ba1b84b9128f832f0bc87588ad54` |
| Recorded import tree of the current filter (`cvat-v2.82.0`) | `6d4ee564079fdc5670e8f04733a2603cad9b2049` |
| Root tree the widened filter should leave at the tag (computed, see below) | `f09b92afccae160a840162d78ab5500285d55c2a` |

## The path list

Twenty-four paths. The first twelve are the current list without
`docker-compose.yml`; the other twelve are new.

```text
.yarnrc.yml
package.json
yarn.lock
.dockerignore
LICENSE
Dockerfile.ui
cvat-data
cvat-core
cvat-canvas
cvat-canvas3d
cvat-ui
components
eslint.config.mjs
.eslintrc.cjs
tests/.eslintrc.js
.stylelintrc.json
.prettierrc
.prettierignore
.editorconfig
helm-chart
cvat/apps/engine/rules/issues.rego
cvat/apps/engine/rules/comments.rego
cvat/apps/iam/rules/utils.rego
cvat/apps/organizations/rules/organizations.rego
```

One path was added to the list of the plan: `tests/.eslintrc.js`. Upstream's
`eslint.config.mjs` loads that file when the configuration is evaluated, so
without it ESLint lints nothing (result 1). Nothing else under `tests/` is
needed. `PATHS` in `mirror-cvat.sh` still holds the old list; applying this
one is the re-import's first step.

## The scratch copy

- Upstream's source archive for the commit was downloaded once. The commit id
  embedded in the archive is the recorded one.
- The commit's own file listing (paths, modes, blob ids) was fetched from the
  hosting service's API in one request. The archive holds 31 entries fewer
  than the commit: `.gitattributes`, `.gitignore`, `.gitmodules`, everything
  under `.github/`, four nested `.gitignore` files and the documentation
  theme's submodule. None of them is in the path list.
- The twenty-four paths were extracted from the archive: 976 entries, of which
  926 are what the current filter keeps at the tag without the Compose file
  and 50 are new (39 under `helm-chart/`, eleven single files). Every entry
  was hashed and compared, with its mode, against the commit's listing. All
  976 match and none is missing.
- From the listing, the root tree a path filter leaves at this commit was
  computed. For the current path list it comes out as the recorded import
  tree, which checks the method. For the widened list it is the id in the
  table above. The re-import can compare the tree of its new filtered tag with
  it.
- The candidate tree is the import as it should be after the re-import: the
  `cvat/` tree of the branch commit above without `docker-compose.yml`, plus
  the twelve new paths. It differs from the plain extraction only in the UI
  files the fork edited (17) or added (57). It has no dangling link. Its one
  link is `helm-chart/analytics`, pointing at `../components/analytics/`,
  which inside the import is `cvat/components/analytics/`.
- For the lint runs the candidate tree got a `node_modules` link to the
  packages installed in the main checkout, and nothing else.

## Results

### 1. Lint configuration

ESLint 10.3.0 and stylelint 15.11.0, the versions installed in the main
checkout, were run from the root of the candidate tree on every UI file the
fork added or edited
(`git diff --name-only --diff-filter=AM cvat-v2.82.0 HEAD:cvat -- cvat-ui`):
65 TypeScript files and 9 style files.

| Run | ESLint | stylelint |
| --- | --- | --- |
| Tree with the plan's list (no `tests/.eslintrc.js`) | exit 2, no file linted: `Cannot find module './tests/.eslintrc.js'`, required by `eslint.config.mjs` | not affected |
| Candidate tree | exit 1: all 65 files have a result, none failed to parse; 25 errors and 7 warnings in 15 files | exit 2: all 9 files have a result, no syntax or configuration error; 7 findings in 5 files |
| Control: `eslint.config.mjs` and `.stylelintrc.json` removed from a copy of the tree | exit 2: no configuration file found | exit 78: no configuration provided |

ESLint exits 2 when it cannot run and, with `--exit-on-fatal-error` as used
here, when a file cannot be parsed; 1 means rule findings only. stylelint
exits 2 on findings and 78 on a configuration error. So in the candidate tree
both configurations load and both tools reach every file. The control shows
that no configuration outside the tree stands in for the tree's own: no
directory above the scratch tree holds a package, a `node_modules` or a lint
configuration.

The findings are not fixed here; they belong to the first lint run
(ticket 05). ESLint: `object-curly-newline` 12, `max-len` 9,
`@stylistic/indent` 2, `@typescript-eslint/explicit-function-return-type` 2,
`no-use-before-define` 1, `no-param-reassign` 1, and five unused
`eslint-disable` comments; 19 of the 32 are fixable automatically. stylelint:
`alpha-value-notation` 4, `scss/double-slash-comment-empty-line-before` 3. No
rule reported an import cycle.

`.prettierrc`, `.prettierignore` and `.editorconfig` are read by neither tool.
They are in the list by the owner's decision and were only checked to be the
commit's files.

### 2. Chart

The candidate chart was copied with `components/` beside it, the fork's
`verify/team-analytics-stack/Chart.lock` was added as the launcher adds it,
and `helm dependency build` (Helm 3.16.3) downloaded the seven locked
dependencies. All seven archives equal `chart-deps.sha256`. Helm followed the
`analytics` link into `components/analytics/`.

The chart was then rendered with the launcher's arguments (`values.yaml`, the
frontend image and Grafana's root address) and compared with a render of the
cached chart the stack uses today.

| Comparison | Result |
| --- | --- |
| Cached chart rendered twice | 7841 lines, 53 objects each; two lines differ |
| Cached chart against candidate chart | the same two lines differ, nothing else |
| All renders with those two lines masked | identical |

The two lines are the Grafana subchart's generated administrator password
(its Secret) and the checksum of that Secret on the Grafana Deployment. They
change on every render of the same chart, so they say nothing about the
candidate. Apart from them the candidate chart renders exactly as the cached
one.

The render does not depend on the ClickHouse setup file. Through its link the
chart reads only Vector's `*.toml` files and Grafana's dashboards, and no
template names `init.py`. A render with the setup file as it was before the
revert is identical too. The plan gave "the in-tree chart will ship that
directory" as the reason for the revert; that holds for the directory, not for
this file.

### 3. Policy test

`verify/opa_issues_test.rego` was run in the local `openpolicyagent/opa:1.12.2`
image (the version the chart deploys), without network, against the four
policy files of the candidate tree and a data file holding
`{"expected":{"patched":false}}`:

- stock expectations: 12 of 12 test rules pass;
- control, the same files with the test's default (patched) expectations: 2 of
  12 fail, `test_unassigned_member_actions` and `test_list_filter_contract`,
  the two that tell the patch from the stock policies.

The four files import only each other (`utils`, `organizations`) and
`rego.v1`, so the test needs no further policy file.

### 4. The ClickHouse setup file

`cvat/components/analytics/clickhouse/init.py` was restored from the filtered
tag in commit `1babeb3`. Its blob id is now the upstream commit's
(`f587a3e98a6a64821c38cbd9a8a5d0e4fb981f3a`). With that, the fork's changes
inside the import are the UI files only: outside `cvat-ui/`,
`git diff --name-status cvat-v2.82.0 HEAD:cvat` lists nothing.

### 5. The mirror script

`mirror-cvat.sh` (commit `65e2221`) clones and filters in
`.cvat-mirror.git.new` beside the existing mirror and renames it over
`.cvat-mirror.git` only after both steps succeeded. It was checked without the
network, in a worktree that holds no real mirror, with `UPSTREAM` pointing at
two small local repositories.

| Case | Before the change | After the change |
| --- | --- | --- |
| The clone fails (no such source) | the existing mirror is gone | exit not zero; the existing mirror keeps its refs, trees and a marker file; nothing is left beside it |
| The run fails after a good clone | the existing mirror is replaced by an unfiltered clone | with `python3` replaced by a failing stub, so that the filter fails: the same as above |
| A directory left by a killed run, then a good run from the second repository | not applicable | exit 0; the mirror holds the second repository, filtered; the old one is gone; nothing is left beside it; `git status` shows nothing |

The old script could not reach its filter on a local repository, because of a
second fault: a source holding only branches and tags ended the run after the
clone, with exit 1 and an unfiltered mirror in place (the search for other
refs found none, and its status ended the script). That is the failure after a
good clone seen in the middle column. The script built the current mirror from
the real upstream, so that source must hold other refs; this is inferred, not
looked at here. The fault is fixed in the same commit, and the successful
builds of the right-hand column went through the real filter.

## Supplied boundaries

- The lint runs used the packages installed in the main checkout, not a fresh
  `yarn install --immutable` in the candidate tree. Imports of the workspace
  packages (`cvat-core` and the others) resolve through that `node_modules` to
  the main checkout's copies, which were compared and equal the candidate's.
- The policy test evaluates the inputs written in the test file. No server
  and no policy engine of a running stack were involved.
- The chart was rendered, not installed. No cluster was contacted or changed.
- The mirror script ran against local repositories and a failing stub, never
  against upstream.

## Not verified

- The filter run and the subtree pull themselves, and that the new filtered
  tree gets the computed id. The re-import (ticket 04) shows both.
- That a squashed subtree pull accepts a re-filtered mirror whose commit ids
  differ from the recorded ones (already listed as unverified in the plan).
- An install of the in-tree chart on a cluster (ticket 08).
- The type check, and whether ESLint reports the same findings when the
  workspace packages resolve inside one checkout (ticket 05).
- The mirror script against the real upstream, and its behaviour when two runs
  overlap or when the disk fills during the swap.
- Two branches of the new mirror script never ran: putting back a previous
  mirror that a killed run left set aside as `.cvat-mirror.git.old`, and giving
  the previous mirror its name back when the final rename fails.
- ruff was not run. The file reverted here was formatted by a ruff run over
  the whole repository in the past, so a ruff formatting check that covers
  `cvat/` would change it again; the gate (ticket 13) has to leave the import
  out.
