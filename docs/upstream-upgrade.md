# Updating the CVAT fork

Use this procedure when taking a new CVAT release into the fork. The
[fork specification](fork-specification.md) defines the behavior to preserve
and lists the fork's delta inside upstream's paths. The repository is a
full-source fork joined to upstream's history
([ADR 0005](adr/0005-a-full-source-fork-joined-to-upstream-history.md)), so a
release is taken by merging its tag. The fork is on `v2.82.0`; `TARGET` below
is the release being taken (for example `v2.83.0`). Commands run from the
repository root unless stated otherwise.

## 1. Record the starting point

Inspect working and staged changes, the current branch, local `main` comparison
and cached remote-tracking state. Preserve unrelated work. Record whether
remote references have actually been fetched. Start the upgrade on a dedicated
branch from the intended clean fork revision.

The `upstream` remote is `https://github.com/cvat-ai/cvat.git` and has no
default fetch rule, so a routine fetch never brings in upstream's branches and
tags. Tags are fetched by name. On a fresh clone, add the remote without the
rule `git remote add` writes, and fetch the tag the fork is on: the check
pipeline, the policy tests and the stack's stock policy check compare with it,
and tags are not pushed.

```bash
git remote add upstream https://github.com/cvat-ai/cvat.git
git config --unset-all remote.upstream.fetch
git fetch --filter=blob:none --no-tags upstream refs/tags/v2.82.0:refs/tags/v2.82.0
```

`--no-tags` keeps the fetch from bringing every upstream tag that points into
the fetched history. Afterwards `git show-ref --tags` must differ from before
by exactly the fetched tag. Keep an existing release tag as it is; investigate
a tag that names another commit instead of force-updating it.

Inspect the current customization with:

```bash
git diff --name-status v2.82.0 HEAD
git diff v2.82.0 HEAD -- . ':!docs' ':!.scratch' ':!verify' ':!tools'
git log --first-parent --oneline v2.82.0..HEAD
```

The first command lists every path the fork added, changed or deleted against
the release, its own directories included; the second shows the changes
inside upstream's paths and the fork's root files. Both must match the
ownership list of the specification.

## 2. Merge the target release

Choose the target tag and record its full commit ID, resolving an annotated
tag to its commit. Review upstream's release changes relevant to the UI, the
policies, the Helm chart, the image build, server/database compatibility and
the upstream internals the specification lists (section 4, "Team Analytics").

```bash
git fetch --filter=blob:none --no-tags upstream "refs/tags/${TARGET}:refs/tags/${TARGET}"
git switch -c "upgrade/cvat-${TARGET}"
git merge --no-ff "${TARGET}"
```

Expect conflicts only where the fork and upstream both changed a file:

- The fork's edited upstream files: the seventeen UI files, the two policies
  and their two test configurations (the specification's ownership list).
  Resolve them against the specification, preserving new upstream behavior
  and keeping only the fork's changes.
- `.github/`: the fork deleted it. A file the release changes there is
  reported as deleted here and modified there; keep it deleted
  (`git rm <path>`). A file the release adds under `.github/` arrives without
  a conflict; remove it in the same merge.
- `cvat/settings/base.py` and `cvat/urls.py`: the fork's lines are appended at
  the end of each file. A release that changes the end of either file
  conflicts there; keep upstream's lines and the fork's block after them.
- `.gitignore`: the fork's block is appended after upstream's entries; resolve
  as for the settings.

Upstream's `README.md` is not edited by the fork and merges cleanly; the
fork's text is `README.fork.md`. Upstream's `Dockerfile` is not edited by the
fork either and merges cleanly; a change to it is ported into
`Dockerfile.server` in section 3.

Then confirm the fork's delta against the new tag:

```bash
git diff --name-status "${TARGET}" HEAD -- . ':!docs' ':!.scratch' ':!verify' ':!tools'
git diff "${TARGET}" HEAD -- cvat cvat-ui cvat-core helm-chart backend_entrypoint.d .gitignore
git status --short
```

The first list must be the specification's ownership list (the `.github/`
deletions, `.gitignore`, the edited and added upstream files, the fork's root
files) and nothing else. Include working and staged changes in the review
until all resolutions are committed, then repeat the comparison on the merge
commit. If upstream now provides an equivalent feature, verify the acceptance
scenarios before removing its local replacement.

