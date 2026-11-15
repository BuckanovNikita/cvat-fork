#!/usr/bin/env bash
# Builds the fork server image (ADR 0007): the whole CVAT backend built from the fork's tree by
# Dockerfile.server, a port of upstream's Dockerfile to Debian 12 with Python 3.12 from the
# official Python image. The server and every worker run this one image.
#
# The build needs network access: it pulls the pinned bases (the Python, Rust and Go images named
# in Dockerfile.server; nothing else: Dockerfile.server needs no external frontend image), downloads and compiles OpenH264 and FFmpeg, and downloads the Python
# packages. It never pushes. Run it outside the closed contour and transfer the result (SAVE=1).
#
# The build context is the tracked files of the paths Dockerfile.server copies, as they are in
# the working tree. The script refuses to build when
# - upstream's Dockerfile differs from the one Dockerfile.server was ported from
#   (PORTED_FROM_SHA256): a release changed it, and the port must be reviewed first
#   (docs/upstream-upgrade.md, section 3);
# - a file under the copied paths is not tracked (the image would lack it while the working
#   tree has it), or a tracked file there is missing from the working tree.
#
# MAKE_JOBS (default 5, upstream's make -j5) sets the parallel jobs of each compile step; the
# FFmpeg, wheel and Go stages run at the same time, so the build can use several times as many
# cores. The build goes to a temporary tag. IMAGE is tagged only after these checks, each in a
# one-off container without network:
# - the image's bundle, from the server's own builder (verify/policy_bundle.sh from-image), holds
#   the tree's two patched policies, each once, byte for byte;
# - with analytics enabled the bundle also holds the tree's Team Analytics policy;
# - python and python3 are the venv's Python 3.12, and so are django-admin and uvicorn, the
#   programs the process configuration starts; supervisord runs; nginx -t accepts the image's
#   configuration as the unprivileged user;
# - no shared object under /opt/venv and no FFmpeg or OpenH264 library under /usr/lib has a
#   dependency that is not found (the libraries a wheel bundles in its .libs directory are
#   loaded through the wheel's own modules and are scanned with them);
# - Django sets up on the production settings with CVAT_ANALYTICS=1 and with 0, with the Team
#   Analytics app installed and its API routed exactly when analytics is enabled;
# - makemigrations --check --dry-run with analytics enabled finds no model change without a
#   migration (it needs no database: it warns that it cannot reach one and goes on).
# If one fails, the script removes only what this run built (the temporary tag; the image goes
# with it unless another tag names it), tags nothing, saves nothing and exits non-zero. An
# earlier image under IMAGE is left as it is. The build cache stays.
set -euo pipefail

IMAGE="${IMAGE:-cvat/server:v2.82.0-fork}"
MAKE_JOBS="${MAKE_JOBS:-5}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE="$ROOT/verify/policy_bundle.sh"

# sha256 of upstream's Dockerfile (v2.82.0) that Dockerfile.server is a port of. After porting
# a release's changes into Dockerfile.server, record the hash of its Dockerfile here.
PORTED_FROM_SHA256=caee3eed999d8330d76128e1bde86ab635beb0907c9eacd5c9bf08a8aea8907f
# What Dockerfile.server copies from the context (cvat/ holds the requirements and nginx.conf).
COPIED=(
    backend_entrypoint.d cvat supervisord utils backend_entrypoint.sh
    components/analytics/clickhouse/init.py manage.py rqscheduler.py wait_for_deps.sh
)

if ! [[ "$MAKE_JOBS" =~ ^[1-9][0-9]*$ ]]; then
    echo "MAKE_JOBS must be a positive integer, not '$MAKE_JOBS'" >&2
    exit 1
fi

upstream_sha256="$(sha256sum "$ROOT/Dockerfile")"
upstream_sha256="${upstream_sha256%% *}"
if [ "$upstream_sha256" != "$PORTED_FROM_SHA256" ]; then
    echo "upstream's Dockerfile changed since Dockerfile.server was ported from it" >&2
    echo "  ported from sha256 $PORTED_FROM_SHA256, the tree has $upstream_sha256" >&2
    echo "port the change into Dockerfile.server, then record the new hash in this script" >&2
    echo "(docs/upstream-upgrade.md, section 3)" >&2
    exit 1
