#!/usr/bin/env bash
# Builds the fork server image (ADRs 0004 and 0006): the stock CVAT server image of the release
# the fork is based on, with the fork's backend files copied over it (Dockerfile.server). Those
# are the tracked files under cvat/ and backend_entrypoint.d/ that differ from the release tag
# (STOCK_TAG) in the working tree: the two patched policies, the Team Analytics app, its wiring
# in cvat/settings/base.py and cvat/urls.py, and the worker's component file. The stock image
# must already be local: the script never pulls or pushes, and the build needs no network.
#
# The image stands in for a full build of the fork's tree only while those files are the fork's
# whole difference in what the server image is made of. The script refuses to build when
# - the fork deleted or renamed a file under cvat/ or backend_entrypoint.d/ (a copy cannot delete),
# - a file there is not tracked (the image is made of tracked files; the working tree would differ), or
# - anything else the stock image is built from differs from the release: the Python
#   requirements, the entry point, the process configuration, the other copied sources, or
#   upstream's Dockerfile. Such a change needs upstream's own build.
#
# The build is tagged IMAGE only after three checks, each with the server's own bundle builder
# (verify/policy_bundle.sh from-image) in one-off containers without network:
# - the built image's bundle holds the tree's two patched policies, each once, byte for byte
#   (a copy to a directory the server does not read fails here);
# - with analytics enabled, the built image's bundle also holds the Team Analytics policy, so
#   the app is installed and loads its rules;
# - the base image's bundle holds the two policies and their two helpers exactly as the
#   upstream release tag STOCK_TAG has them (a base of another release fails here).
# If one fails, the script removes only what this run built (unless a tag names it), tags
# nothing, saves nothing and exits non-zero. An earlier image under IMAGE is left as it is: the
# failure names its ID and says that this run did not check it. The build cache stays.
set -euo pipefail

IMAGE="${IMAGE:-cvat/server:v2.82.0-fork}"
BASE_IMAGE="${BASE_IMAGE:-cvat/server:v2.82.0}"
STOCK_TAG="${STOCK_TAG:-v2.82.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE="$ROOT/verify/policy_bundle.sh"

# What the image takes from the fork's tree.
COPIED=(cvat backend_entrypoint.d)
# What else upstream's Dockerfile makes the server image of. Any difference from the release
# here is not in a copy of files: cvat/requirements is under cvat/, but a changed requirement
# is a package the stock image does not have.
BUILT_FROM=(
    Dockerfile cvat/requirements backend_entrypoint.sh supervisord utils manage.py
    rqscheduler.py wait_for_deps.sh components/analytics/clickhouse/init.py cvat/nginx.conf
)

if [ "$IMAGE" = "$BASE_IMAGE" ]; then
    echo "IMAGE must differ from BASE_IMAGE ($BASE_IMAGE): the stock tag is never overwritten" >&2
    exit 1
fi
# Without a local base the build would fetch it from the registry
if ! docker image inspect "$BASE_IMAGE" >/dev/null 2>&1; then
    echo "$BASE_IMAGE is not present locally; this script never pulls it" >&2
    exit 1
fi
if ! git -C "$ROOT" rev-parse -q --verify "$STOCK_TAG^{commit}" >/dev/null; then
    echo "upstream tag $STOCK_TAG not found; fetch it or set STOCK_TAG (docs/upstream-upgrade.md, section 1)" >&2
    exit 1
fi

# Each git call's output goes to a variable first, so that a failing call stops the script.
# --no-renames throughout: a renamed file is one deleted and one added, and both must be seen.
needs_full_build="$(git -C "$ROOT" diff --no-renames --name-only "$STOCK_TAG" -- "${BUILT_FROM[@]}")"
if [ -n "$needs_full_build" ]; then
    echo "these differ from $STOCK_TAG and are not something a copy of files can deliver:" >&2
    printf '%s\n' "$needs_full_build" | sed 's/^/  /' >&2
    echo "the fork server image cannot stand in for upstream's own build of this tree" >&2
    exit 1
