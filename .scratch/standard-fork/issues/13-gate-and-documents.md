# 13: The gate and the documents

**What to build:** The check pipeline covers the app, and the documents describe the fork as it now is.

**Blocked by:** 12.

**Status:** resolved

- [x] The pipeline checks the app with upstream's black and isort settings and runs upstream's generated policy tests.
- [x] The fork specification states the new ownership, BUILD-1, the service, access and limits of TA-1 and the integration maps, including the upstream internals the app depends on.
- [x] The upgrade procedure is a merge of a release tag, with what to do about `.github/`, the server image and the checks.
- [x] `README.fork.md`, the stack's README and the infrastructure notice match the tree.
- [x] The ledger carries a dated note.

## Comments

2026-11-15: The pipeline gained black, isort and upstream's generated policy tests in `43218eeb`. The documents were rewritten in `05c86536`: the fork specification (ownership and the whole delta inside upstream's directories, BUILD-1, TA-1 as the backend app with its read path, worker, refresh, settings and limits, the upstream internals the app depends on, the acceptance scenarios), the upgrade procedure as a merge of a release tag, `README.fork.md` in Russian, and a dated note in `INFRA_MIGRATION.md`. The stack's README was updated with the launcher in `3fa20bc3`. The ledger's note is in `95e5cef1`.

Not run: the commands of the upgrade procedure against a real later release. The read-only ones were run with the current tag.
