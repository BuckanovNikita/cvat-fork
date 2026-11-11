#!/usr/bin/env bash
# Builds the customised CVAT frontend image with CVAT's own Dockerfile, so the whole
# bundle is compiled inside the image. Needs network access for the npm registry,
# so run it outside the closed contour and transfer the result with docker save/load.
set -euo pipefail

IMAGE="${IMAGE:-cvat/ui:v2.74.1-progress-colors}"
# Dockerfile.ui builds on the floating node:lts-slim tag; pin it here so the image is
# reproducible. CVAT documents Node 20 as the minimum.
NODE_IMAGE="${NODE_IMAGE:-node:24.19.0-slim}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$ROOT/cvat"
# webpack does not clean its output directory, and cvat-ui/dist is part of the build
# context, so a stale host build would be copied into the image alongside the fresh one
git clean -xdqf -- cvat-ui/dist

DOCKER_BUILDKIT=1 docker build \
    --build-context "node:lts-slim=docker-image://$NODE_IMAGE" \
    --build-arg SOURCE_MAPS_ENABLED=false \
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