fi
deleted="$(git -C "$ROOT" diff --no-renames --name-only --diff-filter=D "$STOCK_TAG" -- "${COPIED[@]}")"
if [ -n "$deleted" ]; then
    echo "the fork deleted these files of $STOCK_TAG, which copying over the stock image cannot do:" >&2
    printf '%s\n' "$deleted" | sed 's/^/  /' >&2
    exit 1
fi
untracked="$(git -C "$ROOT" ls-files --others --exclude-standard -- "${COPIED[@]}")"
if [ -n "$untracked" ]; then
    echo "these files are not tracked, so the image would lack them while the working tree has them:" >&2
    printf '%s\n' "$untracked" | sed 's/^/  /' >&2
    echo "add them (git add) or remove them, then build again" >&2
    exit 1
fi
changed="$(git -C "$ROOT" -c core.quotePath=off diff --no-renames --name-only --diff-filter=AMT "$STOCK_TAG" -- "${COPIED[@]}")"
if [ -z "$changed" ]; then
    echo "nothing under ${COPIED[*]} differs from $STOCK_TAG: there is no fork server image to build" >&2
    exit 1
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
# The build context: exactly those files, as they are in the working tree, at their paths.
mkdir "$work/context"
printf '%s\n' "$changed" | tar -C "$ROOT" -cf - --verbatim-files-from -T - | tar -C "$work/context" -xf -
chmod -R u=rwX,go=rX "$work/context"
echo "copying $(printf '%s\n' "$changed" | wc -l) files of the fork's tree over $BASE_IMAGE" >&2

# The image under IMAGE before this run, if any; a failed check leaves it in place.
earlier="$(docker image inspect --format '{{.Id}}' "$IMAGE" 2>/dev/null || true)"

DOCKER_BUILDKIT=1 docker build \
    --pull=false \
    --network=none \
    --provenance=false \
    --build-arg "BASE_IMAGE=$BASE_IMAGE" \
    --iidfile "$work/id" \
    -f "$ROOT/Dockerfile.server" \
    "$work/context"
built="$(cat "$work/id")"

status=0
echo "checking the bundle of the build ($built) against the tree's two patched policies" >&2
{ "$BUNDLE" from-image "$built" >"$work/fork.tar.gz" && "$BUNDLE" check <"$work/fork.tar.gz"; } || status=1
echo "checking the bundle of the build with analytics enabled against the tree's Team Analytics policy" >&2
{ "$BUNDLE" from-image "$built" analytics >"$work/analytics.tar.gz" && "$BUNDLE" check-analytics <"$work/analytics.tar.gz"; } || status=1
echo "checking the bundle of $BASE_IMAGE against the four policy files of $STOCK_TAG" >&2
{ "$BUNDLE" from-image "$BASE_IMAGE" >"$work/base.tar.gz" && "$BUNDLE" check-stock "$STOCK_TAG" <"$work/base.tar.gz"; } || status=1

if [ "$status" != 0 ]; then
    # Removed only while untagged: an identical build may be another tag's image, or the earlier one.
    if [ "$(docker image inspect --format '{{len .RepoTags}}' "$built" 2>/dev/null)" = 0 ]; then
        docker image rm "$built" >/dev/null || echo "could not remove the untagged build $built" >&2
    fi
    echo "policy check failed: this run's build $built was not tagged and nothing was saved" >&2
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
echo "built $IMAGE ($built) on $BASE_IMAGE; its policies are the tree's, its base's those of $STOCK_TAG"

# Only needed when the image has to cross the air gap
if [ "${SAVE:-0}" = 1 ]; then
    cd "$ROOT"
    docker save "$IMAGE" | gzip > "${IMAGE//[:\/]/-}.tar.gz"
    echo "saved ${IMAGE//[:\/]/-}.tar.gz"
fi
