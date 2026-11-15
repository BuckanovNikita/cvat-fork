#!/usr/bin/env bash
# ESLint or stylelint, with upstream's configuration, on the fork's UI files only.
#
#   tools/gate/ui-lint.sh eslint      the fork's .ts and .tsx files of the UI packages
#   tools/gate/ui-lint.sh stylelint   the fork's .scss files of the UI packages
#
# The fork's files are the tracked files of the five UI packages whose content in the
# working tree differs from the upstream release tag the fork is based on (UPSTREAM_TAG),
# or that the tag does not have. Untouched upstream files are never passed to the
# tool, and the tool runs without --fix, so nothing is rewritten. A new file counts
# once it is tracked (git add). The tools come from the installed node_modules.
set -euo pipefail

tool="${1:-}"
tag="${UPSTREAM_TAG:-v2.82.0}"
packages=(cvat-ui cvat-core cvat-canvas cvat-canvas3d cvat-data)
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"

case "$tool" in
eslint)
    globs=("${packages[@]/%//*.ts}" "${packages[@]/%//*.tsx}")
    cmd=(node node_modules/eslint/bin/eslint.js --max-warnings 0 --no-warn-ignored)
    ;;
stylelint)
    globs=("${packages[@]/%//*.scss}")
    cmd=(node node_modules/stylelint/bin/stylelint.mjs --max-warnings 0)
    ;;
*)
    echo "usage: $0 eslint|stylelint" >&2
    exit 2
    ;;
esac

if ! git rev-parse -q --verify "$tag^{tree}" >/dev/null; then
    echo "$0: upstream tag $tag not found; fetch it or set UPSTREAM_TAG" >&2
    exit 2
fi
if [ ! -e "${cmd[1]}" ]; then
    echo "$0: ${cmd[1]} not found; install node_modules (docs/upstream-upgrade.md, section 4)" >&2
    exit 2
fi

# Each git call's output goes to a variable first, so that a failing call stops
# the script (set -e) instead of leaving an empty list.
tracked_list="$(git -c core.quotePath=off ls-files -- "${globs[@]}")"
present=()
while IFS= read -r f; do
    [ -n "$f" ] && [ -f "$f" ] && present+=("$f")
done <<<"$tracked_list"

files=()
if [ "${#present[@]}" -gt 0 ]; then
    tag_list="$(git -c core.quotePath=off ls-tree -r "$tag")"
    hashes="$(printf '%s\n' "${present[@]}" | git hash-object --stdin-paths)"
    # First input: the upstream tag's "<mode> <type> <blob>\t<path>". Second: the
    # working tree's "<blob>\t<path>" of each candidate.
    # Print the candidates whose blob differs or that the tag lacks.
    selected="$(
        awk -F '\t' '
            NR == FNR { split($1, f, " "); tag[$2] = f[3]; next }
            { if (!($2 in tag) || tag[$2] != $1) print $2 }' \
            <(printf '%s\n' "$tag_list") \
            <(paste <(printf '%s\n' "$hashes") <(printf '%s\n' "${present[@]}"))
    )"
    while IFS= read -r f; do
        [ -n "$f" ] && files+=("$f")
    done <<<"$selected"
fi

if [ "${#files[@]}" -eq 0 ]; then
    echo "$tool: no fork files"
    exit 0
fi
echo "$tool: ${#files[@]} fork files"
exec "${cmd[@]}" "${files[@]}"
