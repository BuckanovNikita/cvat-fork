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
#   verify/policy_bundle.sh check-stock REF    reads a bundle on stdin and compares all four
#                                              policy files the import carries (the two
#                                              policies and their two helpers) with REF's: the
#                                              bundle of a stock server image of REF's release
#
# Before comparing, every check refuses a bundle that is not a readable archive, that holds
# two entries of one name (extraction would keep only the last), or whose entry for a compared
# file is anything but a regular file (a link would be followed on extraction).
#
# A served bundle is checked the same way: curl -s <api>/auth/rules | verify/policy_bundle.sh check
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Upstream paths; the import has them under cvat/. The bundle holds each under rules/<name>.
POLICY_PATHS=(cvat/apps/engine/rules/issues.rego cvat/apps/engine/rules/comments.rego)
STOCK_PATHS=("${POLICY_PATHS[@]}" cvat/apps/iam/rules/utils.rego cvat/apps/organizations/rules/organizations.rego)

# Judges the archive's listing before anything is extracted. $1 is the archive, the rest
# are the bundle paths (rules/<name>) that must each be one regular file.
check_listing() {
    local archive="$1" listing dupes p type status=0
    shift
    listing="$(python3 -I -c '
import sys, tarfile
try:
    with tarfile.open(sys.argv[1], "r:gz") as t:
        for m in t.getmembers():
            name = m.name[2:] if m.name.startswith("./") else m.name
            kind = "file" if m.isreg() else "dir" if m.isdir() else "link" if m.issym() or m.islnk() else "other"
            print(kind, name)
except (tarfile.TarError, OSError, EOFError) as exc:
    sys.exit(f"not a readable bundle archive: {exc}")
' "$archive")" || return 1
    dupes="$(cut -d' ' -f2- <<<"$listing" | sort | uniq -d)"
    if [ -n "$dupes" ]; then
        while read -r p; do echo "TWICE    $p (two entries of one name)" >&2; done <<<"$dupes"
        status=1
    fi
    for p in "$@"; do
        type="$(awk -v p="$p" '{k=$1; $1=""; if (substr($0, 2) == p) print k}' <<<"$listing" | sort -u | paste -sd,)"
        if [ -n "$type" ] && [ "$type" != file ]; then
            echo "NOT FILE $p ($type)" >&2
            status=1
        fi
    done
    return "$status"
}

# Compares the bundle on stdin with the files at REF ($1, empty for the import in the working
# tree), for the upstream paths given after it.
compare_bundle() {
    local ref="$1" status=0 path name
    shift
    work=$(mktemp -d)  # global: the EXIT trap reads it
    trap 'rm -rf "$work"' EXIT
    cat > "$work/bundle.tar.gz"
    local names=()
    for path in "$@"; do names+=("rules/${path##*/}"); done
    check_listing "$work/bundle.tar.gz" "${names[@]}" || exit 1
    mkdir "$work/bundle" "$work/expected"
    tar xzf "$work/bundle.tar.gz" -C "$work/bundle"
    for path in "$@"; do
        name="${path##*/}"
        if [ -n "$ref" ]; then
            git -C "$ROOT" show "$ref:$path" > "$work/expected/$name"
        else
            cp "$ROOT/cvat/$path" "$work/expected/$name"
        fi
        if [ ! -f "$work/bundle/rules/$name" ]; then
            echo "missing  rules/$name" >&2
            status=1
        elif cmp -s "$work/expected/$name" "$work/bundle/rules/$name"; then
            echo "equal    rules/$name = ${ref:-import}:$path"
        else
            echo "DIFFERS  rules/$name != ${ref:-import}:$path" >&2
            status=1
        fi
    done
    exit "$status"
}

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
    compare_bundle "${2:-}" "${POLICY_PATHS[@]}"
    ;;
check-stock)
    compare_bundle "${2:?usage: $0 check-stock REF}" "${STOCK_PATHS[@]}"
    ;;
*)
    echo "usage: $0 from-image IMAGE | check [REF] | check-stock REF" >&2
    exit 2
    ;;
esac
