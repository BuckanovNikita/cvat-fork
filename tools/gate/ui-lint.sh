#!/usr/bin/env bash
# ESLint or stylelint, with upstream's configuration, on the fork's UI files only.
#
#   tools/gate/ui-lint.sh eslint      the fork's .ts and .tsx files under cvat/
#   tools/gate/ui-lint.sh stylelint   the fork's .scss files under cvat/
#
# The fork's files are the tracked files under cvat/ whose content in the working
# tree differs from the import tag (IMPORT_TAG, default the import now in the tree),
# or that the tag does not have. Untouched upstream files are never passed to the
# tool, and the tool runs without --fix, so nothing is rewritten. A new file counts
# once it is tracked (git add). The tools come from the installed cvat/node_modules.
set -euo pipefail

tool="${1:-}"
tag="${IMPORT_TAG:-cvat-v2.82.0-widened}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$root"

case "$tool" in
eslint)
    globs=('cvat/*.ts' 'cvat/*.tsx')
    cmd=(node cvat/node_modules/eslint/bin/eslint.js --max-warnings 0 --no-warn-ignored)
    ;;
stylelint)
    globs=('cvat/*.scss')
    cmd=(node cvat/node_modules/stylelint/bin/stylelint.mjs --max-warnings 0)
    ;;
*)
    echo "usage: $0 eslint|stylelint" >&2
    exit 2
    ;;
esac

if ! git rev-parse -q --verify "$tag^{tree}" >/dev/null; then
    echo "$0: import tag $tag not found; fetch it or set IMPORT_TAG" >&2
    exit 2
fi
if [ ! -e "${cmd[1]}" ]; then
    echo "$0: ${cmd[1]} not found; install cvat/node_modules (docs/upstream-upgrade.md, section 4)" >&2
    exit 2
fi

mapfile -t tracked < <(git -c core.quotePath=off ls-files -- "${globs[@]}")
present=()
for f in "${tracked[@]}"; do
    [ -f "$f" ] && present+=("$f")
done

files=()
if [ "${#present[@]}" -gt 0 ]; then
    # First input: the import tag's "<mode> <type> <blob>\t<path>", paths relative
    # to cvat/. Second: the working tree's "<blob>\t<path>" of each candidate.
    # Print the candidates whose blob differs or that the tag lacks.
    mapfile -t files < <(
        awk -F '\t' '
            NR == FNR { split($1, f, " "); tag[$2] = f[3]; next }
            { rel = substr($2, length("cvat/") + 1); if (!(rel in tag) || tag[rel] != $1) print $2 }' \
            <(git -c core.quotePath=off ls-tree -r "$tag") \
            <(paste <(printf '%s\n' "${present[@]}" | git hash-object --stdin-paths) \
                    <(printf '%s\n' "${present[@]}"))
    )
fi

if [ "${#files[@]}" -eq 0 ]; then
    echo "$tool: no fork files"
    exit 0
fi
echo "$tool: ${#files[@]} fork files"
exec "${cmd[@]}" "${files[@]}"