## 3. Merge the policies and update the images

The issue and comment policies are edited in the tree
(`cvat/apps/engine/rules/issues.rego` and `comments.rego`, IAM-1), so the
merge of section 2 merges upstream's changes to them like any other file;
nothing is reapplied by hand. Each policy must come out of the merge as the
target's stock file plus the same two additions marked
`# Local patch (role floor):`, and nothing else, and each test configuration
as the target's file plus the fork's added rows:
`git diff "${TARGET}" HEAD -- cvat/apps/engine/rules` shows exactly those.
Retain the target's upstream context checks and filter wrapper, and compare
its helper policies (`cvat/apps/iam/rules/utils.rego`,
`cvat/apps/organizations/rules/organizations.rego`) with the old ones; the
merged tree carries all four files from one upstream revision. Then run the
issue and comment matrix's expectations against both sides with the new tag,
without a server:
`STOCK_TAG="${TARGET}" verify/team-analytics-stack/run.sh check-issue-policies patched`
and `... check-issue-policies stock`. Every stack `up` runs both as well.

Read the scopes of both stock policies in the target release against the
previous one. The added rule has no scope whitelist, so every scope upstream
adds to the issue or comment policy is granted to organization members at or
above the floor once the merge is committed. Decide for each new scope whether
that is wanted; if not, the added rule needs an exclusion, which is a change to
the specification. A new scope also needs its row in the test configuration.

Update the release in the default tags together. The tools read the release
tag as `STOCK_TAG` (`verify/policy_test.sh`, the stack's
`check-issue-policies`) and `UPSTREAM_TAG` (`tools/gate/ui-lint.sh`). Search
the fork's own files for the old release number, outside dated evidence and
the tracker:

```bash
git grep -n -F v2.82.0 -- $(git diff --name-only --diff-filter=AM "${TARGET}" HEAD -- . ':!docs/evidence' ':!.scratch')
```

At least these name it: `build-ui.sh` (the UI tag), `build-server.sh` (the
fork server tag, and the release whose `Dockerfile` it records),
`tools/gate/ui-lint.sh` (`UPSTREAM_TAG`), `verify/policy_test.sh`
(`STOCK_TAG`), `verify/policy_bundle.sh` (its usage text),
`verify/team_analytics_backend.sh` (its image), the stack's `stack.env` and
`run.sh`, and the commands of this document. Review upstream's `Dockerfile.ui`
build arguments and base-image name against the UI script's BuildKit override,
and its file list against `Dockerfile.ui.dockerignore`. Consult project
dependency configuration for compatible tools rather than adding version pins
to these instructions.

The fork server image is built by `Dockerfile.server`, the fork's port of
upstream's `Dockerfile` to Debian 12 (BUILD-1,
[ADR 0007](adr/0007-the-fork-builds-its-images-from-public-bases-the-server-on-debian-12.md)),
and `build-server.sh` refuses to build while upstream's `Dockerfile` differs
from the one the port was made from (`PORTED_FROM_SHA256` in the script). See
what the release changed in it:

```bash
git diff v2.82.0 "${TARGET}" -- Dockerfile
```

