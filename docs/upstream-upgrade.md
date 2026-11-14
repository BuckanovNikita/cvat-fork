# Updating the CVAT fork

Use this procedure when importing a new CVAT release. The
[fork specification](fork-specification.md) defines the behavior to preserve;
the [dated baseline](evidence/2026-11-13-fork-baseline.md) and the
[widened import baseline](evidence/2026-11-14-widened-import-baseline.md)
identify the starting revisions. Commands run from the repository root unless stated otherwise.

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

The import was re-filtered at v2.82.0 with a widened path list (the
[widened import baseline](evidence/2026-11-14-widened-import-baseline.md)).
Its filtered commit is the local tag `cvat-v2.82.0-widened`. The older tags
`cvat-v2.82.0` and `v2.82.0` keep the commit of the earlier, narrower filter,
which earlier merges cite; they no longer describe the import. The tags are
local and never pushed: a fresh clone has none of them. To recreate the
widened tag, build a mirror with the current `PATHS` and fetch as in section
2; before tagging, compare the fetched commit and its tree with the ids in the
widened import baseline. The tree must match; the commit id can differ if the
clone held a different history.

Inspect the current customization with:

```bash
git diff --name-status cvat-v2.82.0-widened HEAD:cvat
git diff cvat-v2.82.0-widened HEAD:cvat
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
different source. The script downloads upstream history into
`.cvat-mirror.git.new`, beside the existing mirror, and applies its maintained
path list there. It replaces `.cvat-mirror.git` only after both steps succeeded;
a failed run leaves the existing mirror as it was. Keep unique work out of
these generated directories. If the new release requires
additional build/runtime files, update `PATHS` before regenerating the mirror.

After selecting `TARGET` (for example, the chosen `vX.Y.Z` tag):

```bash
git switch -c "upgrade/cvat-${TARGET}"
./mirror-cvat.sh
git fetch --no-tags .cvat-mirror.git "refs/tags/${TARGET}:refs/tags/cvat-${TARGET}"
git subtree pull --prefix cvat .cvat-mirror.git "$TARGET" --squash
```

`--no-tags` matters: a fetch with a destination otherwise also copies every
mirror tag that points into the fetched history, which puts upstream's
release tags (`vX.Y.Z`, filtered) into this repository. An existing local tag
of the same name is not moved by it, but the new ones are noise. Afterwards
`git show-ref --tags` must differ from before by exactly the one new tag.

Keep an existing filtered baseline tag immutable; investigate a conflicting tag
instead of force-updating it. Changing `PATHS` can also rewrite historical
filtered commit IDs: retain the original baseline reference and record the
filter change alongside the new raw-to-filtered mapping in dated evidence.

**After changing `PATHS`.** Re-filtering gives every filtered commit a new id,
so the commit the last snapshot records is not an ancestor of the new tag.
The squashed pull still works: it finds the last snapshot by its
`git-subtree-dir: cvat` line, writes a new snapshot of the new tree on top of
it and merges it. But its snapshot message lists the subject of every commit
of the new tag's history. Any squashed pull writes its snapshot message
itself, so the snapshot cannot carry commit trailers. Whenever that message
must be controlled (a re-filtered mirror, or required trailers), write the
snapshot as `git subtree` does instead, then merge it the same way (tag name as chosen above;
`<previous snapshot>` is the commit `git log -1 --grep='^git-subtree-dir: cvat/*$'` prints):

```bash
git fetch --no-tags .cvat-mirror.git "refs/tags/${TARGET}:refs/tags/<new tag>"
new=$(git rev-parse "<new tag>^{commit}")
snapshot=$(git commit-tree "<new tag>^{tree}" -p <previous snapshot> -F <message file>)
git merge --no-ff -Xsubtree=cvat -F <merge message file> "$snapshot"
git subtree pull --prefix cvat .cvat-mirror.git "$TARGET" --squash
```

The message file holds a subject, the two lines `git-subtree-dir: cvat` and
`git-subtree-split: $new` (the full id), and the trailers. No other commit
message may carry `git-subtree-` lines, or later pulls find the wrong
snapshot. The last command must print `Subtree is already at commit <new>`
and change nothing: that shows a later release pulls normally on top. Before
the merge, check the new tag's tree against one computed independently, and
after it, that every path the import kept is unchanged
([the v2.82.0 re-import](evidence/2026-11-14-widened-import-baseline.md)
lists the checks).
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
reasons in dated evidence. No root Spec Kit or OpenSpec workflow exists at the
recorded baseline; use a native workflow if one is introduced later.

### Check pipeline

One command runs, from the repository root, every check that needs neither
ClickHouse nor a stack:

```bash
prek run --all-files
```

`prek.toml` holds the hooks: ESLint and stylelint on the fork's UI files, the
type check, ruff on the fork's Python, the policy test on the patched and on
the stock policies, and the three fast frontend suites, one after another. A
hook pipeline is a default the owner was not asked about. No hook rewrites a
file. The UI linters run the commands under "Frontend" below on the tracked
files under `cvat/` whose content differs from the import tag
(`tools/gate/ui-lint.sh`), so a new file is checked once it is tracked; after
an upgrade, change the script's default tag (`IMPORT_TAG` overrides it) with
the policy test's `STOCK_TAG`. ruff never reads `cvat/` (`ruff.toml`), and
formatting is not checked: the fork's Python was never formatted with ruff.
Run the pipeline by its command; do not install it as git hooks.

Prerequisites on a fresh checkout:

- `prek`, `uv`, Node and Docker on the path; network on the first run, when
  `uv` installs ruff into `.venv` as `uv.lock` locks it and Docker pulls the
  OPA image that `verify/policy_test.sh` names.
- The import tag (section 1; tags are not pushed).
- `cvat/node_modules` and `verify/node_modules`, installed as under
  "Frontend" below.

Kept out of the pipeline, each a separate command with its own prerequisites:

- `verify/team_analytics_service.sh`: the service seam, under "Team
  Analytics"; Docker, the stock server image and a ClickHouse image.
- `verify/team-analytics-stack/run.sh cycle`: the stack, under "Team
  Analytics"; both built images, a cluster and the reserved host port.
- `BROWSER_BIN=<browser> node --test verify/task_progress.cjs`: the browser
  check of the task legend, under "Frontend"; without `BROWSER_BIN` the
  pipeline's run skips it.
- `verify/run.sh` and `verify/opa_issues.sh all`: the legacy live launchers,
  under "Packaging and integration".

### Frontend

With the toolchain required by the imported package configuration:

```bash
(cd cvat && DISABLE_HUSKY=1 yarn install --immutable)
npm ci --prefix verify
node --test verify/task_progress.cjs
(cd cvat && SOURCE_MAPS_ENABLED=false yarn run build:cvat-ui)
```

Lint and type-check the fork's UI code with upstream's own configuration, which
the import carries at its root (`cvat/eslint.config.mjs` with
`cvat/.eslintrc.cjs`, `cvat/.stylelintrc.json`, `cvat/cvat-ui/tsconfig.json`).
Each command runs from the repository root on the installed `cvat/node_modules`
and needs neither `yarn` nor a change of directory:

```bash
node cvat/node_modules/eslint/bin/eslint.js --max-warnings 0 --no-warn-ignored <files>
node cvat/node_modules/stylelint/bin/stylelint.mjs --max-warnings 0 <files>
node cvat/node_modules/typescript/bin/tsc -p cvat/cvat-ui/tsconfig.json
```

ESLint takes the `.ts` and `.tsx` files, stylelint the `.scss` files, as paths
from the repository root. Pass only the UI files the fork added or edited, never
the whole import, and never let `--fix` touch upstream's files: they stay as
upstream wrote them. A finding in an upstream line of a file the fork edited is
left alone and recorded in the dated evidence. The list compares committed
content with the tag of the import now in the tree: `cvat-v2.82.0-widened`
(section 1) until the next upgrade, then the new tag of section 2. Against an
older tag it would also list every UI file upstream changed since.

```bash
import_tag=cvat-v2.82.0-widened
git diff --name-only --diff-filter=d "$import_tag" HEAD:cvat -- '*.ts' '*.tsx' | sed 's|^|cvat/|'
git diff --name-only --diff-filter=d "$import_tag" HEAD:cvat -- '*.scss' | sed 's|^|cvat/|'
```

`--max-warnings 0` is the fork's addition: upstream's `yarn run lint` fails on
errors only, while the fork's files are kept free of warnings too, unused
disable directives among them. `--no-warn-ignored` keeps a path the
configuration ignores from counting as a warning. The type check is upstream's
`yarn run type-check` (`tsc -p cvat-ui/tsconfig.json`) and always covers the
whole UI. It resolves the workspace packages (`cvat-core`, `cvat-canvas`,
`cvat-canvas3d`, `cvat-data`) through the links in `cvat/node_modules`, so in a
worktree whose `cvat/node_modules` links to another checkout it checks against
that checkout's packages; run it where the dependencies are installed.

`npm ci --prefix verify` installs the frontend harness's own dependencies: the
browser environment (jsdom) that the two Team Analytics frontend suites below
load. `verify/package.json` declares it and `verify/package-lock.json` locks it;
the import's manifest and lock are not involved. It goes to
`verify/node_modules`, which git ignores, once per checkout. A worktree may link
that path to the `verify/node_modules` of a checkout that has it installed
instead. `verify/task_progress.cjs` does not need it.

For task-legend color changes, also run the browser regression with an installed
Chrome/Chromium executable (name or absolute path):

```bash
BROWSER_BIN=google-chrome node --test verify/task_progress.cjs
```

It checks computed text contrast with the real summary component, Ant Design
styles and task-card stylesheet in an isolated browser profile. Without
`BROWSER_BIN`, this browser check is skipped; the other regression tests run.

`DISABLE_HUSKY=1` matches the imported Dockerfile's dependency installation and
avoids installing upstream Git hooks in the wrapper repository. A host build
does not prove image packaging.

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

Confirm where the target server image keeps `cvat/apps/engine/rules/` and that
both Compose overlays mount the patched files there (`/opt/cvat/cvat/...` since
2.72.0). Build the bundle in that image with the mounts applied and check that
both files in it carry the patch; a wrong target fails silently.

Check policy compilation with the same target helpers. If strict OPA lint fails,
compare stock and patched rules before classifying an inherited warning. Retain
the stock-versus-patched distinction in the recorded result.

### Team Analytics

Account for every file in the TA-1 integration map. Check the upstream
dependencies listed there against the target release: the `events` table
schema, the server's allowed client scopes and working-time calculation,
Vector's field allowlist, the cvat-core logger and plugin wrapper, saved
annotation event names, the memberships policy, the project `id` filter,
CVAT's minimum app width, and the shortcut action names. A changed name breaks
figures without an error, so compare them, not only the build.

Run the three seams. The service seam needs only Docker. The two frontend
seams need `cvat/node_modules` and the harness's dependencies
(`npm ci --prefix verify`, under "Frontend" above); without the latter they fail
and name what is missing, they do not skip tests:

```bash
verify/team_analytics_service.sh               # service against a real ClickHouse
node --test verify/team_analytics_logging.cjs  # events the UI logging sends
node --test verify/team_analytics_page.cjs     # page with supplied responses
```

The service tests run in a container of the stock server image. Set
`CLICKHOUSE_IMAGE` to the ClickHouse version of the target chart. If the
server image's Python or `clickhouse_connect` changed, check that the service
still needs nothing beyond them.

Then build both images from the integrated tree and run the stack once
(`verify/team-analytics-stack/README.md`; reserved host port 8490):

```bash
IMAGE=cvat/ui:<tag> ./build-ui.sh
IMAGE=cvat/team-analytics:<tag> ./build-team-analytics-service.sh
TA_UI_IMAGE=cvat/ui:<tag> TA_SERVICE_IMAGE=cvat/team-analytics:<tag> \
    TA_SCREENSHOT_DIR=<dir> verify/team-analytics-stack/run.sh cycle
```

For a new release, update the stack's pinned upstream commit, `Chart.lock`,
`chart-deps.sha256` and the approved image list in `stack.env` together. `cycle`
brings up a disposable CVAT and the service in their own namespace. It sends
events, waits for the service's own scheduled refresh, and checks figures and
refusals for every role. Its final run has the real UI annotate in headless
Chrome and finds each new record in ClickHouse. It checks the figures for that
work and for a synthetic hundred annotators and forty long-named projects. It
drives the page (period, filters, full view, trend comparison, narrow window)
and stops the service to check the error panel and annotation. Then the stack
is torn down. Inspect the screenshots as well as the exit status. The
detector record is sent through the API, because the stack runs no model
function. Record what ran and what stayed unverified in dated evidence.

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