fi

# The three bases are the defaults of Dockerfile.server's ARGs; each must be pinned by digest.
bases=()
for arg in BASE_IMAGE RUST_IMAGE GOLANG_IMAGE; do
    ref="$(sed -n "s/^ARG $arg=//p" "$ROOT/Dockerfile.server")"
    if ! [[ "$ref" =~ ^[^@[:space:]]+@sha256:[0-9a-f]{64}$ ]]; then
        echo "Dockerfile.server: ARG $arg is not one image pinned by digest: '$ref'" >&2
        exit 1
    fi
    bases+=("$ref")
done

# Each git call's output goes to a variable first, so that a failing call stops the script.
untracked="$(git -C "$ROOT" ls-files --others --exclude-standard -- "${COPIED[@]}")"
if [ -n "$untracked" ]; then
    echo "these files are not tracked, so the image would lack them while the working tree has them:" >&2
    printf '%s\n' "$untracked" | sed 's/^/  /' >&2
    echo "add them (git add) or remove them, then build again" >&2
    exit 1
fi
deleted="$(git -C "$ROOT" ls-files --deleted -- "${COPIED[@]}")"
if [ -n "$deleted" ]; then
    echo "these tracked files are missing from the working tree:" >&2
    printf '%s\n' "$deleted" | sed 's/^/  /' >&2
    echo "restore them or remove them from the index (git rm), then build again" >&2
    exit 1
fi

