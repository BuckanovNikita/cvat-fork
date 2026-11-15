#!/usr/bin/env bash
# Policy test for the issue and comment policies, without a running CVAT.
#
#   verify/policy_test.sh            patched policies of the working tree, patched expectations
#   verify/policy_test.sh stock      stock policies of STOCK_TAG, stock expectations
#
# Both runs read the two resource policies and their two helper policies; the
# patched run from the working tree, the stock run from the upstream release tag
# the fork is based on. Needs Docker and the OPA image (OPA_IMAGE, default the
# chart's image); no network, no outside checkout.
set -euo pipefail

mode="${1:-patched}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="${OPA_IMAGE:-openpolicyagent/opa:1.12.2}"
stock_tag="${STOCK_TAG:-v2.82.0}"

policies=(
    cvat/apps/engine/rules/issues.rego
    cvat/apps/engine/rules/comments.rego
    cvat/apps/iam/rules/utils.rego
    cvat/apps/organizations/rules/organizations.rego
)

mounts=(-v "$root/verify/opa_issues_test.rego:/test/opa_issues_test.rego:ro")
args=(/test/opa_issues_test.rego)

case "$mode" in
patched)
    for p in "${policies[@]}"; do
        mounts+=(-v "$root/$p:/policies/$p:ro")
        args+=("/policies/$p")
    done
    ;;
stock)
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    for p in "${policies[@]}"; do
        mkdir -p "$tmp/$(dirname "$p")"
        git -C "$root" show "$stock_tag:$p" >"$tmp/$p"
        args+=("/policies/$p")
    done
    echo '{"expected":{"patched":false}}' >"$tmp/expected.json"
    chmod -R a+rX "$tmp"
    mounts+=(-v "$tmp:/policies:ro")
    args+=(/policies/expected.json)
    ;;
*)
    echo "usage: $0 [patched|stock]" >&2
    exit 2
    ;;
esac

docker run --rm --network none --cpus=1 --memory=256m "${mounts[@]}" "$image" \
    test -v --timeout 60s "${args[@]}"
