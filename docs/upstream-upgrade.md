# Updating the CVAT fork

Use this procedure when importing a new CVAT release. The
[fork specification](fork-specification.md) defines the behavior to preserve;
the [dated baseline](evidence/2026-11-13-fork-baseline.md) identifies the starting
revisions. Commands run from the repository root unless stated otherwise.

## 1. Record the starting point

Inspect working and staged changes, the current branch, local `main` comparison
and cached remote-tracking state. Preserve unrelated work. Record whether
remote references have actually been fetched. Start the upgrade on a dedicated
branch from the intended clean fork revision.

Record the old filtered import reference and its raw upstream commit separately.
Filtered commit IDs differ from commits in `cvat-ai/cvat` because history and
paths have been rewritten. Local `cvat-v*` tags identify filtered upstream trees,
not fork release snapshots. Recover import metadata from subtree merge commits
if a tag is missing; do not guess the baseline from the custom image name.

For the baseline documented here, inspect the current customization with:

```bash
git diff --name-status cvat-v2.82.0 HEAD:cvat
git diff cvat-v2.82.0 HEAD:cvat
git log --first-parent --oneline
```

This tree-to-tree comparison is essential: a root-level comparison with an
upstream commit would mix the subtree layout with fork changes. It also omits
root-owned OPA/build/verification files, which must be reviewed separately.

## 2. Import the target release

Choose the target upstream tag and record its full raw commit ID, resolving an
annotated tag to its commit. Obtain the matching full upstream source separately
for backend policy comparison. Review upstream release changes relevant to the
UI, OPA, image build and server/database compatibility.

Refresh the filtered mirror using `mirror-cvat.sh`; `UPSTREAM` can select a
different source. The script deletes and recreates only its `.cvat-mirror.git`
directory, downloads upstream history and applies its maintained path list.
Keep unique work out of that generated directory. If the new release requires
additional build/runtime files, update `PATHS` before regenerating the mirror.

After selecting `TARGET` (for example, the chosen `vX.Y.Z` tag):

```bash
git switch -c "upgrade/cvat-${TARGET}"
./mirror-cvat.sh
git fetch .cvat-mirror.git "refs/tags/${TARGET}:refs/tags/cvat-${TARGET}"
git subtree pull --prefix cvat .cvat-mirror.git "$TARGET" --squash
```

Keep an existing filtered baseline tag immutable; investigate a conflicting tag
instead of force-updating it. Changing `PATHS` can also rewrite historical
filtered commit IDs: retain the original baseline reference and record the
filter change alongside the new raw-to-filtered mapping in dated evidence.
Resolve merge conflicts against the specification, preserving new upstream
behavior and transplanting only the required fork changes.

Compare the result with the new filtered reference:

```bash
git diff --name-status "cvat-${TARGET}" HEAD:cvat
git diff "cvat-${TARGET}" HEAD:cvat
git diff -- cvat
```

`HEAD:cvat` reflects committed content only. Include working/staged changes in
the review until all resolutions are committed, then repeat the tree comparison
on the final commit. Account for every remaining file in the fork specification;
if upstream now provides an equivalent feature, verify the acceptance scenarios
before removing its local replacement.

## 3. Rebase the external overlays

Compare the old stock rules with `opa/rules/` to identify the local additions.
Use the target release's full `cvat/apps/engine/rules/issues.rego` and
`comments.rego` as the new base, and reapply the same-organization member action
and base-filter extensions. Retain the target's upstream context checks and
filter wrapper. Compare old and new IAM/organization helpers as well.

Keep the four policy sources from one raw upstream revision: the two resource
rules, `cvat/apps/iam/rules/utils.rego`, and
`cvat/apps/organizations/rules/organizations.rego`. Mixing helper versions can
hide precisely the compatibility failures this check is meant to detect.

Update default custom UI tags together in `build-ui.sh`,
`docker-compose.override.yml` and `verify/docker-compose.verify.yml`. Select
the matching stock backend version in the deployment/test configuration.
Review the imported Dockerfile's build arguments and base-image name against
the script's BuildKit override. Consult project dependency configuration for
compatible tools rather than adding version pins to these instructions.

Check added/renamed services against the verification overlays: fixed upstream
container names can cause collisions if an overlay no longer renames every
service. Reconcile runtime mounts and Compose path resolution with the intended
deployment directory. Update the specification only for intentional behavior
changes, and record their acceptance evidence.

