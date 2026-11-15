# Infrastructure migration for cvat-fork

## Why this notice exists

The shared development stands managed by k8s-infra are being removed in one
sitting. This project's migration is delayed. When the k8s-infra wipe is carried
out (plan phase P3), tests that need those stands will fail until migrated.
No wipe date is set. Shared data is destroyed without backups or imports, and
the old service credentials, helper scripts and run-tag model are retired.
This repository does not consume those shared stands, so the wipe itself is
not expected to break its current verification stacks. Its maintained Compose
verification setup nevertheless needed the migration described here.

## What was affected here

The plan lists no shared-stand dependency for cvat-fork. Inspection of the
maintained launchers and verification files found Compose stacks rather than
the retired k8s-infra registry, run tags or storage paths: two Compose
launchers (task progress, and the stock and patched issue and comment
permissions) with fixed container names and host ports, their Compose overlays,
the seed and check scripts they ran, and the deployment overlay that mounted the
copied policies into the server. All of them are now removed; the list of files
is in `docs/evidence/2026-11-15-compose-removed.md`, and the outcome below.

## Platform available after the reset

k8s-infra retains ingress, the local-CA certificate, Docker Desktop's default
`hostpath` storage class and one exclusive GPU slot, without time-slicing.
No wildcard name lookup will be provided; it was probed and dropped.
Only dedicated services have host names: ClearML web, API and files over trusted TLS,
and `mongodb.k8s.docker.internal` on port 27018. No current project uses them.
Request `nvidia.com/gpu: 1` only for a test that needs the GPU.
The platform no longer provisions project dependencies or manages Compose.

## Namespace lifetime

The sweeper deletes every namespace outside k8s-infra's protected list 48 hours
after creation, even while active, with no renewal. It also deletes namespaces
created before the last PC or Docker Desktop restart. It runs every 30 minutes.
A missing `ResourceQuota` is reported but neither exempts a namespace nor
causes deletion by itself. Deletion is based on age or restart.
The plan keeps deletion disabled until real restart proofs and arming are done.

## Rules for this migration

1. Deploy test infrastructure into this project's own namespaces using its own
   manifests or chart and its own teardown.
2. Use a distinct namespace prefix, such as `<project>-it-<id>`. Never reuse
   `clearml`, `mongodb`, `ingress-nginx`, `infra-janitor`, `default` or `kube-*`.
3. Give every created namespace a project-chosen `ResourceQuota`. Migration is
   incomplete without quotas, checked through the sweeper report. Add a
   `LimitRange` as well: CPU or memory quotas reject pods without requests.
4. Omit `storageClassName` or use the default storage class. Prefer `emptyDir`
   for disposable data. Remove references to `local-path` and
   `/mnt/wsl/data/k8s-volumes`.
5. Finish runs within the namespace lifetime and make tooling recreate missing
   namespaces, since they can disappear at 48 hours or after a restart.
6. Current workloads must not use the dedicated ClearML or FiftyOne services.
   Deploy this project's own ClearML and FiftyOne database wherever needed.
   Dedicated services require an owner-issued bundle file; none is issued at
   the start.
7. Request `nvidia.com/gpu: 1` only where a test needs it; only one slot exists.
8. Remove `INFRA_RUN_TAG`, `INFRA_PROJECT`, `K8S_INFRA_SKILL_DIR` and
   `INFRA_REGISTRY`, plus calls to `infra.py`, `clearml.py`, `mongodb.py`,
   `cvat.py`, `lakefs.py` and `postgres.py`, from code, skills and shell profiles.
9. Host access to a project's own services is by `kubectl port-forward`. Names a
   project invents do not resolve on the host; only the dedicated services have
   host names.

## Required outcome and workflow

Run verification in this project's own namespace with a quota and owned
teardown, replacing the Compose stacks under `verify/`. Keep no maintained
Compose launcher. Mirrored upstream content under `cvat/` stays untouched.

> Note, 2026-11-15: the mirrored `cvat/` import no longer exists. The
> repository became a full-source fork of upstream CVAT
> ([ADR 0005](docs/adr/0005-a-full-source-fork-joined-to-upstream-history.md)):
> upstream's tree is the repository root, and the fork's edits to upstream
> files are listed in
> [the fork specification](docs/fork-specification.md#ownership-and-scope).
The deployment design and the golden verification matrix are this project's
decisions, not designs supplied by k8s-infra.

Carry the migration through this repository's own specification and verification
work. There is no root `AGENTS.md` or equivalent specification workflow here,
and no named Spec Kit or OpenSpec process. Use the existing verification under
`verify/` as the behavioral baseline and decide the migration's specification
and acceptance within this repository; this notice does not invent a workflow.

## Outcome, 2026-11-15

The required outcome is in place in this repository:

- Live verification runs on the Kubernetes test stack
  (`verify/team-analytics-stack/`): its own namespace `cvat-ta-it-<run id>` with a
  `ResourceQuota` and a `LimitRange`, the default storage class, its own teardown
  (`run.sh down`, `run.sh cycle`), and a namespace that is recreated when missing
  or too old for the sweeper's lifetime. Host access is by `kubectl port-forward`.
- The two Compose checks moved onto that stack: the task progress check
  (`run.sh check-task-progress`) and the issue and comment permission matrix
  (`run.sh check-issues`), beside the check of the policy bundle the server serves
  (`run.sh check-policies`). Both live checks passed on the stack
  (`docs/evidence/2026-11-14-task-progress-on-stack.md`,
  `docs/evidence/2026-11-14-stack-issue-matrix.md`).
- The policies reach the server in the fork server image (ADR 0004), not through
  a mount.
- The Compose overlay, the three Compose verification files, the two Compose
  launchers, the seed and check scripts only they used, and the copied policy
  directory are deleted. No maintained Compose launcher is left.

Not yet shown, so this notice stays: a stack `up` run after the removal (the
live checks above ran before it), that the project owner has been told the
verification has moved, and that the sweeper report lists the stack's namespace
with its quota. None of these is recorded in this repository.

## Done when

The required outcome passes this repository's verification, the project owner
has been told it has moved, and the sweeper report shows its namespaces carrying
a quota. Then delete this file.

Plan: `<home>/k8s-infra/docs/plans/2026-11-09-managed-infrastructure-reset.md`.
