#!/usr/bin/env bash
# Brings up a throwaway CVAT stack serving the custom frontend and seeds it with tasks
# covering every job stage/state. Runs under its own compose project and its own container
# names so it cannot touch a deployment that owns the default `cvat` project.
# Tear down with: verify/run.sh down
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT=cvat-verify
COMPOSE=(docker compose -p "$PROJECT" -f "$ROOT/cvat/docker-compose.yml" -f "$ROOT/verify/docker-compose.verify.yml")

if [ "${1:-up}" = down ]; then
    "${COMPOSE[@]}" down -v
    exit 0
fi

"${COMPOSE[@]}" up -d
until [ "$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8181/api/server/about)" != "502" ]; do sleep 5; done

docker exec -e DJANGO_SUPERUSER_PASSWORD=verify-pass-123 verify_cvat_server \
    python manage.py createsuperuser --noinput --username admin --email admin@example.com || true

IMAGES="$(mktemp -d)"
python3 "$ROOT/verify/mkimg.py" "$IMAGES"
python3 "$ROOT/verify/seed.py" "$IMAGES"
rm -rf "$IMAGES"

echo
echo "http://localhost:8181/tasks - admin / verify-pass-123"