## 4. Verify the integrated changes

Run applicable checks once on the integrated result; rerun them only after
relevant changes or failures. Keep failures, warnings, skipped checks and their
reasons in dated evidence. No root Spec Kit, OpenSpec or prek pipeline exists
at the recorded baseline; use a native workflow if one is introduced later.

### Frontend

With the toolchain required by the imported package configuration:

```bash
(cd cvat && DISABLE_HUSKY=1 yarn install --immutable)
node --test verify/task_progress.cjs
(cd cvat && yarn run type-check)
(cd cvat && SOURCE_MAPS_ENABLED=false yarn run build:cvat-ui)
```

For task-legend color changes, also run the browser regression with an installed
Chrome/Chromium executable (name or absolute path):

```bash
BROWSER_BIN=google-chrome node --test verify/task_progress.cjs
```

It checks computed text contrast with the real summary component, Ant Design
styles and task-card stylesheet in an isolated browser profile. Without
`BROWSER_BIN`, this browser check is skipped; the other regression tests run.

`DISABLE_HUSKY=1` matches the imported Dockerfile's dependency installation and
avoids installing upstream Git hooks in the wrapper repository. The filtered
tree may omit upstream lint configuration; report that limitation rather than
claiming a successful lint run. A host build does not prove image packaging.

### OPA

Set `UPSTREAM_CVAT` to an absolute full-source checkout of the exact target
upstream commit, and `OPA_IMAGE` to the OPA image selected by the imported
Compose configuration. The existing policy test can run without starting CVAT:

```bash
docker run --rm --network none --cpus=1 --memory=256m \
  -v "$PWD:/repo:ro" -v "$UPSTREAM_CVAT:/upstream:ro" "$OPA_IMAGE" \
  test /repo/opa/rules /repo/verify/opa_issues_test.rego \
  /upstream/cvat/apps/iam/rules/utils.rego \
  /upstream/cvat/apps/organizations/rules/organizations.rego -v
```

Repeat with the two stock resource rules instead of `/repo/opa/rules` and an
additional data file containing `{"expected":{"patched":false}}`. Pass that
file as another positional input to `opa test`. Keep it in a task-owned mounted
temporary directory and remove it afterward. Both runs must match their own
expectations; an identical result is not the goal because member access differs.

Check policy compilation with the same target helpers. If strict OPA lint fails,
compare stock and patched rules before classifying an inherited warning. Retain
the stock-versus-patched distinction in the recorded result.

### Packaging and integration

Check shell syntax and render applicable Compose configurations without starting
services. Inspect the resolved images, rule mounts and service names. For actual
packaging, use `./build-ui.sh` with the chosen `IMAGE`/`NODE_IMAGE` overrides;
use `SAVE=1` only if an archive is needed. Inspect served assets in the built
image, then exercise the specification's browser/API scenarios in owned test
infrastructure.

Read [`INFRA_MIGRATION.md`](../INFRA_MIGRATION.md) before live verification.
The current legacy entry points are `verify/run.sh` (frontend) and
`verify/opa_issues.sh all` (stock/patched permissions). They use fixed Compose
projects, names and ports and leave stacks running. Establish ownership before
using them; their successful exit is not proof of all acceptance scenarios.
The OPA checker prints a matrix that needs review, and the frontend seed covers
only part of the palette. Verify both bundle files and live policy behavior,
including negative authorization cases. Recreate only the intended server and
allow for OPA's asynchronous bundle refresh.

Clean up only resources created for this verification. The legacy `down`
commands remove their project volumes, so use them only for owned disposable
stacks. Account for temporary seed/bundle directories if a launcher fails.
Do not treat these launchers as completion of the pending infrastructure
migration or as permission to intervene in an existing deployment.

## 5. Record and hand off

Obtain independent review of the integrated behavioral and permission changes
after verification. Record the raw and filtered upstream revisions, final fork
revision, remaining customization inventory, commands/outcomes and unverified
acceptance scenarios in a dated file under `docs/evidence/`. Update the README
baseline link and specification integration map as needed. Keep historical
test counts and deployment results out of the evergreen specification.

Commit only task-owned changes using the repository's commit convention, with
safe mechanical formatting fixes separate from behavior changes. Publishing
or deployment requires its own authorization. Before an authorized deployment,
retain the prior UI image, policy files and deployment configuration, and plan
database backup/rollback according to the target upstream release; reverting
the subtree alone does not undo server database migrations.
