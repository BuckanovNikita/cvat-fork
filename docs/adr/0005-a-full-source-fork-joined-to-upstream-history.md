---
status: accepted
---

# The repository is a full-source fork, joined to upstream's history by one merge

The repository held a path-filtered copy of upstream CVAT under `cvat/`, pulled as a squashed subtree from a filtered mirror, and no Python backend. Putting Team Analytics inside the backend (ADR 0006) needs the backend in the tree. On 2026-11-15 the owner decided to make the repository a full-source fork of `cvat-ai/cvat`, and to do it without rewriting published history: `main` gains one merge commit whose parents are the overlay's `main` and upstream's `v2.82.0`. From that commit on the repository root is upstream's root, the fork's changes are ordinary commits on top, and a later release is taken with `git merge <tag>`.

## Considered Options

- **A new `main` rooted on the upstream tag, force-pushed.** The cleanest history, upstream's commits and then ours. It replaces a published branch. Kept as the fallback, to be used only on the owner's word.
- **A new repository forked from `cvat-ai/cvat` on GitHub.** A fork relation only matters for pull requests to upstream. It costs a new address and the carrying over of the tracker, the documents and the evidence.
- **Widening the filtered import to include the backend.** Every widening changes the identifiers of the mirrored history again, and the backend is most of the repository; the filter would keep nearly everything and still stand between the fork and a plain merge.

## Consequences

- It reverses the owner's decision of 2026-11-14 to keep the overlay layout, the "filtered source tree" of ADR 0003, and what ADR 0004 says about the policies being edited "inside the import". The mirror script, the vendored filter tool and the filtered tags are retired; the tags `cvat-v2.74.1`, `cvat-v2.82.0` and `cvat-v2.82.0-widened` stay as names for what earlier documents cite.
- `git log` on `main` shows the overlay's commits and all of upstream's. The first-parent line is the fork's own.
- Upstream owns the root names. Its `README.md` stays as upstream wrote it and the fork's Russian text is `README.fork.md`; replacing upstream's file would conflict on every release that touches it. The owner's standing rule is that `README.md` is Russian, and this is a stated exception to it. The fork's entries are appended to upstream's `.gitignore`. The gate's Python pin lives in `tools/gate/`, because the root `pyproject.toml` is upstream's.
- Upstream's `.github/` is removed. Its workflows, Dependabot configuration and code owners are written for upstream's repository and would act on this one. A release that changes one of those files reports a conflict with the deletion, and the answer is to keep it deleted.
- The fork's delta inside upstream's directories is small enough to list: seventeen edited UI files, two policies, and the touch points of ADR 0006. The list is kept in the fork specification, and `git diff <tag>..main` shows it exactly.
- Upstream's whole-repository linters would sweep the fork's own directories. They are not run as upstream runs them; the fork's gate (`prek.toml`) checks the fork's files with upstream's configuration where the file lives in upstream's tree, and with the fork's own elsewhere.
- Compose stays unsupported (the amendment of ADR 0003). Upstream's Compose files arrive with the tree and are left as they are.
- The upstream remote has no default fetch rule. Tags are fetched by name, so a routine fetch never brings in every upstream branch and tag.
