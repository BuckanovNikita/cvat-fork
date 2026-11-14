#!/usr/bin/env bash
# Builds the fork server image (ADR 0004): the stock CVAT server image with the two patched
# policies of the import (cvat/cvat/apps/engine/rules) copied over the stock ones
# (Dockerfile.server). The stock image must already be local: the script never pulls or
# pushes, and the build needs no network.
set -euo pipefail

IMAGE="${IMAGE:-cvat/server:v2.82.0-fork-policies}"
BASE_IMAGE="${BASE_IMAGE:-cvat/server:v2.82.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$IMAGE" = "$BASE_IMAGE" ]; then
    echo "IMAGE must differ from BASE_IMAGE ($BASE_IMAGE): the stock tag is never overwritten" >&2
    exit 1
fi
# Without a local base the build would fetch it from the registry
if ! docker image inspect "$BASE_IMAGE" >/dev/null 2>&1; then
    echo "$BASE_IMAGE is not present locally; this script never pulls it" >&2
    exit 1
fi

DOCKER_BUILDKIT=1 docker build \
    --pull=false \
    --network=none \
    --provenance=false \
    --build-arg "BASE_IMAGE=$BASE_IMAGE" \
    -f "$ROOT/Dockerfile.server" \
    -t "$IMAGE" \
    "$ROOT/cvat/cvat/apps/engine/rules"

echo "built $IMAGE on $BASE_IMAGE"

# Only needed when the image has to cross the air gap
if [ "${SAVE:-0}" = 1 ]; then
    cd "$ROOT"
    docker save "$IMAGE" | gzip > "${IMAGE//[:\/]/-}.tar.gz"
    echo "saved ${IMAGE//[:\/]/-}.tar.gz"
fi
