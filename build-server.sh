#!/usr/bin/env bash
# Builds the fork server image (ADR 0004): the stock CVAT server image with the two patched
# policies of the import (cvat/cvat/apps/engine/rules) copied over the stock ones
# (Dockerfile.server). The stock image must already be local: the script never pulls or
# pushes, and the build needs no network.
#
# The build is tagged IMAGE only after two checks, both with the server's own bundle builder
# (verify/policy_bundle.sh from-image) in one-off containers without network:
# - the built image's bundle holds the import's two patched policies, each once, byte for
#   byte (a copy to a directory the server does not read fails here);
# - the base image's bundle holds the four policy files the import carries exactly as the
#   import tag STOCK_TAG has them (a base of another release fails here).
# If either fails, no image is left under IMAGE: an earlier image under that tag is removed
# (only the tag, when the image has another one), the new build is removed unless another tag
# names it, and no archive is saved. The build cache stays.
set -euo pipefail

IMAGE="${IMAGE:-cvat/server:v2.82.0-fork-policies}"
BASE_IMAGE="${BASE_IMAGE:-cvat/server:v2.82.0}"
STOCK_TAG="${STOCK_TAG:-cvat-v2.82.0-widened}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE="$ROOT/verify/policy_bundle.sh"

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
    echo "import tag $STOCK_TAG not found; fetch it or set STOCK_TAG (docs/upstream-upgrade.md, section 1)" >&2
    exit 1
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

DOCKER_BUILDKIT=1 docker build \
    --pull=false \
    --network=none \
    --provenance=false \
    --build-arg "BASE_IMAGE=$BASE_IMAGE" \
    --iidfile "$work/id" \
    -f "$ROOT/Dockerfile.server" \
    "$ROOT/cvat/cvat/apps/engine/rules"
built="$(cat "$work/id")"

status=0
echo "checking the bundle of the build ($built) against the import's two patched policies" >&2
{ "$BUNDLE" from-image "$built" >"$work/fork.tar.gz" && "$BUNDLE" check <"$work/fork.tar.gz"; } || status=1
echo "checking the bundle of $BASE_IMAGE against the four policy files of $STOCK_TAG" >&2
{ "$BUNDLE" from-image "$BASE_IMAGE" >"$work/base.tar.gz" && "$BUNDLE" check-stock "$STOCK_TAG" <"$work/base.tar.gz"; } || status=1

if [ "$status" != 0 ]; then
    if docker image inspect "$IMAGE" >/dev/null 2>&1; then
        docker image rm "$IMAGE" >/dev/null || { echo "could not remove the earlier image under $IMAGE; remove it before use" >&2; exit 1; }
        echo "removed the earlier image under $IMAGE" >&2
    fi
    # Removed only while untagged: an identical build may be another tag's image.
    if [ "$(docker image inspect --format '{{len .RepoTags}}' "$built" 2>/dev/null)" = 0 ]; then
        docker image rm "$built" >/dev/null || echo "could not remove the untagged build $built" >&2
    fi
    echo "policy check failed: no image is left under $IMAGE and nothing was saved" >&2
    exit 1
fi

docker tag "$built" "$IMAGE"
echo "built $IMAGE ($built) on $BASE_IMAGE; its policies are the import's, its base's those of $STOCK_TAG"

# Only needed when the image has to cross the air gap
if [ "${SAVE:-0}" = 1 ]; then
    cd "$ROOT"
    docker save "$IMAGE" | gzip > "${IMAGE//[:\/]/-}.tar.gz"
    echo "saved ${IMAGE//[:\/]/-}.tar.gz"
fi