work="$(mktemp -d)"
tmp_tag="cvat-server-build:$(date +%Y%m%d%H%M%S)-$$"
cleanup() {
    # Untags this run's build; the image goes only when no other tag (IMAGE included) names it.
    docker image rm "$tmp_tag" >/dev/null 2>&1 || true
    rm -rf "$work"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# The build context: the tracked files of the copied paths, as they are in the working tree.
mkdir "$work/context"
git -C "$ROOT" ls-files -z -- "${COPIED[@]}" >"$work/files"
tar -C "$ROOT" -cf - --null --verbatim-files-from -T "$work/files" | tar -C "$work/context" -xf -
chmod -R u=rwX,go=rX "$work/context"
echo "context: $(tr -cd '\0' <"$work/files" | wc -c) tracked files of ${COPIED[*]}" >&2

for ref in "${bases[@]}"; do
    docker pull -q "$ref" >/dev/null
done

DOCKER_BUILDKIT=1 docker build \
    --pull=false \
    --provenance=false \
    --build-arg "MAKE_JOBS=$MAKE_JOBS" \
    --iidfile "$work/id" \
    -t "$tmp_tag" \
    -f "$ROOT/Dockerfile.server" \
    "$work/context"
built="$(cat "$work/id")"

# A one-off container of the build: no network, one CPU, the image's own user.
in_image() {
    docker run --rm --network none --cpus=1 "$@"
}

status=0
echo "checking the bundle of the build ($built) against the tree's two patched policies" >&2
{ "$BUNDLE" from-image "$tmp_tag" >"$work/fork.tar.gz" && "$BUNDLE" check <"$work/fork.tar.gz"; } || status=1
echo "checking the bundle of the build with analytics enabled against the tree's Team Analytics policy" >&2
{ "$BUNDLE" from-image "$tmp_tag" analytics >"$work/analytics.tar.gz" && "$BUNDLE" check-analytics <"$work/analytics.tar.gz"; } || status=1

echo "checking that CVAT's programs run on the venv's Python 3.12" >&2
in_image --entrypoint /bin/sh "$tmp_tag" -c '
fail=0
for p in python python3 django-admin uvicorn; do
    w="$(command -v "$p")" || { echo "MISSING  $p is not on PATH"; fail=1; continue; }
    case "$w" in
    /opt/venv/bin/*) echo "ok       $p -> $w" ;;
    *) echo "WRONG    $p -> $w (not the venv)"; fail=1 ;;
    esac
done
for s in django-admin uvicorn; do
    w="$(command -v "$s")" || continue
    IFS= read -r line < "$w"
    case "$line" in
    "#!/opt/venv/bin/python"*) echo "ok       $s runs on ${line#??}" ;;
    *) echo "WRONG    $s runs on ${line#??}"; fail=1 ;;
    esac
done
for p in python python3; do
    v="$("$p" -c "import sys; print(\"%d.%d\" % sys.version_info[:2])")"
    if [ "$v" = 3.12 ]; then echo "ok       $p is Python $v"; else echo "WRONG    $p is Python $v"; fail=1; fi
done
if v="$(supervisord --version 2>&1)"; then echo "ok       supervisord $v"; else echo "WRONG    supervisord does not run: $v"; fail=1; fi
if v="$(nginx -t 2>&1)"; then echo "ok       nginx -t accepts /etc/nginx/nginx.conf"; else echo "WRONG    nginx -t: $v"; fail=1; fi
exit "$fail"' || status=1

echo "checking the shared objects of the venv and of FFmpeg for missing dependencies" >&2
in_image --entrypoint /bin/sh "$tmp_tag" -c '
libs="$(ls /usr/lib/libav*.so* /usr/lib/libsw*.so* /usr/lib/libopenh264.so* 2>/dev/null)"
if [ -z "$libs" ]; then echo "MISSING  no FFmpeg or OpenH264 library under /usr/lib"; exit 1; fi
{ printf "%s\n" "$libs"; find /opt/venv -type f -name "*.so*" ! -path "*.libs/*"; } | {
    n=0 bad=0
    while IFS= read -r f; do
        n=$((n + 1))
        # Judged by the output alone: ldd exits 0 when a dependency is not found.
        out="$(ldd "$f" 2>&1)" || true
        case "$out" in *"not a dynamic executable"*) continue ;; esac
        missing="$(printf "%s\n" "$out" | grep "not found")" || continue
        echo "MISSING  $f:"; printf "%s\n" "$missing"
        bad=1
    done
    if [ "$bad" = 0 ]; then echo "ok       $n shared objects scanned"; else echo "WRONG    $n shared objects scanned"; fi
    exit "$bad"
}' || status=1

for analytics in 1 0; do
    echo "checking that Django sets up on the production settings with CVAT_ANALYTICS=$analytics" >&2
    in_image -w /opt/cvat -e "CVAT_ANALYTICS=$analytics" --entrypoint /opt/venv/bin/python "$tmp_tag" -c '
import os, django
django.setup()
from django.apps import apps
from django.urls import Resolver404, resolve
on = os.environ["CVAT_ANALYTICS"] == "1"
installed = apps.is_installed("cvat.apps.team_analytics")
try:
    resolve("/api/team-analytics/status")
    routed = True
except Resolver404:
    routed = False
print(f"CVAT_ANALYTICS={int(on)}: Team Analytics app installed: {installed}, its API routed: {routed}")
raise SystemExit(0 if installed == on and routed == on else 1)' || status=1
done

echo "checking that no model change lacks a migration (no database: a warning about it is expected)" >&2
in_image -w /opt/cvat -e CVAT_ANALYTICS=1 --entrypoint /opt/venv/bin/python "$tmp_tag" \
    manage.py makemigrations --check --dry-run || status=1

if [ "$status" != 0 ]; then
    echo "a check failed: this run's build $built was not tagged and nothing was saved" >&2
    earlier="$(docker image inspect --format '{{.Id}}' "$IMAGE" 2>/dev/null || true)"
    if [ -z "$earlier" ]; then
        echo "no image is under $IMAGE" >&2
    elif [ "$earlier" = "$built" ]; then
        echo "$IMAGE still names $earlier, which is identical to this run's build and failed its checks" >&2
    else
        echo "$IMAGE still names the earlier build $earlier; this run did not check that build" >&2
    fi
    exit 1
fi

docker tag "$built" "$IMAGE"
echo "built $IMAGE ($built) from the fork's tree; every check passed"

# Only needed when the image has to cross the air gap
if [ "${SAVE:-0}" = 1 ]; then
    cd "$ROOT"
    docker save "$IMAGE" | gzip > "${IMAGE//[:\/]/-}.tar.gz"
    echo "saved ${IMAGE//[:\/]/-}.tar.gz"
fi
