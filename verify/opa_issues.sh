#!/usr/bin/env bash
# Proves the patched issue/comment OPA rules on a throwaway CVAT stack.
#
#   verify/opa_issues.sh all     stock stack -> baseline matrix -> patched stack -> patched matrix
#   verify/opa_issues.sh down    tear it down, volumes and all
#
# Its own compose project, container names and ports (8281/8291), so it cannot
# touch a deployment that owns the default `cvat` project.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT=cvat-opa
export OPA_RULES="$ROOT/opa/rules"
export OPA_ISSUES_BASE=${OPA_ISSUES_BASE:-http://localhost:8281/api}

STOCK=(docker compose -p "$PROJECT"
    -f "$ROOT/cvat/docker-compose.yml"
    -f "$ROOT/verify/docker-compose.opa-issues.yml")
PATCHED=("${STOCK[@]}" -f "$ROOT/verify/docker-compose.opa-patch.yml")

wait_for_server() {
    # Wait for JSON, not for "not a 502": the UI's nginx answers /api/ with an
    # HTML 200 whenever the traefik rule is broken, and a status-only probe
    # reads that as a healthy server and runs the seed against a dead API.
    until curl -s -o /dev/null -w '%{content_type}' "${OPA_ISSUES_BASE}/server/about" | grep -q json; do
        sleep 5
    done
    # OPA polls the bundle on a schedule; a fresh bundle is not live the instant
    # the server answers.
    sleep 20
}

case "${1:-all}" in
down)
    "${STOCK[@]}" down -v
    exit 0
    ;;
all) ;;
*)
    echo "usage: $0 [all|down]" >&2
    exit 2
    ;;
esac

"${STOCK[@]}" up -d
wait_for_server

docker exec -e DJANGO_SUPERUSER_PASSWORD=verify-pass-123 opa_cvat_server \
    python manage.py createsuperuser --noinput --username admin --email admin@example.com || true

python3 "$ROOT/verify/opa_issues_seed.py"
python3 "$ROOT/verify/opa_issues_check.py" stock

"${PATCHED[@]}" up -d --force-recreate cvat_server  # get_opa_bundle is lru_cached
wait_for_server
# Unpacked rather than piped into grep: `grep -q` closes the pipe on its first
# match, tar dies of SIGPIPE, and pipefail turns the successful match into a
# failed check.
bundle=$(mktemp -d)
curl -s "${OPA_ISSUES_BASE}/auth/rules" -o "$bundle/rules.tar.gz"
tar xzf "$bundle/rules.tar.gz" -C "$bundle"
if grep -l 'Local patch' "$bundle"/rules/issues.rego "$bundle"/rules/comments.rego; then
    echo "bundle served by cvat_server carries the patched rules"
else
    echo "bundle does NOT carry the patched rules - the mounts did not reach cvat_server" >&2
    exit 1
fi
rm -rf "$bundle"

python3 "$ROOT/verify/opa_issues_check.py" patched

echo
echo "http://localhost:8281  admin / verify-pass-123   worker1,worker2 / worker-pass-123"
echo "tear down with: verify/opa_issues.sh down"
