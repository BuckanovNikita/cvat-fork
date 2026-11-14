#!/usr/bin/env bash
# Builds .cvat-mirror.git: a bare mirror of cvat-ai/cvat holding only the paths needed to
# build the frontend image, plus the compose files the deployment needs. It is the source
# the cvat/ subtree is pulled from - roughly 25 MB of tree instead of 122 MB.
#
# The new mirror is built beside the existing one, in .cvat-mirror.git.new, and replaces it
# only after the clone and the filter both succeeded. A failed run leaves the existing
# mirror as it was.
#
#   ./mirror-cvat.sh                 # refresh the mirror from upstream
#   git subtree pull --prefix cvat .cvat-mirror.git <tag> --squash
set -euo pipefail

UPSTREAM="${UPSTREAM:-https://github.com/cvat-ai/cvat.git}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIRROR="$ROOT/.cvat-mirror.git"
NEW="$MIRROR.new"
OLD="$MIRROR.old"

PATHS=(
    # workspace root, needed for yarn install --immutable
    .yarnrc.yml package.json yarn.lock .dockerignore LICENSE
    # the frontend build
    Dockerfile.ui cvat-data cvat-core cvat-canvas cvat-canvas3d cvat-ui
    # what the deployment mounts at runtime
    docker-compose.yml components
)

# What a killed run can leave behind: an unfinished build, or the previous mirror set aside
# in the middle of the swap below.
rm -rf "$NEW"
if [ -e "$OLD" ]; then
    if [ -e "$MIRROR" ]; then rm -rf "$OLD"; else mv "$OLD" "$MIRROR"; fi
fi
trap 'rm -rf "$NEW"' EXIT

git clone --mirror "$UPSTREAM" "$NEW"

# Drop anything that is not an upstream branch or tag, so local work never leaks in
git -C "$NEW" for-each-ref --format='%(refname)' refs/ |
    { grep -vE '^refs/(heads|tags)/' || true; } |
    while read -r ref; do git -C "$NEW" update-ref -d "$ref"; done

(cd "$NEW" && python3 "$ROOT/tools/git-filter-repo" --force "${PATHS[@]/#/--path=}")

# Swap. If the new mirror cannot take the name, the previous one gets it back.
if [ -e "$MIRROR" ]; then mv "$MIRROR" "$OLD"; fi
mv "$NEW" "$MIRROR" || { [ ! -e "$OLD" ] || mv "$OLD" "$MIRROR"; exit 1; }
rm -rf "$OLD"

echo "mirror ready: $MIRROR"
