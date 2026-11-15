# 07: Server image from scratch

**What to build:** The fork server image is built from scratch, so that no Dockerfile of ours starts `FROM cvat/*` and the server runs on Debian 12 (item 9 of the spec).

- `Dockerfile.server` is rewritten as a full build on `python:3.12-slim-bookworm`, mirroring the stages of upstream's `Dockerfile`, which stays untouched: Rust 1.85 from a pinned `rust:1.85-slim-bookworm` stage; upstream's Python apt packages dropped; `libldap-2.5-0` and `libldap-dev`; `unrar` from non-free; no `ubuntu` user to delete; the virtual environment from `/usr/local/bin/python3`. A new `Dockerfile.server.dockerignore` goes with it.
- Pulled images are pinned by digest: `python:3.12-slim-bookworm`, `rust:1.85-slim-bookworm` and `golang:1.27.2` (the stage upstream uses for smokescreen). They join the approved pulls in `verify/team-analytics-stack/stack.env`; stock `cvat/server:v2.82.0` leaves it.
- Known deviation: Debian's `supervisor` package brings Debian's Python 3.11 beside the image's 3.12, which CVAT's code runs on. The build checks that `python3` resolves to 3.12 for every process under `supervisord/`.
- `build-server.sh` is rewritten: a context of tracked files with the untracked-file refusal kept, the overlay guards removed, a recorded hash of upstream's `Dockerfile` that refuses the build when a release changed it, then the two tree-policy bundle checks, `makemigrations --check`, an `ldd` scan of the virtual environment and `django.setup()` before tagging.
- `verify/team_analytics_backend.sh` runs the calculation suite on the fork image instead of stock `cvat/server:v2.82.0`; `verify/policy_bundle.sh` loses its check against the stock image on the build path.
- Docs: a new ADR 0007 superseding ADR 0004, BUILD-1, section 3 of `docs/upstream-upgrade.md` and `README.fork.md` (recorded as a docs handoff).

Every build before ticket 10 uses the work tag `cvat/server:v2.82.0-fork-wip`: the owner's stack runs `cvat/server:v2.82.0-fork` and never pulls, so a rebuild under that tag could reach it at a pod restart.

**Blocked by:** none.

**Status:** ready-for-agent

- [ ] No Dockerfile of the fork has a `FROM cvat/` line, and every `FROM` names an image pinned by digest; upstream's `Dockerfile` is byte-identical to `v2.82.0`.
- [ ] `IMAGE=cvat/server:v2.82.0-fork-wip ./build-server.sh` completes (heavy; run when the machine is free), and a change to upstream's `Dockerfile` makes it refuse.
- [ ] Inside the image, every process under `supervisord/` runs Python 3.12, `makemigrations --check` passes, the `ldd` scan finds no missing library and `django.setup()` succeeds.
- [ ] The one-time comparison with the present `cvat/server:v2.82.0-fork` (installed distributions, the `/opt/cvat` tree by hash, user, entry point, environment, key binaries) is kept as evidence with every difference explained.
- [ ] The calculation suite passes on the work image (`verify/team_analytics_backend.sh`, heavy).
- [ ] `stack.env` approves the three new pulls and no longer lists stock `cvat/server:v2.82.0`.

## Comments
