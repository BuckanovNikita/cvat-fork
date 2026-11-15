# 07: Fork server image

**What to build:** One script builds the fork server image: the stock release image with the two patched policies copied over the stock ones, and nothing else. See ADR 0004 and "Policies and the fork server image" in the spec (`../spec.md`).

**Blocked by:** 06 (Policies patched in place with the role floor).

**Status:** resolved

- [x] A build script beside the UI's builds the image from the stock release image and the two patched policies of the import. Nothing is installed and no Python changes.
- [x] The image's tag names the release and marks it as the fork's. Its default is set in the script, as for the UI image.
- [x] The server's own bundle builder, run in the image with no mounts, yields a bundle whose two policies equal the patched files of the import. The same check on the stock image shows the stock policies.
- [x] Compared with the stock image, only those two files differ.
- [x] The script needs no network when the stock image is local, and never pulls or pushes.
- [x] The Team Analytics service image still builds on the stock base, unchanged.
- [x] The checks are recorded in a dated evidence file.

## Comments

2026-11-14: `./build-server.sh` (`Dockerfile.server`) builds the image. Its default tag is
`cvat/server:v2.82.0-fork-policies`. The record is
`docs/evidence/2026-11-14-fork-server-image.md`. For ticket 08, a served bundle is checked
with `curl -s <api>/auth/rules | verify/policy_bundle.sh check`, which compares each policy
byte for byte with the import's file.

2026-11-14: The no-network criterion is now shown. The script, given the stock image under a
temporary name on the unresolvable host `registry.invalid` as its base, built the same image
(same ID) with no pull; see the evidence file. The earlier comment below is superseded.

2026-11-14 (superseded): The no-network criterion is unticked. Its second half is shown: the script
refuses a base that is not local, never pulls and has no push step, and the build's events
showed no pull. The first half is not shown: the Docker daemon's network cannot be switched
off from here, so the build never ran with the network off. Both halves currently rest on the
local-base check, `--pull=false`, the absence of `RUN` steps, the events and the build log.

2026-11-14: Resolved by merge `bdfb5232` into `feat/team-analytics-page`; evidence in `docs/evidence/2026-11-14-fork-server-image.md`. On the merged tree: `bash -n` exits 0 for `build-server.sh` and `verify/policy_bundle.sh`; the bundle built from `cvat/server:v2.82.0-fork-policies` equals the import's two policies, and the bundle built from `cvat/server:v2.82.0` differs from them and equals `cvat-v2.82.0-widened`; nothing under `cvat/` changed.

2026-11-15: Changed by the follow-up to the independent review of the delivery change (branch `fix/delivery-review`, findings 2 and 3). `build-server.sh` now builds untagged and tags `IMAGE` only when the build's bundle, from the server's own builder, holds the import's two patched policies and the base's bundle holds the four policy files of the import tag (`STOCK_TAG`, which must be local); on failure no image is left under `IMAGE` and nothing is saved. Seen failing on a base whose rules directory is elsewhere and on a base with a changed helper policy; the integration tip's script built both. `verify/policy_bundle.sh` refuses duplicate entries and a policy that is not a regular file, and gains `check-stock`. The rebuilt `cvat/server:v2.82.0-fork-policies` passed both checks with the same ID, `4b38c649ae96`. Evidence: `docs/evidence/2026-11-15-compose-removed.md`, "Independent review of the delivery change".

2026-11-15: Changed by the follow-up to the review of the follow-ups (branch `fix/last-review`, findings 1 and 5). `verify/policy_bundle.sh` refuses any entry that is neither a regular file nor a directory, wherever it sits (a link on the `rules` directory passed before), compares entry names after normalising them (`rules//issues.rego` is `rules/issues.rego`) and refuses a name that leaves the bundle; the real fork bundle passes, the stock, mixed and old bundles fail as before. A failed check in `build-server.sh` no longer removes an earlier image under `IMAGE`: it removes only what the run built, tags and saves nothing, exits 1 and names the earlier build as unchecked by that run; shown on throwaway tags. `cvat/server:v2.82.0-fork-policies` kept `4b38c649ae96`, and the new script rebuilt it at the end with both checks passing and the same ID. Evidence: `docs/evidence/2026-11-15-integrated-branch-review.md`, "Review of the follow-ups".
