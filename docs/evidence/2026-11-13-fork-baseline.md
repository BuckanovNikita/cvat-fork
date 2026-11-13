# Fork baseline — 2026-11-13

This is a source inventory for the documentation task, not a deployment report.
The maintained behavior is described in the [specification](../fork-specification.md).

## Revisions

| Item | Observed value |
| --- | --- |
| Fork revision inspected | `001eb3835f9defbdbaa1245c56f87c5d6c2a5735` |
| Branch | `main`; initially clean and identical to local `main` |
| Cached remote state | `origin/main` at the same commit; remote references were not fetched |
| Upstream release | CVAT `v2.82.0` |
| Raw upstream commit recorded by fork commit `525fdd6` | `02bd74fde78e00f770b7dfc3c33761ad9ab00095` |
| Filtered upstream commit (`cvat-v2.82.0`, also local `v2.82.0`) | `6545b83e7f340c3f16bc37094eeee398cdbfb76b` |
| Squashed import snapshot | `5e5af81d59b9883f33d4d5f4c2c65dd0bf9e0af2` |
| Subtree merge | `7ba828c4d095a6e4b3947087e89c7b0912fcc4d0` |
| Import tree (same for filtered tag and squash snapshot) | `6d4ee564079fdc5670e8f04733a2603cad9b2049` |

The raw upstream identity above is recorded provenance from local Git history;
it was not independently fetched from upstream during this documentation task.
The filtered tag and squash tree equality were checked locally.

## Complete subtree delta

`git diff --name-status cvat-v2.82.0 HEAD:cvat` at the inspected fork revision
reported exactly these paths (relative to `cvat/`):

```text
M components/analytics/clickhouse/init.py
M cvat-ui/src/actions/tasks-actions.ts
M cvat-ui/src/components/tasks-page/styles.scss
M cvat-ui/src/components/tasks-page/task-item.tsx
A cvat-ui/src/components/tasks-page/task-jobs-progress.tsx
M cvat-ui/src/containers/tasks-page/task-item.tsx
M cvat-ui/src/reducers/index.ts
M cvat-ui/src/reducers/tasks-reducer.ts
A cvat-ui/src/utils/task-jobs-summary.ts
```

The ClickHouse diff changes formatting only. The eight UI files implement the
summary feature. No current subtree delta exists in `Dockerfile.ui`,
`cvat-core`, `base.scss` or `index.html`; historical changes to those paths
should not be blindly reapplied.

Root-owned additions lie outside this comparison: `mirror-cvat.sh`, vendored
`tools/git-filter-repo`, `build-ui.sh`, `docker-compose.override.yml`, `opa/`,
`verify/`, `.gitignore`, `ruff.toml` and `INFRA_MIGRATION.md`. The documentation
added by this task also stays outside the imported tree.

## Historical evidence and relevant changes

These are reports in existing commits, not checks rerun for this document:

- `6e8dff7` imported v2.74.1 and adapted policy filters to prefix expressions and
  `org_filter_proof`; old rules failed the new filter-contract checks.
- `525fdd6` aligned v2.82.0 overlays and restored upstream organization-context
  guards. It records reproduction of sandbox-to-organization access using the
  previous overrides, successful frontend checks and both stock/patched OPA
  runs, and inherited strict OPA warnings. Packaging, live integration,
  database migration and deployment were not performed in that upgrade.
- `c56f2d0` records the twelve-combination palette change and successful mocked
  frontend regressions, TypeScript and webpack checks on 2026-11-12. It records
  missing ESLint configuration and no packaging/deployment.
- `001eb38` subsequently restored default legend text color and adjusted its
  regression assertion. Earlier verification cannot by itself establish this
  later revision's outcome.

## Verification limits observed in source

- `verify/task_progress.cjs` executes actual frontend source with mocked API
  boundaries and static React rendering, not a browser or live server.
- `verify/opa_issues_test.rego` evaluates synthetic policy inputs and needs
  matching full-source helper rules absent from the filtered subtree.
- `verify/opa_issues_check.py` prints HTTP observations without asserting the
  expected matrix. Some operations and list-content cases are not exercised.
- The bundle marker check in `verify/opa_issues.sh` can succeed for either rule;
  it does not prove both rule contents match or that OPA activated them.
- The frontend seed covers six stage/state combinations and a single-job task,
  not the complete palette. The live launchers use fixed project/container
  identities, unbounded readiness loops and explicit, volume-deleting teardown.
- `INFRA_MIGRATION.md` describes pending replacement of maintained Compose
  verification infrastructure. No migration was performed for this document.

## Checks executed for this documentation task

- Inspected source, Git history and the complete filtered-tree comparison;
  confirmed the filtered tag and squash snapshot share the recorded tree.
- `node --test verify/task_progress.cjs`: all 20 tests passed on the inspected
  application revision. This establishes the suite's mocked frontend behavior,
  including the final default-text-color correction; it does not establish
  browser appearance or live API compatibility.
- Independent source review checked the integrated documentation. A zero-total
  rendering statement was corrected to require zero fetched jobs as well;
  review confirmed the correction and found no other actionable issues.

This task did not refresh upstream, change application code, rerun the OPA
suite, type checking or production build, build images, launch services,
migrate data or deploy the fork.
