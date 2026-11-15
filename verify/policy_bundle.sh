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
# Before comparing, every check refuses a bundle that is not a readable archive, that holds an
# entry other than a regular file or a directory anywhere (a link would be followed on
# extraction), a name that leaves the archive's root, or two file entries whose names are one
# name once normalised (extraction would keep only the last).
#
# A served bundle is checked the same way: curl -s <api>/auth/rules | verify/policy_bundle.sh check
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Upstream paths; the import has them under cvat/. The bundle holds each under rules/<name>.
POLICY_PATHS=(cvat/apps/engine/rules/issues.rego cvat/apps/engine/rules/comments.rego)
STOCK_PATHS=("${POLICY_PATHS[@]}" cvat/apps/iam/rules/utils.rego cvat/apps/organizations/rules/organizations.rego)

# Judges the archive's listing before anything is extracted ($1 is the archive). Each entry's
# name is normalised as extraction resolves it (a leading ./ or /, a doubled /, a . segment), so
# two spellings of one name are one name. Refused: an entry that is neither a regular file nor
# a directory, wherever it sits (a link to a directory would be followed on extraction), a name
# that leaves the archive's root, and two file entries of one name (extraction keeps the last).
check_listing() {
    python3 -I -c '
import posixpath, sys, tarfile
from collections import Counter
try:
    with tarfile.open(sys.argv[1], "r:gz") as t:
        members = t.getmembers()
except (tarfile.TarError, OSError, EOFError) as exc:
    sys.exit(f"not a readable bundle archive: {exc}")
problems, files = [], Counter()
for m in members:
    name = posixpath.normpath(m.name.lstrip("/") or ".")
    if not (m.isreg() or m.isdir()):
        kind = "link" if m.issym() or m.islnk() else "other"
        problems.append(f"NOT FILE {m.name} ({kind}: only regular files and directories are read)")
    if name == ".." or name.startswith("../"):
        problems.append(f"OUTSIDE  {m.name} (leaves the bundle)")
    if not m.isdir():
        files[name] += 1
for name, count in sorted(files.items()):
    if count > 1:
        problems.append(f"TWICE    {name} ({count} entries of one name)")
for problem in problems:
    print(problem, file=sys.stderr)
sys.exit(1 if problems else 0)
' "$1"
}

# Compares the bundle on stdin with the files at REF ($1, empty for the import in the working
# tree), for the upstream paths given after it.
compare_bundle() {
    local ref="$1" status=0 path name
    shift
    work=$(mktemp -d)  # global: the EXIT trap reads it
    trap 'rm -rf "$work"' EXIT
    cat > "$work/bundle.tar.gz"
    check_listing "$work/bundle.tar.gz" || exit 1
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
