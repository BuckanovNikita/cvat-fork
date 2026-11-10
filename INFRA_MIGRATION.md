# Infrastructure migration for cvat-fork

## Why this notice exists

The shared development stands managed by k8s-infra are being removed in one
sitting. This project's migration is delayed. When the k8s-infra wipe is carried
out (plan phase P3), tests that need those stands will fail until migrated.
No wipe date is set. Shared data is destroyed without backups or imports, and
the old service credentials, helper scripts and run-tag model are retired.
This repository does not consume those shared stands, so the wipe itself is
not expected to break its current verification stacks. Its maintained Compose
verification setup nevertheless needs the migration described here.

## What is affected here

The plan lists no shared-stand dependency for cvat-fork. Inspection of the
maintained launchers and verification files found Compose stacks rather than
the retired k8s-infra registry, run tags or storage paths.

- `verify/run.sh` starts and tears down a Compose CVAT stack and seeds it through
  Docker commands; its API is reached on `localhost:8181`.
- `verify/opa_issues.sh` launches stock and patched Compose stacks, uses Docker
  commands, and runs the issue/comment permission checks on `localhost:8281`.
- `verify/docker-compose.verify.yml` and
  `verify/docker-compose.opa-issues.yml` define fixed container names and expose
  ports 8181/8191 and 8281/8291 respectively.
- `verify/docker-compose.opa-patch.yml` mounts the local OPA rule patches into
  that verification stack. `docker-compose.override.yml` supplies deployment
  overrides and is another maintained Compose assumption to reconcile.
- `verify/seed.py`, `verify/opa_issues_seed.py` and
  `verify/opa_issues_check.py` are the verification consumers of these stacks.

## Platform available after the reset

k8s-infra retains ingress, the local-CA certificate, Docker Desktop's default
`hostpath` storage class and one exclusive GPU slot, without time-slicing.
The certificate covers single-label hosts directly under `k8s.docker.internal`
only; it does not cover deeper project subdomains. Wildcard name lookup is
available only if phase P4 proves it. Until then, use `kubectl port-forward`.
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
9. After P4 proves wildcard lookup, use a single-label host directly under
   `k8s.docker.internal` on the project's own Ingress with the platform
   certificate. Until then, and if P4 fails, use `kubectl port-forward`.

## Required outcome and workflow

Run verification in this project's own namespace with a quota and owned
teardown, replacing the Compose stacks under `verify/`. Keep no maintained
Compose launcher. Mirrored upstream content under `cvat/` stays untouched.
The deployment design and the golden verification matrix are this project's
decisions, not designs supplied by k8s-infra.

Carry the migration through this repository's own specification and verification
work. There is no root `AGENTS.md` or equivalent specification workflow here,
and no named Spec Kit or OpenSpec process. Use the existing verification under
`verify/` as the behavioral baseline and decide the migration's specification
and acceptance within this repository; this notice does not invent a workflow.

## Done when

The required outcome passes this repository's verification, the project owner
has been told it has moved, and the sweeper report shows its namespaces carrying
a quota. Then delete this file.

Plan: `/mnt/wsl/data/nkt/k8s-infra/docs/plans/2026-11-09-managed-infrastructure-reset.md`.
