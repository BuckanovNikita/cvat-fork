# 07: Server image from scratch

**What to build:** The fork server image is built from scratch, so that no Dockerfile of ours starts `FROM cvat/*` and the server runs on Debian 12 (item 9 of the spec).

- `Dockerfile.server` is rewritten as a full build on `python:3.12-slim-bookworm`, mirroring the stages of upstream's `Dockerfile`, which stays untouched: Rust 1.85 from a pinned `rust:1.85-slim-bookworm` stage; upstream's Python apt packages dropped; `libldap-2.5-0` and `libldap-dev`; `unrar` from non-free; no `ubuntu` user to delete; the virtual environment from `/usr/local/bin/python3`. There is no `Dockerfile.server.dockerignore`: `build-server.sh` builds from a temporary copy of the tracked files of the paths `Dockerfile.server` copies.
- Pulled images are pinned by digest in `Dockerfile.server`, as the defaults of its `ARG`s, so every `FROM` is pinned there: `python:3.12-slim-bookworm`, `rust:1.85-slim-bookworm` and `golang:1.27.2` (the stage upstream uses for smokescreen). `verify/team-analytics-stack/stack.env` does not list them, because the build script pulls them, not the stack; stock `cvat/server:v2.82.0` leaves it.
- Known deviation: Debian's `supervisor` package brings Debian's Python 3.11 beside the image's 3.12, which CVAT's code runs on. The build checks that `python3` resolves to 3.12 for every process under `supervisord/`.
- `build-server.sh` is rewritten: a context of tracked files with the untracked-file refusal kept, the overlay guards removed, a recorded hash of upstream's `Dockerfile` that refuses the build when a release changed it, then the two tree-policy bundle checks, `makemigrations --check`, an `ldd` scan of the virtual environment and `django.setup()` before tagging.
- `verify/team_analytics_backend.sh` runs the calculation suite on the fork image instead of stock `cvat/server:v2.82.0`; `verify/policy_bundle.sh` loses its check against the stock image on the build path.
- Docs: a new ADR 0007 superseding ADR 0004, BUILD-1, section 3 of `docs/upstream-upgrade.md` and `README.fork.md` (recorded as a docs handoff).

Every build before ticket 10 uses the work tag `cvat/server:v2.82.0-fork-wip`: the owner's stack runs `cvat/server:v2.82.0-fork` and never pulls, so a rebuild under that tag could reach it at a pod restart.

**Blocked by:** none.

**Status:** resolved

- [x] No Dockerfile of the fork has a `FROM cvat/` line, and every `FROM` of `Dockerfile.server` names an image pinned by digest in the Dockerfile or an earlier stage; upstream's `Dockerfile` is byte-identical to `v2.82.0`.
- [x] `IMAGE=cvat/server:v2.82.0-fork-wip ./build-server.sh` completes (heavy; run when the machine is free), and a change to upstream's `Dockerfile` makes it refuse.
- [x] Inside the image, every process under `supervisord/` runs Python 3.12, `makemigrations --check` passes, the `ldd` scan finds no missing library and `django.setup()` succeeds.
- [x] The one-time comparison with the present `cvat/server:v2.82.0-fork` (installed distributions, the `/opt/cvat` tree by hash, user, entry point, environment, key binaries) is kept as evidence with every difference explained.
- [x] The calculation suite passes on the work image (`verify/team_analytics_backend.sh`, heavy).
- [x] `stack.env` no longer lists stock `cvat/server:v2.82.0`, and does not list the build's three bases (`build-server.sh` pulls them).

## Comments

2026-11-16: Done in `d99757c4f`, `7b0c55d2b`, `8ab1195bc`, `99908d4d4` (ADR 0007), `aa9a4e659` and the review's fix `074f69d1a` (ldd judged by its output, the Go stage pinned in the Dockerfile, the apt sources restored, `nginx -t`). Shown: `Dockerfile.server`'s three bases are pinned by digest as `ARG` defaults; upstream's `Dockerfile` is unchanged from `v2.82.0`; the only `FROM cvat/` line in the tree is upstream's own `Dockerfile.ci`, unchanged and not built by the fork. The final build `7ead6d1cec4b` (from `2883bb8c1`) passed every check (policy bundles, Python 3.12 for every program, supervisord 4.2.5, `nginx -t`, 458 shared objects with nothing missing, Django set-up with analytics on and off, "No changes detected"); the refusal of a changed upstream `Dockerfile` hash rests only on the build lane's own report (provoked there before the first build, with no log kept in the evidence); it was not repeated for the record. The one-time comparison (against the first from-scratch image `baa5a8b72149`, the tree of `eadf981f7`) is kept with every difference explained; the calculation suite passed on the work image (370 tests). `stack.env` lists neither the stock server image nor the three bases. Not built: `CLAM_AV=yes` and `CVAT_DEBUG_ENABLED=yes`. Record: `docs/evidence/2026-11-16-open-lines-closed-and-admin-settings.md`.