If nothing changed, nothing is ported. Otherwise port each change into the
matching stage of `Dockerfile.server`: Ubuntu package names become Debian 12's
(a package may have another name there, be in Debian's non-free component, or
be missing), and the commented deviations stay, each with its comment. A path
upstream's `COPY` gains is copied by its own `COPY` line and added to the list
of copied paths in `build-server.sh` (`COPIED`), which makes the build
context. Check the pinned bases against the change: a Python version upstream
moves to, or a Rust or Go version its stages name, needs a new base, pinned by
digest. All three bases are the defaults of `Dockerfile.server`'s `ARG`s:
`BASE_IMAGE` (Python), `RUST_IMAGE` and `GOLANG_IMAGE` (the Go image of
upstream's smokescreen stage, whose `FROM` names that `ARG`); the script
refuses one that is not pinned. Then record the hash of the
target's `Dockerfile` in `build-server.sh` as `PORTED_FROM_SHA256`:

```bash
sha256sum Dockerfile
```

A changed requirement under `cvat/requirements` needs no step of its own: the
build installs the tree's requirements. A new system library that a package
needs shows as a failed build or in the build's check for missing shared
libraries.

Build the fork server image from the merged tree. The build needs network
access, compiles FFmpeg and takes long; `MAKE_JOBS` sets the parallel jobs of
each compile step:

```bash
IMAGE="cvat/server:${TARGET}-fork" ./build-server.sh
```

It tags the image only when its six checks pass (BUILD-1): the bundle holds
the merged policies and, with analytics enabled, the Team Analytics policy;
the programs CVAT starts run on the venv's Python 3.12, supervisord runs and
`nginx -t` accepts the shipped nginx configuration; no shared library is
missing (judged by `ldd`'s output: any "not found" fails); Django sets up with
analytics on and off; and no model change lacks a migration. The checks build
and test the default configuration only: the `CLAM_AV=yes` and
`CVAT_DEBUG_ENABLED=yes` builds have never been built. A ported package from
Debian's non-free component goes in while that component is enabled, as
`unrar` does; the final image's apt sources have the main component only. Before it builds, it refuses the unported
`Dockerfile` above, a base not pinned by digest, and a tree with an untracked
file, or a tracked file missing, under the copied paths; an untracked file is
added or removed before building again. Check
its bundle as under "Policies" in section 4. Check added or renamed chart
services and images against the stack's render checks and image lists
([stack README](../verify/team-analytics-stack/README.md)). Update the
specification only for intentional behavior changes, and record their
acceptance evidence.

## 4. Verify the integrated changes

Run applicable checks once on the integrated result; rerun them only after
relevant changes or failures. Keep failures, warnings, skipped checks and their
reasons in dated evidence. No root Spec Kit or OpenSpec workflow exists in the
repository; use a native workflow if one is introduced later.

Upstream's own Django and REST suites are not part of the fork's checks. Its
REST test for issues, `tests/python/rest_api/test_issues.py`, encodes the
stock issue policy and disagrees with IAM-1. Upstream's Kubernetes test mode
flushes databases in whatever namespace the current kube context names; do not
run it against a shared cluster.

### Check pipeline

One command runs, from the repository root, every check that needs neither
ClickHouse nor a stack:

```bash
prek run --all-files
```

`prek.toml` holds the hooks, run one after another: ESLint and stylelint on
the fork's UI files, the type check, ruff on the fork's Python, black and
isort on the fork's code inside upstream's `cvat/` tree, the policy test on
the patched and on the stock policies, upstream's generated policy tests, and
the three fast frontend suites. A hook pipeline is a default the owner was not
asked about. No hook rewrites a file. The UI linters run the commands under
"Frontend" below on the tracked files of the five UI packages whose content
differs from the release tag (`tools/gate/ui-lint.sh`, `UPSTREAM_TAG`), so a
new file is checked once it is tracked. ruff reads only the fork's directories
that `ruff.toml` lists, never upstream's code; the Team Analytics app is among
them, for undefined names and unused imports. black and isort check
`cvat/apps/team_analytics`, `cvat/settings/base.py` and `cvat/urls.py` with
upstream's settings (the root `pyproject.toml`). Run the pipeline by its
command; do not install it as git hooks.

The three frontend suites run through `tools/gate/node-suite.sh`, which gives
every process of the run a memory limit (address space, `NODE_SUITE_MEMORY_KB`,
default 8 GiB) and every test a time limit (`NODE_SUITE_TEST_TIMEOUT_MS`,
default one minute), so a runaway test fails its suite instead of exhausting
the machine. Node's test runner has neither limit by default. Run a suite by
hand through the same wrapper, as the commands below do. The browser check of
the task legend (`BROWSER_BIN`) is not part of the pipeline and keeps its own
command. A browser does not start inside an address-space limit, so the task
progress hook passes `--may-start-browser`: for that suite alone, and only
while `BROWSER_BIN` is set, the wrapper leaves the memory limit off, says so
in one line, and keeps the time limit. The other two suites keep their memory
limit whatever the environment holds.

Prerequisites on a fresh checkout:

- `prek`, `uv`, `python3`, Node and Docker on the path; network on the first
  run, when `uv` installs ruff, black and isort into `tools/gate/.venv` as
  `tools/gate/uv.lock` locks them and Docker pulls the OPA image that
  `verify/policy_test.sh` names.
- The release tag (section 1; tags are not pushed).
- `node_modules` at the root and `verify/node_modules`, installed as under
  "Frontend" below.

Kept out of the pipeline, each a separate command with its own prerequisites:

- `verify/team_analytics_backend.sh`: the calculation tests, under "Team
  Analytics"; Docker, the fork server image built from the tree
  (`build-server.sh`) and the ClickHouse and Redis images.
- `verify/policy_bundle.sh`: the bundle check of the fork server image, under
  "Policies"; Docker and the built image.
- `verify/team-analytics-stack/run.sh cycle`: the stack, under "Team
  Analytics"; the two built images, a cluster and the reserved host port.
- `BROWSER_BIN=<browser> node --test verify/task_progress.cjs`: the browser
  check of the task legend, under "Frontend"; without `BROWSER_BIN` the
  pipeline's run skips it.

### Frontend

With the toolchain required by upstream's package configuration:

```bash
DISABLE_HUSKY=1 yarn install --immutable
npm ci --prefix verify
tools/gate/node-suite.sh verify/task_progress.cjs
SOURCE_MAPS_ENABLED=false yarn run build:cvat-ui
```

Lint and type-check the fork's UI code with upstream's own configuration at
the root (`eslint.config.mjs` with `.eslintrc.cjs`, `.stylelintrc.json`,
`cvat-ui/tsconfig.json`). Each command runs from the repository root on the
installed `node_modules`:

```bash
node node_modules/eslint/bin/eslint.js --max-warnings 0 --no-warn-ignored <files>
node node_modules/stylelint/bin/stylelint.mjs --max-warnings 0 <files>
node node_modules/typescript/bin/tsc -p cvat-ui/tsconfig.json
```

ESLint takes the `.ts` and `.tsx` files, stylelint the `.scss` files. Pass
only the UI files the fork added or edited, never the whole tree, and never
let `--fix` touch upstream's files: they stay as upstream wrote them. A finding
in an upstream line of a file the fork edited is left alone and recorded in the
dated evidence. The list compares with the release tag the fork is on
(`v2.82.0` until the merge of section 2 is committed, then `${TARGET}`); against
an older tag it would also list every UI file upstream changed since.
`tools/gate/ui-lint.sh` selects the same files from the working tree:

```bash
git diff --name-only --diff-filter=d v2.82.0 HEAD -- cvat-ui cvat-core cvat-canvas cvat-canvas3d cvat-data | grep -E '\.tsx?$'
git diff --name-only --diff-filter=d v2.82.0 HEAD -- cvat-ui cvat-core cvat-canvas cvat-canvas3d cvat-data | grep -E '\.scss$'
```

`--max-warnings 0` is the fork's addition: upstream's `yarn run lint` fails on
errors only, while the fork's files are kept free of warnings too, unused
disable directives among them. `--no-warn-ignored` keeps a path the
configuration ignores from counting as a warning. The type check is upstream's
`yarn run type-check` (`tsc -p cvat-ui/tsconfig.json`) and always covers the
whole UI. It resolves the workspace packages (`cvat-core`, `cvat-canvas`,
`cvat-canvas3d`, `cvat-data`) through the links in `node_modules`, so in a
worktree whose `node_modules` links to another checkout it checks against
that checkout's packages; run it where the dependencies are installed.

`npm ci --prefix verify` installs the frontend harness's own dependencies: the
browser environment (jsdom) that the two Team Analytics frontend suites below
load. `verify/package.json` declares it and `verify/package-lock.json` locks it;
upstream's manifest and lock are not involved. It goes to
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

`DISABLE_HUSKY=1` matches upstream's Dockerfile dependency installation and
avoids installing upstream's Git hooks. A host build does not prove image
packaging.

### Policies

The fork's policy test runs without starting CVAT, in a one-off container of
the OPA image (`OPA_IMAGE`, default the one the script names):

```bash
verify/policy_test.sh          # the tree's patched policies, patched expectations
verify/policy_test.sh stock    # the stock policies of STOCK_TAG, stock expectations
```

Both runs read the two resource policies and their two helper policies; the
patched run from the working tree, the stock run from the release tag
(`STOCK_TAG`, which follows the release as in section 3). Both must match
their own expectations; an identical result is not the goal because member
access differs.

Upstream's generated policy tests cover every app's policies in the tree, the
patched issue and comment policies and the Team Analytics policy among them.
Upstream's runner writes one test file per policy from the test
configurations beside it (the files are ignored by git), then OPA runs them
all, the rules directories named one by one:

```bash
python3 cvat/apps/iam/rules/tests/generate_tests.py
docker run --rm --network none --cpus=1 --memory=3g -v "$PWD:/mnt/src:ro" -w /mnt/src \
    openpolicyagent/opa:1.12.2 test --timeout 600s cvat/apps/*/rules
```

`verify/policy_generated.sh` runs the same two commands. The check pipeline
runs the policy test on both sides and the generated tests.
After a merge, a generated case that fails on the patched policies means that
upstream changed a policy or its configuration; resolve it against IAM-1. The
fork's configuration changes add rows and change none of upstream's.

Then check what the rebuilt fork server image serves. The bundle is built by the
server's own builder inside the image, so a policy installed where the server
does not read it shows here; `build-server.sh` runs the same checks and tags
nothing when one fails (an earlier image under the tag stays, unchecked by that
run, and the failure names its ID), and the stack checks the served bundle
again:

```bash
verify/policy_bundle.sh from-image <fork server tag> | verify/policy_bundle.sh check
verify/policy_bundle.sh from-image <fork server tag> analytics | verify/policy_bundle.sh check-analytics
```

The first check must report both policies equal to the tree's, the second the
Team Analytics policy as well. Each policy is compared by itself, byte for
byte; a marker in only one of them does not pass.

Check policy compilation with the same target helpers. If strict OPA lint fails,
compare stock and patched rules before classifying an inherited warning. Retain
the stock-versus-patched distinction in the recorded result.

### Team Analytics

Account for every file in the TA-1 integration map and the backend's touch
points. Check the upstream dependencies listed there against the target
release: the `events` table schema, the server's allowed client scopes and
working-time calculation, Vector's field allowlist, the cvat-core logger and
plugin wrapper, saved annotation event names, the header's plugin flag and
`admin` group, the selected organization in the UI's state, CVAT's minimum app
width, and the shortcut action names. A changed name breaks figures without an error, so
compare them, not only the build.

Read the release's changes to the upstream internals the app depends on (the
specification's list under "Upstream internals the fork depends on"):

```bash
git diff v2.82.0 "${TARGET}" -- \
    cvat/apps/iam/permissions.py cvat/apps/iam/middleware.py \
    cvat/apps/redis_handler/management/commands/syncperiodicjobs.py \
    cvat/settings/base.py cvat/requirements \
    cvat/apps/iam/models.py cvat/apps/engine/models.py \
    cvat/apps/organizations/apps.py cvat/apps/organizations/default_settings.py \
    cvat/apps/organizations/permissions.py cvat/apps/organizations/rules/organizations.rego \
    backend_entrypoint.sh backend_entrypoint.d \
    helm-chart/templates/_helpers.tpl helm-chart/templates/cvat_backend \
    cvat-core/src/server-proxy.ts cvat-core/src/axios-config.ts \
    cvat/apps/iam/rules/tests/generate_tests.py
```

Look for: a changed signature of `OpenPolicyAgentPermission` or of what
`PolicyEnforcer` calls; `load_app_iam_rules`; the names and format of
`RQ_QUEUES`, `PERIODIC_RQ_JOBS` and `REDIS_INMEM_SETTINGS`, and how
`syncperiodicjobs` reads them; the keys of `request.iam_context` and how the
middleware resolves an organization; the user model (`AUTH_USER_MODEL`, its
`username`, `first_name` and `last_name`) and the project model's `name`, which
the settings endpoints read, and a change in how upstream's migrations or
`migrate` treat an app's own migrations;
the format of the entry point's component files and `run worker`; the helper
templates and backend values the worker template uses (compare it with
upstream's other worker templates, which it is modelled on); new `rq` or
`django_rq` versions; `serverRequest`, the 429 retry and the text
`generateError` makes of an error body; the conventions of the generated
policy tests; and, for IAM-2, the setting `ORGANIZATIONS_MIN_ROLE_TO_CREATE`
(the fork's default `admin`, upstream's `user`), its environment variable
`CVAT_ORGANIZATIONS_MIN_ROLE_TO_CREATE`, the organizations app's taking of its
default only when the Django settings have none, and the policy's `create`
rule that reads it. A change there lets every `user` create organizations
again without an error; the stack's `check-org-creation` shows it. Most of these fail at merge, at the server image's build, at
the policy tests or on the stack; the error text and the retry fail nowhere
but in the page's behavior, so confirm them on the stack's page checks.

Two of the UI dependencies are orders of execution that no suite can see,
because both suites drive them in a fixed order. Read them in the target
release and confirm them in the stack run below:

- The canvas sends `canvas.groupmoved` and then the grabbed object's
  `canvas.dragshape` synchronously in one task, and the wrapper calls
  `groupMoved` before its handler's first `await`. If not, a group drag counts
  extra alignments with no error. The stack run's group drag, read back from
  the events table, shows it (ticket 27).
- The shown frame changes only through `changeFrameAsync`, and no navigation
  shortcut's handler waits for a later task before starting it. If not,
  navigation keys are counted for the wrong frames or stop counting. The stack
  run's held navigation key, compared with CVAT's `change:frame` events, shows
  it (ticket 27).

Build the two images from the integrated tree first: the calculation tests
run in the fork server image, and the stack runs both.

```bash
IMAGE="cvat/server:${TARGET}-fork" ./build-server.sh
IMAGE="cvat/ui:${TARGET}-fork" ./build-ui.sh
```

Run the three seams. The calculation tests need Docker, the fork server image
and the ClickHouse and Redis images. The two frontend seams need the root
`node_modules` and the harness's dependencies (`npm ci --prefix verify`, under
"Frontend" above); without the latter they fail and name what is missing, they
do not skip tests:

```bash
SERVER_IMAGE="cvat/server:${TARGET}-fork" verify/team_analytics_backend.sh   # calculation tests against a real ClickHouse
tools/gate/node-suite.sh verify/team_analytics_logging.cjs  # events the UI logging sends
tools/gate/node-suite.sh verify/team_analytics_page.cjs     # page with supplied responses
```

The calculation tests (`verify/team-analytics-backend/`) run the app's code in
a container of the fork server image (`SERVER_IMAGE`, by default the fork
server tag of the release the fork is on), with the working tree's
`cvat/apps/team_analytics` mounted over it, beside a throwaway ClickHouse and
a throwaway Redis, and remove all three when they end. Set `SERVER_IMAGE` to
the image just built and `CLICKHOUSE_IMAGE` to the ClickHouse version of the
target chart. If the image's Python, `clickhouse_connect`, `redis`, `rq` or
Django changed, check that the app still needs nothing beyond them.

Then run the stack once (`verify/team-analytics-stack/README.md`, which names
its image variables, its subcommands and its reserved host port):

```bash
verify/team-analytics-stack/run.sh cycle
```

For a new release, update the stack's chart dependency pins and image lists
together, as its README describes; the chart itself comes with the merge.
`cycle` brings up a disposable CVAT from the tree's chart on the two images,
with analytics and its worker, in its own namespace, runs the checks of `up`
(`check-worker` among them) and tears it down. The acceptance checks of the
backend path are not part of `up`; run them on a stack brought up with
`run.sh up`, then `run.sh down`:

```bash
verify/team-analytics-stack/run.sh check-cross-org
verify/team-analytics-stack/run.sh check-fixes page   # the page in a browser: filter bar, selectors, operations card, tooltips, settings
verify/team-analytics-stack/run.sh check-isolation   # or one part: worker-down, clickhouse-down, totals-dropped, redis-down
verify/team-analytics-stack/run.sh check-load          # needs the volume data (see the README)
verify/team-analytics-stack/run.sh check-analytics-off   # last: it leaves the stack with analytics disabled
```

`check-isolation` without a part runs all four, `redis-down` (the in-memory
Redis at zero: reads answer 503, then the refresh schedule and the figures come
back) last, because it restarts what depends on Redis.

`run.sh check-evidence STEP` (steps `rq-start-race`, `liveness`,
`killed-worker`, `idle-generation`, `two-replicas`, `off-then-on`) is the
one-off evidence run of the Team Analytics delivery, not part of every
upgrade: several steps upgrade the release in place, and each puts the
stack's own values back when it ends, also on a failure or an interrupt. The
stack's README says what each step judges.

Inspect the screenshots as well as the exit status.
Record what ran and what stayed unverified in dated evidence.

### Packaging and integration

The two images are built by their scripts (BUILD-1): `./build-ui.sh` with the
chosen `IMAGE`/`NODE_IMAGE` overrides, and `./build-server.sh` with
`IMAGE`/`MAKE_JOBS`. Both need network access; `build-server.sh` pulls only the
three bases `Dockerfile.server` pins, and no `cvat/` image. Use
`SAVE=1` only if an archive is needed, for example to carry an image to an
installation without network access. Inspect served assets in the built UI image and
check the fork server image's bundle (under "Policies"). Without touching the
cluster, `verify/team-analytics-stack/run.sh preflight` runs what `up` does
before its first change to the cluster: the image check, `check-issue-policies`
on both sides, the chart build with its pinned dependencies and the render
checks, once with analytics on (the worker required) and once with analytics
off (no worker); the stack's README has the full list.

All live verification runs on the test stack under "Team Analytics", in the
project's own namespace with a quota and its own teardown (`down`, or `cycle`).
It needs no shared deployment and creates nothing in the cluster outside its
namespace; `down` also stops only its own port-forward. Every subcommand that
talks to the stack over HTTP first checks that the host port is served by the
port-forward of the namespace it acts on, and refuses a port that does not
belong to that namespace. Clean up only what a run created.

## 5. Record and hand off

Obtain independent review of the integrated behavioral and permission changes
after verification. Record the upstream release tag and its commit, the merge
commit, the final fork revision, the remaining customization inventory
(`git diff --name-status "${TARGET}" HEAD`), commands/outcomes and unverified
acceptance scenarios in a dated file under `docs/evidence/`. Update the README
baseline link and specification integration map as needed. Keep historical
test counts and deployment results out of the evergreen specification.

Commit only task-owned changes using the repository's commit convention, with
safe mechanical formatting fixes separate from behavior changes. Publishing
or deployment requires its own authorization. Before an authorized deployment,
retain the prior UI and fork server images and deployment configuration, and plan
database backup/rollback according to the target upstream release; reverting
the merge alone does not undo server database migrations.

### An instance on a fork version that read `TEAM_ANALYTICS_TECHNICAL_ACCOUNTS`

Fork versions before the Technical accounts list read the list of technical
accounts from the environment variable `TEAM_ANALYTICS_TECHNICAL_ACCOUNTS`
(user names separated by commas). The fork no longer takes the list from it (it
only looks at it to warn, below): the list is kept
in Postgres and edited by an administrator in Team Analytics settings on the
page (TA-1). On such an instance:

- Write down the user names the variable holds before the upgrade.
- The migration `team_analytics 0001` creates the list's table; the entry
  point's `init` applies it with CVAT's other migrations, where analytics is
  enabled.
- After the upgrade the list is empty, so every account counts as a person
  until it is listed. An administrator opens Team Analytics, then Settings, and
  adds each account; the change applies to every past period at the next read,
  and nothing is recomputed.
- Remove the variable from the deployment (for example
  `cvat.backend.additionalEnv` or `cvat.backend.worker.teamAnalytics.additionalEnv`
  in the chart's values). While it is set, each process that loads the app logs
  a warning that it is ignored.
