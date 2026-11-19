#!/usr/bin/env bash
# Builds the customised CVAT frontend image with CVAT's own Dockerfile, so the whole
# bundle is compiled inside the image. The build context is the repository root, cut down
# to the frontend packages by Dockerfile.ui.dockerignore.
#
# With no overrides the build pulls the public bases and installs from the public npm registry.
# The build inside a closed network uses the same files: every input that network has to supply is
# a build argument of Dockerfile.ui and an environment variable here of the same name, passed
# through when it is set. Nothing of such a network lives in this script or in the Dockerfile.
#
#   NODE_IMAGE     the build stage's base     default here: node:24.19.0-slim
#   NGINX_IMAGE    the runtime stage's base   default: the ARG default in Dockerfile.ui
#   NPM_REGISTRY   npm, yarn and corepack     default: each tool's own registry
#
# SAVE=1 packages the result for transfer; the build never pushes.
set -euo pipefail

IMAGE="${IMAGE:-cvat/ui:v2.82.0-fork}"
# Dockerfile.ui bases on the floating node:lts-slim tag; pin it here so the image is
# reproducible. CVAT documents Node 20 as the minimum.
NODE_IMAGE="${NODE_IMAGE:-node:24.19.0-slim}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$ROOT"
# webpack does not clean its output directory, and cvat-ui/dist is part of the build
# context, so a stale host build would be copied into the image alongside the fresh one
git clean -xdqf -- cvat-ui/dist

build_args=(--build-arg "NODE_IMAGE=$NODE_IMAGE" --build-arg SOURCE_MAPS_ENABLED=false)
set_args=()
# NGINX_IMAGE and NPM_REGISTRY are passed only when the environment sets them, so that an unset
# variable keeps the ARG's public default.
for arg in NGINX_IMAGE NPM_REGISTRY; do
    value="${!arg:-}"
    if [ -n "$value" ]; then
        set_args+=("$arg")
        build_args+=(--build-arg "$arg=$value")
    fi
done
if [ "${#set_args[@]}" -gt 0 ]; then
    echo "inputs from the environment: ${set_args[*]}" >&2
fi

DOCKER_BUILDKIT=1 docker build \
    "${build_args[@]}" \
    -f Dockerfile.ui \
    -t "$IMAGE" \
    .

echo "built $IMAGE on $NODE_IMAGE"

# Only needed when the image has to cross the air gap
if [ "${SAVE:-0}" = 1 ]; then
    cd "$ROOT"
    docker save "$IMAGE" | gzip > "${IMAGE//[:\/]/-}.tar.gz"
    echo "saved ${IMAGE//[:\/]/-}.tar.gz"
fi
