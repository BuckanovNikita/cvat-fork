#!/usr/bin/env bash
# Seam 1: Team Analytics' calculations in the backend app's core, against a real ClickHouse and Redis.
#
#   verify/team_analytics_backend.sh                            # every test
#   verify/team_analytics_backend.sh tests.test_working_time    # unittest names, relative to verify/team-analytics-backend
#
# Runs the tests with stdlib unittest inside a container of the stock CVAT server image (the backend's
# runtime) against a throwaway ClickHouse container and a throwaway Redis for the refresh lock. The code
# under test is the working tree's cvat/apps/team_analytics, mounted where the image keeps CVAT's apps;
# CVAT's own ClickHouse init script creates each test's events database. Container and network names
# are unique per run, no host port is published, and everything started here is removed on exit.
# Images: SERVER_IMAGE (default cvat/server:v2.82.0), CLICKHOUSE_IMAGE (default the Helm chart's
# cvat/clickhouse:23.12.2-debian-11-r0; clickhouse/clickhouse-server:23.11-alpine also works),
# REDIS_IMAGE (default the chart's redis:7.2.11). None is pulled here.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
server_image="${SERVER_IMAGE:-cvat/server:v2.82.0}"
clickhouse_image="${CLICKHOUSE_IMAGE:-cvat/clickhouse:23.12.2-debian-11-r0}"
redis_image="${REDIS_IMAGE:-redis:7.2.11}"
run_id="ta-backend-$(printf '%s' "$repo" | sha1sum | cut -c1-8)-$$-${RANDOM}"
network="$run_id"
clickhouse="$run_id-clickhouse"
redis="$run_id-redis"
tests="$run_id-tests"

cleanup() {
    # -v: with their anonymous volumes (the upstream ClickHouse image declares two)
    docker rm -f -v "$tests" "$clickhouse" "$redis" >/dev/null 2>&1 || true
    docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM

docker network create "$network" >/dev/null
# The Bitnami-based chart image reads CLICKHOUSE_ADMIN_*, the upstream image CLICKHOUSE_USER/PASSWORD.
docker run -d --pull never --name "$clickhouse" --network "$network" --network-alias clickhouse \
    --cpus 2 --memory 2g \
    -e CLICKHOUSE_ADMIN_USER=user -e CLICKHOUSE_ADMIN_PASSWORD=user \
    -e CLICKHOUSE_USER=user -e CLICKHOUSE_PASSWORD=user -e CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1 \
    "$clickhouse_image" >/dev/null

# no persistence and no published port: the refresh lock of the tests is its only user
docker run -d --pull never --name "$redis" --network "$network" --network-alias redis \
    --cpus 1 --memory 256m \
    "$redis_image" redis-server --save '' --appendonly no >/dev/null

docker run --rm --pull never --name "$tests" --network "$network" --cpus 2 \
    -v "$repo/verify/team-analytics-backend:/srv/team-analytics-backend:ro" \
    -v "$repo/cvat/apps/team_analytics:/opt/cvat/cvat/apps/team_analytics:ro" \
    -v "$repo/components/analytics/clickhouse:/srv/cvat-clickhouse:ro" \
    -w /srv/team-analytics-backend \
    -e CLICKHOUSE_HOST=clickhouse -e CLICKHOUSE_PORT=8123 \
    -e CLICKHOUSE_USER=user -e CLICKHOUSE_PASSWORD=user \
    -e REDIS_HOST=redis -e REDIS_PORT=6379 \
    -e TEAM_ANALYTICS_EVENTS_INIT=/srv/cvat-clickhouse/init.py \
    -e PYTHONDONTWRITEBYTECODE=1 \
    --entrypoint /opt/venv/bin/python \
    "$server_image" -B -m unittest "${@:-discover}" -v
