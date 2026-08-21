#!/usr/bin/env bash
# Builds .cvat-mirror.git: a bare mirror of cvat-ai/cvat holding only the paths needed to
# build the frontend image, plus the compose files the deployment needs. It is the source
# the cvat/ subtree is pulled from - roughly 25 MB of tree instead of 122 MB.
#
#   ./mirror-cvat.sh                 # refresh the mirror from upstream
#   git subtree pull --prefix cvat .cvat-mirror.git <tag> --squash
set -euo pipefail

UPSTREAM="${UPSTREAM:-https://github.com/cvat-ai/cvat.git}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIRROR="$ROOT/.cvat-mirror.git"

PATHS=(
    # workspace root, needed for yarn install --immutable
    .yarnrc.yml package.json yarn.lock .dockerignore LICENSE
    # the frontend build
    Dockerfile.ui cvat-data cvat-core cvat-canvas cvat-canvas3d cvat-ui
    # what the deployment mounts at runtime
    docker-compose.yml components
)

rm -rf "$MIRROR"
git clone --mirror "$UPSTREAM" "$MIRROR"

cd "$MIRROR"
# Drop anything that is not an upstream branch or tag, so local work never leaks in
git for-each-ref --format='%(refname)' refs/ |
    grep -vE '^refs/(heads|tags)/' |
    while read -r ref; do git update-ref -d "$ref"; done

python3 "$ROOT/tools/git-filter-repo" --force "${PATHS[@]/#/--path=}"

echo "mirror ready: $MIRROR"
