# OPA rules mount path, 2026-11-14

The two Compose overlays mounted the patched `issues.rego` and `comments.rego`
into `/home/django/cvat/apps/engine/rules/`. The stock `cvat/server:v2.82.0`
image has no such directory: upstream moved the installed sources to
`/opt/cvat` in 2.72.0, and the server builds the bundle it serves at
`/api/auth/rules` from `/opt/cvat/cvat/apps/engine/rules/`. Docker creates the
missing target without an error, so a deployment using the overlay as written
ran the stock rules (IAM-1 not in force).

## Observed

| Check | Old target (`/home/django/...`) | New target (`/opt/cvat/...`) |
| --- | --- | --- |
| Directory exists in `cvat/server:v2.82.0` | no | yes |
| Bundle built by the server's own `get_opa_bundle()` in that image, with both files mounted: `issues.rego` carries the patch | no | yes |
| Same, `comments.rego` | no | yes |

The bundle was built in a one-off container of the stock image with the two
files mounted at the target and Django set up, no other service running. The
rendered Compose configuration of the verification overlay and the deployment
override now both name the new target.

The existing policy test passed against the v2.82.0 helper rules (12 of 12)
with OPA 1.12.2, unchanged by this fix.

## Not verified

- No stack was started. `verify/opa_issues.sh all` was not run: three of its
  images were not present locally and were not pulled. The live matrix (an
  unassigned organization member acting on issues and comments through the
  API) therefore still rests on the policy test plus the bundle check above.
- Whether any deployment ran v2.72.0 or later with the old overlay, and for
  how long, was not examined.

## Changed

`docker-compose.override.yml`, `verify/docker-compose.opa-patch.yml`, the
BUILD-1 section of `docs/fork-specification.md`, and the OPA section of
`docs/upstream-upgrade.md` (a check of the target directory on every upgrade).
A running deployment picks the fix up when `cvat_server` is recreated with the
corrected override.
