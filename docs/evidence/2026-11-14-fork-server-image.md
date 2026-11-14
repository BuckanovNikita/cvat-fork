# Fork server image, 2026-11-14

Ticket 07 of the defect fixes (ADR 0004). `build-server.sh` builds
`cvat/server:v2.82.0-fork-policies` from the local `cvat/server:v2.82.0` with
`Dockerfile.server`: one `COPY` of the import's `cvat/cvat/apps/engine/rules/issues.rego`
and `comments.rego` over the stock files at `/opt/cvat/cvat/apps/engine/rules/`, nothing
else. Checked at commit `a028335`, on top of merge `ff0c4a9` (ticket 06, patched policies).

## Live outcomes

### The served policies

`verify/policy_bundle.sh from-image IMAGE` runs the server's own `get_opa_bundle()` in a
one-off container of the image (no mounts, no network, Django set up with the production
settings, no other service) and writes the bundle. `verify/policy_bundle.sh check [REF]`
reads a bundle on stdin and compares `rules/issues.rego` and `rules/comments.rego`, each by
itself and byte for byte, with the import's files, or with the files at an upstream mirror
tag.

| Bundle built in | `check` (the import, patched) | `check cvat-v2.82.0-widened` (stock) |
| --- | --- | --- |
| `cvat/server:v2.82.0` | both differ, exit 1 | both equal, exit 0 |
| `cvat/server:v2.82.0-fork-policies` | both equal, exit 0 | both differ, exit 1 |

Both bundles hold the same 35 members; `diff -rq` between them reports exactly
`rules/issues.rego` and `rules/comments.rego`. Ticket 06's marker `Local patch (role floor)`
occurs twice in each policy of the fork bundle and zero times in the stock bundle.

### Only the two files differ

- The stock image's 18 layer diffIDs (`docker image inspect`, `.RootFS.Layers`) are,
  unchanged and in order, the first 18 of the fork image's 19.
- The 19th layer was listed from one `docker save` of the fork image, streamed through the
  shared lock (`nice -n19 ionice -c3`) into a reader that kept only small members; nothing
  large was written to disk. The sha256 of the uncompressed layer equals the 19th diffID in
  the image config and in `docker image inspect`, so the listing is of that layer. It holds:

  | Entry | Owner | Mode | Size |
  | --- | --- | --- | --- |
  | `opt/`, `opt/cvat/`, `opt/cvat/cvat/`, `opt/cvat/cvat/apps/`, `opt/cvat/cvat/apps/engine/`, `opt/cvat/cvat/apps/engine/rules/` (directories) | 0:0 | 755 | |
  | `opt/cvat/cvat/apps/engine/rules/comments.rego` | 0:0 | 644 | 5003 |
  | `opt/cvat/cvat/apps/engine/rules/issues.rego` | 0:0 | 644 | 4781 |

  No whiteout entry. The six directory entries are the parents the `COPY` writes; in both
  images those directories are `root:root 755`, so only their modification times can
  differ. `rules/` holds 12 files in both images.
- The image configs (`.Config`: user `1000:1000`, working directory, entrypoint, command,
  environment, labels, ports) are identical, as are architecture and OS. The build passes
  `--provenance=false`, so the image carries no attestation manifest either.
- In the running image both files are `root:root 644`, the owner and mode of the stock
  files, and are read by the server's user `django`; their sha256 equal the import's files.

### No network, no pull

- The script stops before any build when the base image is not local
  (`BASE_IMAGE=cvat/server:v0.0.0-absent`: exit 1, "never pulls it") and when `IMAGE`
  equals `BASE_IMAGE` (exit 1), so it can neither fetch the base nor overwrite the stock tag.
  It passes `--pull=false` and `--network=none`, and has no push step.
- During the build, `docker events` (type image) showed only `create` and `tag` of the new
  image, no `pull`. The plain progress log resolves the base by its local digest
  (`docker.io/cvat/server:v2.82.0@sha256:e4ff37f1...`), and the stock image ID was the same
  afterwards.

### The Team Analytics service image

`build-team-analytics-service.sh` and `team-analytics/Dockerfile` are unchanged. Built with
`IMAGE=cvat/team-analytics:v2.82.0-t07-check` (its Dockerfile only copies files onto the
local base; no `RUN`): it succeeded, its first 18 layers are the stock image's, and it does
not contain the fork image's policy layer.

## Not verified

- The client cannot switch off the Docker daemon's network, so the build was not run on a
  machine with no network. `--network=none` covers only `RUN` steps, of which there are
  none; the absence of a pull rests on the local-base check, the events and the log above.
- No server was started: the policies a running server serves at `/api/auth/rules` are
  ticket 08's check (`curl -s <api>/auth/rules | verify/policy_bundle.sh check`).
- The policy decisions themselves are ticket 06's policy test, not repeated here.
