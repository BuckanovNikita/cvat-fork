#!/usr/bin/env bash
# Builds the Team Analytics service image from the stock CVAT server image, with the service
# code and its SQL copied in (team-analytics/Dockerfile). No dependency is installed, so the
# build needs no network once the base image is local.
set -euo pipefail

IMAGE="${IMAGE:-cvat/team-analytics:v2.82.0}"
BASE_IMAGE="${BASE_IMAGE:-cvat/server:v2.82.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DOCKER_BUILDKIT=1 docker build \
    --build-arg "BASE_IMAGE=$BASE_IMAGE" \
    -f "$ROOT/team-analytics/Dockerfile" \
    -t "$IMAGE" \
    "$ROOT/team-analytics/service"

echo "built $IMAGE on $BASE_IMAGE"

# Only needed when the image has to cross the air gap
if [ "${SAVE:-0}" = 1 ]; then
    cd "$ROOT"
    docker save "$IMAGE" | gzip > "${IMAGE//[:\/]/-}.tar.gz"
    echo "saved ${IMAGE//[:\/]/-}.tar.gz"
fi
