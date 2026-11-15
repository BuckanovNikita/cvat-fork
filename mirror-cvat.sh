#!/usr/bin/env bash
# Builds .cvat-mirror.git: a bare mirror of cvat-ai/cvat holding only the paths the fork
# uses: the frontend build, the analytics components, upstream's lint configuration, the
# Helm chart and the four stock policy files. It is the source the cvat/ subtree is pulled
# from.
#
# The new mirror is built beside the existing one, in .cvat-mirror.git.new, and replaces it
# only after the clone and the filter both succeeded and the result holds a tag and the
# paths in REQUIRED below. A failed or refused run leaves the existing mirror as it was.
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
    # ClickHouse, Vector and Grafana setup; the chart reaches it through helm-chart/analytics
    components
    # upstream's lint configuration; eslint.config.mjs loads tests/.eslintrc.js
    eslint.config.mjs .eslintrc.cjs tests/.eslintrc.js .stylelintrc.json
    .prettierrc .prettierignore .editorconfig
    # the Helm chart
    helm-chart
    # the stock issue and comment policies and the two helper policies they import
    cvat/apps/engine/rules/issues.rego cvat/apps/engine/rules/comments.rego
    cvat/apps/iam/rules/utils.rego cvat/apps/organizations/rules/organizations.rego
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

# A run that succeeds on the wrong source (another repository, a moved layout) must not
# replace the mirror: the filtered result holds at least one tag, and upstream's default
# branch holds each of these paths. When upstream moves one of them, update PATHS and this
# list together.
REQUIRED=(
    package.json yarn.lock cvat-ui/package.json cvat-core/package.json
    components/analytics helm-chart/Chart.yaml
    cvat/apps/engine/rules/issues.rego cvat/apps/engine/rules/comments.rego
    cvat/apps/iam/rules/utils.rego cvat/apps/organizations/rules/organizations.rego
)
missing=0
if [ -z "$(git -C "$NEW" tag)" ]; then
    echo "the filtered mirror holds no tag" >&2
    missing=1
fi
if ! git -C "$NEW" rev-parse -q --verify 'HEAD^{commit}' >/dev/null; then
    echo "the filtered mirror has no default branch" >&2
    missing=1
else
    for p in "${REQUIRED[@]}"; do
        git -C "$NEW" cat-file -e "HEAD:$p" 2>/dev/null || { echo "the filtered mirror lacks $p" >&2; missing=1; }
    done
fi
if [ "$missing" != 0 ]; then
    echo "not replacing $(basename "$MIRROR"): the source does not look like CVAT's (UPSTREAM)" >&2
    exit 1
fi

# Swap. If the new mirror cannot take the name, the previous one gets it back.
if [ -e "$MIRROR" ]; then mv "$MIRROR" "$OLD"; fi
mv "$NEW" "$MIRROR" || { [ ! -e "$OLD" ] || mv "$OLD" "$MIRROR"; exit 1; }
rm -rf "$OLD"

echo "mirror ready: $MIRROR"
