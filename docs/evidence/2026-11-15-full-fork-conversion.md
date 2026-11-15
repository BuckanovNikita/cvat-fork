# Conversion to a full-source fork, 2026-11-15

Tickets 01 and 02 of `.scratch/standard-fork/` (ADR 0005). The repository was joined to
upstream's history on branch `feat/full-fork`, started from `main` at `5b88efcc`. Nothing was
pushed. Everything below ran on that branch on the date above; commit ids are local.

The branch was then published on `main` as one commit, at the owner's word: a merge commit whose
parents are `main` at `5b88efcc` and upstream's `v2.82.0` (`02bd74f`), and whose tree is the
branch's tip. The join is kept, so a later release is still merged by its tag. The commit ids in
this record, in the other records of this date and in the tickets of `.scratch/standard-fork/`
are those of the branch before it was squashed; they are not in the published history.

## The join was tried before it was made

In a scratch clone of `cvat-ai/cvat` (commits and trees only), with the fork's `main` fetched
into it, the join and the replay were built with plumbing, with no working tree:

| Check | Result |
| --- | --- |
| upstream paths of `v2.82.0` that differ at the join commit | 0 of 3,258 |
| files of the old `cvat/` import that differ at the replayed tip | 0 of 1,037 |
| `git merge-base <tip> v2.83.0` | `02bd74f`, which is `v2.82.0` |
| `git merge-tree --write-tree <tip> v2.83.0` | exit 0, no conflicted path |

`v2.83.0` changes 85 files. One of them is edited by the fork
(`cvat-ui/src/reducers/index.ts`) and merged without a conflict. This shows that a release
merges onto the joined history; it says nothing about releases that touch the fork's files
more heavily.

## The join and the replay on the branch

| Commit | What |
| --- | --- |
| `2abbf81f` | merge with parents `5b88efcc` (the overlay's `main`) and `02bd74f` (upstream `v2.82.0`) |
| `e0e04a03` | task progress, 8 files |
| `f7a881ea` | issue and comment policies, 2 files |
| `73b8ce00` | Team Analytics page and logging, 70 files |

Read back from those commits:

- At `2abbf81f` no upstream path differs from `v2.82.0`. The tree adds the fork's own files:
  `README.md` as `README.fork.md`, `pyproject.toml` and `uv.lock` under `tools/gate/`, the
  rest where they were. It does not carry the old `cvat/` import, `mirror-cvat.sh`,
  `tools/git-filter-repo` or the fork's `.gitignore`.
- At `73b8ce00` every one of the 1,037 files of `5b88efcc:cvat/` has the same blob at its
  unprefixed path. Against `v2.82.0` that tip has 19 modified upstream files and none deleted.
- The 80 replayed files are the ones under `5b88efcc:cvat/` whose blob differs from, or is
  absent in, `v2.82.0`: 61 added, 19 modified. The split into 8, 2 and 70 is by path.

Local changes made for it, none of them in a commit:

- The local tags `v2.82.0` and `v2.74.1` named filtered commits. They were deleted after
  checking that `cvat-v2.82.0` and `cvat-v2.74.1` name the same commits (`6545b83e`,
  `eb9eca2f`). `v2.82.0` is now upstream's tag.
- A remote `upstream` (`https://github.com/cvat-ai/cvat.git`), with the clone's blob filter
  and no default fetch rule. Only `refs/tags/v2.82.0` was fetched.
- The installed dependencies were moved from `cvat/node_modules` and `cvat/.yarn` to the
  repository root, not reinstalled.

## Tooling on the new layout

Commits `6cc31091` (`.github/` removed), `3de05f86`, `3ae9ab7d`.

| Check | Result |
| --- | --- |
| `prek run --all-files` at `3ae9ab7d` | 9 hooks passed |
| page, logging, task progress suites | 223, 77, and 20 with 1 skipped: the counts before the conversion |
| files ruff selects | 74: 63 under `team-analytics/`, 9 under `verify/`, 2 under `docs/`; none of upstream's |
| `verify/team-analytics-stack/run.sh preflight` | passed: server image, both policy matrices, chart build from `helm-chart/`, render, render guard; nothing created or pulled |
| `IMAGE=cvat/ui:v2.82.0-fork ./build-ui.sh` at `9c0d8248` | built; the build context sent was 27 MB |

One failure on the way. With the dependencies at the repository root, the harness's jsdom
resolved upstream's `canvas` package, whose native part is not built here, and the page and
logging suites failed before running a test. `verify/browser-environment.cjs` now reports
`canvas` to jsdom as not installed while jsdom loads.

The service suite was started at `3ae9ab7d` and stopped by hand after 75 tests had passed and
none had failed, because it reads the service's files from the working tree and the next
step moved them. Its full run on the moved code is recorded with the backend work.

## The fork server image with the backend files

`./build-server.sh` at `9c0d8248` built `cvat/server:v2.82.0-fork` (`dd807aebf200`) from the
local `cvat/server:v2.82.0`, with no network. Its three checks passed:

- the image's own bundle builder yields the tree's `issues.rego` and `comments.rego`;
- with `CVAT_ANALYTICS=1` it also yields the tree's `team_analytics.rego`;
- the base image's bundle equals the four policy files of `v2.82.0`.

Inside the image, with Django set up on the production settings and no other service
(`--network none`):

| | `CVAT_ANALYTICS=1` | `CVAT_ANALYTICS=0` |
| --- | --- | --- |
| app `cvat.apps.team_analytics` installed | yes | no |
| queue `team_analytics` registered | yes | no |
| periodic job `team_analytics_refresh` | `* * * * *` | absent |
| `/api/team-analytics/{status,overview,trends,list,details}` | resolve to the view set | 404 |

This is the wiring as Django resolves it. No request was served and no worker was started
for this record.

Later the same day (`2c653fe6`) the queue was defined for both settings, so that a stored
schedule can be removed where analytics is switched off; the table is the image of `9c0d8248`.

## Not verified here

- Nothing on a running stack: that is the acceptance run's record.
- The build of the fork's tree with upstream's own `Dockerfile`.
- A merge of a release that changes the fork's edited files, or files under `.github/`.
- That a fresh clone of the branch, with dependencies installed from scratch at the root,
  passes the check pipeline: the dependencies here were moved, not installed.
