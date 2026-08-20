#!/usr/bin/env bash
# Builds the customised CVAT frontend image. Needs network access for the npm registry,
# so run it outside the closed contour and transfer the result with docker save/load.
set -euo pipefail

IMAGE="${IMAGE:-cvat/ui:v2.59.1-progress-colors}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export COREPACK_ENABLE_DOWNLOAD_PROMPT=0
corepack enable --install-directory "$HOME/.npm-global/bin" yarn
export PATH="$HOME/.npm-global/bin:$PATH"

cd "$ROOT/cvat"
yarn install --immutable
DISABLE_SOURCE_MAPS=true yarn run build:cvat-ui

cd "$ROOT"
docker build -t "$IMAGE" -f Dockerfile.custom-ui .
docker save "$IMAGE" | gzip > "${IMAGE//[:\/]/-}.tar.gz"
echo "built $IMAGE -> ${IMAGE//[:\/]/-}.tar.gz"
