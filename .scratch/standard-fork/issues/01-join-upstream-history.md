# 01: Join upstream history

**What to build:** `main`'s line gains one merge commit whose parents are the overlay's `main` and upstream's `v2.82.0`, and the fork's changed files are replayed at upstream's paths. See ADR 0005 and "Repository" in the spec (`../spec.md`).

**Blocked by:** none.

**Status:** resolved

- [x] The join is tried first where it can do no harm: the merge commit is accepted, the merge base with a later upstream tag is `v2.82.0`, and a trial merge of that later tag conflicts, if at all, only in files the fork edits.
- [x] At the join commit every path of upstream's `v2.82.0` is unchanged.
- [x] After the replay every path of the old `cvat/` import has the same content at its unprefixed path, and upstream files differ from the tag only in the fork's 19 edited files.
- [x] The local tags that would clash with upstream's are gone, and the upstream remote fetches tags by name only.
- [x] Nothing is pushed.

## Comments

2026-11-15: Tried in a scratch clone of upstream with the fork's `main` fetched into it, with plumbing only (no working tree). The join commit kept all 3,258 upstream paths unchanged; the replay reproduced all 1,037 files of the old import; the merge base with `v2.83.0` was `02bd74f` (`v2.82.0`); `git merge-tree` of `v2.83.0` onto the replayed tip finished with no conflict. `v2.83.0` changes 85 files, one of them edited by the fork (`cvat-ui/src/reducers/index.ts`), and that one merged cleanly.

2026-11-15: Done on branch `feat/full-fork`: join `2abbf81f`, then `e0e04a03` (task progress, 8 files), `f7a881ea` (policies, 2 files), `73b8ce00` (Team Analytics UI and logging, 70 files). Checked on those commits: 0 upstream paths differ at the join; 0 of the 1,037 old import paths differ at `73b8ce00`; against `v2.82.0` the tip has 19 modified and no deleted upstream files. The local tags `v2.82.0` and `v2.74.1`, which named filtered commits, were deleted after checking that `cvat-v2.82.0` and `cvat-v2.74.1` name the same commits; `v2.82.0` is now upstream's tag. The remote `upstream` has no default fetch rule. The installed dependencies were moved from `cvat/node_modules` to `node_modules`, not reinstalled.
