#!/usr/bin/env bash
# Checks that an OPA bundle built or served by the CVAT server carries the import's issue and
# comment policies, each compared byte for byte by itself.
#
#   verify/policy_bundle.sh from-image IMAGE   writes the bundle that the server's own builder
#                                              (get_opa_bundle) makes in IMAGE to stdout: a
#                                              one-off container, no mounts, no network
#   verify/policy_bundle.sh check [REF]        reads a bundle (tar.gz) on stdin and compares
#                                              rules/issues.rego and rules/comments.rego with
#                                              the import's files in the working tree, or
#                                              with the files of an upstream mirror tag REF
#                                              (cvat-v2.82.0-widened for the stock policies)
#
# A served bundle is checked the same way: curl -s <api>/auth/rules | verify/policy_bundle.sh check
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RULES=cvat/apps/engine/rules  # upstream path; the import has it under cvat/
POLICIES=(issues.rego comments.rego)

case "${1:-}" in
from-image)
    image="${2:?usage: $0 from-image IMAGE}"
    docker run --rm --network none --cpus=1 -w /opt/cvat \
        --entrypoint /opt/venv/bin/python "$image" -c '
import os, sys, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cvat.settings.production")
django.setup()
from cvat.apps.iam.utils import get_opa_bundle
sys.stdout.buffer.write(get_opa_bundle()[0])'
    ;;
check)
    ref="${2:-}"
    work=$(mktemp -d)
    trap 'rm -rf "$work"' EXIT
    cat > "$work/bundle.tar.gz"
    mkdir "$work/bundle" "$work/expected"
    tar xzf "$work/bundle.tar.gz" -C "$work/bundle"
    status=0
    for name in "${POLICIES[@]}"; do
        if [ -n "$ref" ]; then
            git -C "$ROOT" show "$ref:$RULES/$name" > "$work/expected/$name"
        else
            cp "$ROOT/cvat/$RULES/$name" "$work/expected/$name"
        fi
        if [ ! -f "$work/bundle/rules/$name" ]; then
            echo "missing  rules/$name" >&2
            status=1
        elif cmp -s "$work/expected/$name" "$work/bundle/rules/$name"; then
            echo "equal    rules/$name = ${ref:-import}:$RULES/$name"
        else
            echo "DIFFERS  rules/$name != ${ref:-import}:$RULES/$name" >&2
            status=1
        fi
    done
    exit "$status"
    ;;
*)
    echo "usage: $0 from-image IMAGE | check [REF]" >&2
    exit 2
    ;;
esac
