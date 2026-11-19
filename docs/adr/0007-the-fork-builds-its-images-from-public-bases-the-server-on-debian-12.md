---
status: accepted
---

# The fork builds its images from public bases, the server on Debian 12 with Python 3.12

The fork server image was the stock CVAT release image with the fork's backend files copied over it (ADR 0004, as amended by ADR 0006). It depended on a CVAT image as its base and could not take a changed Python requirement, a deleted file or a changed process configuration: the build refused each of those. On 2026-11-15 the owner decided that no Dockerfile of the fork starts from a `cvat/` image, and that the server image is built from scratch on Debian 12. `Dockerfile.server` is a fork-owned port of upstream's `Dockerfile`, stage for stage, on `python:3.12-slim-bookworm`: the official Python image gives Python 3.12, the version upstream builds and pins its requirements for, on Debian 12. Rust for the Datumaro wheel comes from `rust:1.85-slim-bookworm`, smokescreen from the Go image upstream names, and every base is pinned by digest. Upstream's own `Dockerfile` stays as upstream wrote it.

This supersedes ADR 0004's image. What still holds of ADR 0004 and ADR 0006: the chart has one backend image setting, so the server and every worker run this one image; the image carries the fork's backend tree, the patched issue and comment policies and the Team Analytics app with its wiring and component file, at upstream's paths; it is rebuilt on every upstream upgrade and whenever the fork's backend changes, and must be present on the node.

## Considered Options

- **The overlay on the stock image (ADR 0004, as built).** No compile and no network for the build. Rejected by the owner: it depends on a CVAT image as its base and cannot take a changed requirement.
- **Upstream's own `Dockerfile` with `ubuntu:24.04`.** Nothing to port and nothing to re-port. Not chosen: the owner wants Debian 12.
- **Plain `debian:12` with a Python built in the image.** The same Python 3.12, with its build and patch releases to maintain in the fork.
- **Plain `debian:12` with Debian's Python 3.11.** Upstream neither builds nor pins its requirements for 3.11.

## Consequences

- The build needs network access: it pulls the pinned bases, downloads and compiles OpenH264 and FFmpeg, and builds the Datumaro and python-ldap wheels from source. It takes long, and its compile steps run in parallel stages; `build-server.sh` takes the job count (`MAKE_JOBS`, upstream's 5 by default). It runs outside the closed contour, and the image crosses as a saved archive.
- `Dockerfile.server` must be re-ported whenever upstream's `Dockerfile` changes. `build-server.sh` holds the hash of the upstream `Dockerfile` it was ported from and refuses to build when the tree's differs, so a release merge forces that review (`docs/upstream-upgrade.md`, section 3).
- The image is not byte-for-byte upstream's: it has Debian 12's glibc and system packages where upstream has Ubuntu 24.04's, nginx 1.22 for 1.24, unrar from Debian's non-free component. Debian's `supervisor` package runs on Debian's own Python, so the image holds a second interpreter, Python 3.11, in `/usr/bin`, used only by supervisord. Every program CVAT starts resolves `python`, `python3` and its entry points to the venv's Python 3.12, and the build checks that before it tags the image.
- The build checks the image before tagging it: the policy bundle from the server's own builder, the interpreters, missing shared-library dependencies, Django set-up with analytics on and off, and no model change without a migration. The overlay's guards (no deleted file, nothing outside the copied paths changed since the release) go with the overlay; the stock image's bundle is no longer checked.
- The calculation suite runs in the fork server image instead of the stock one.
- The UI image stays upstream's `Dockerfile.ui`: a Node build stage and an Alpine nginx runtime, neither of them a CVAT image. The chart's third-party images, `cvat/postgresql` and `cvat/clickhouse` among them, are pulled unmodified and are the base of no Dockerfile of the fork; they are untouched.

## Amendments, 2026-11-17

- **"Public bases" means the defaults, not the only possibility.** The three bases still default to public references — `BASE_IMAGE` to `python:3.12-slim-bookworm`, `RUST_IMAGE` to `rust:1.85-slim-bookworm`, `GOLANG_IMAGE` to the Go version upstream's smokescreen stage names — and the default build is the public build this record describes. Every input that a build inside a closed network has to supply is now an argument with a public default: `BASE_IMAGE`, `RUST_IMAGE`, `GOLANG_IMAGE` and, in the UI image, `NODE_IMAGE` and `NGINX_IMAGE`, together with `APT_REMOTE`, `APT_SECURITY_REMOTE`, `PIP_INDEX`, `GO_PROXY`, `CARGO_INDEX`, `GITHUB_PROXY` and `NPM_REGISTRY`. The same Dockerfiles and the same build scripts build in both places, and nothing of the closed network is committed ([ADR 0008](0008-the-fork-is-the-original-for-two-repositories.md)).
- **No base is pinned by digest.** This record's "every base is pinned by digest", and its consequence that the build "pulls the pinned bases", no longer hold. A base is a reference: a tag is accepted, a digest is not required of it, and `build-server.sh` records in its log the digest each reference resolved to — a tag moves, so the log rather than the file is the record of what was built from.
- **The build no longer has to run outside the closed contour.** The consequence above that it "runs outside the closed contour, and the image crosses as a saved archive" describes the default path only: with the perimeter arguments supplied, `Dockerfile.server` builds inside the network, and `SAVE=1` stays the way to carry an image across an air gap.
- **The UI base is an argument too.** The Node version of the build stage is `NODE_IMAGE`, passed by `build-ui.sh` as a build argument, and the nginx runtime is `NGINX_IMAGE`; the build-context override is gone with it. What this record says about the UI image's two stages stands.
