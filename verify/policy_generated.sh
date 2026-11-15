#!/usr/bin/env bash
# Upstream's generated policy tests, for every app's policies in the tree: the fork's Team
# Analytics policy and the patched issue and comment policies among them.
#
#   verify/policy_generated.sh
#
# Upstream's runner (cvat/apps/iam/rules/tests/generate_tests.py) writes one test file per policy
# from the test configurations beside it; the files are ignored by git and left in place. OPA then
# runs them all. Needs python3, Docker and the OPA image (OPA_IMAGE, default the chart's image);
# no network.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="${OPA_IMAGE:-openpolicyagent/opa:1.12.2}"
cd "$root"

# the runner prints the events generator's scopes; only a failure is of interest here
python3 cvat/apps/iam/rules/tests/generate_tests.py >/dev/null

# The rules directories are named one by one: other directories under cvat/apps hold JSON that
# OPA would try to load as data. The tests of all apps together need more than 512 MiB.
rules=(cvat/apps/*/rules)
docker run --rm --network none --cpus=1 --memory=3g -v "$root:/mnt/src:ro" -w /mnt/src "$image" \
    test --timeout 600s "${rules[@]}"
