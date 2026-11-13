#!/usr/bin/env bash
# Seam 1: the Team Analytics service's read interface against a real ClickHouse.
#
#   verify/team_analytics_service.sh                 # every test
#   verify/team_analytics_service.sh tests.test_working_time   # unittest names, relative to the service dir
#
# Runs the tests with stdlib unittest inside a container of the stock CVAT server image (the
# service's own runtime) against a throwaway ClickHouse container. Container and network names
# are unique per run, no host port is published, and everything started here is removed on exit.
# Images: SERVER_IMAGE (default cvat/server:v2.82.0), CLICKHOUSE_IMAGE (default the Helm chart's
# cvat/clickhouse:23.12.2-debian-11-r0; clickhouse/clickhouse-server:23.11-alpine also works).
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
server_image="${SERVER_IMAGE:-cvat/server:v2.82.0}"
clickhouse_image="${CLICKHOUSE_IMAGE:-cvat/clickhouse:23.12.2-debian-11-r0}"
run_id="ta-seam1-$(printf '%s' "$repo" | sha1sum | cut -c1-8)-$$-${RANDOM}"
network="$run_id"
clickhouse="$run_id-clickhouse"
tests="$run_id-tests"

cleanup() {
    docker rm -f "$tests" "$clickhouse" >/dev/null 2>&1 || true
    docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM

docker network create "$network" >/dev/null
# The Bitnami-based chart image reads CLICKHOUSE_ADMIN_*, the upstream image CLICKHOUSE_USER/PASSWORD.
docker run -d --name "$clickhouse" --network "$network" --network-alias clickhouse \
    --cpus 2 --memory 2g \
    -e CLICKHOUSE_ADMIN_USER=user -e CLICKHOUSE_ADMIN_PASSWORD=user \
    -e CLICKHOUSE_USER=user -e CLICKHOUSE_PASSWORD=user -e CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1 \
    "$clickhouse_image" >/dev/null

docker run --rm --name "$tests" --network "$network" --cpus 2 \
    -v "$repo/team-analytics/service:/srv/team-analytics:ro" \
    -v "$repo/cvat/components/analytics/clickhouse:/srv/cvat-clickhouse:ro" \
    -w /srv/team-analytics \
    -e CLICKHOUSE_HOST=clickhouse -e CLICKHOUSE_PORT=8123 \
    -e CLICKHOUSE_USER=user -e CLICKHOUSE_PASSWORD=user \
    -e TEAM_ANALYTICS_EVENTS_INIT=/srv/cvat-clickhouse/init.py \
    -e PYTHONDONTWRITEBYTECODE=1 \
    --entrypoint /opt/venv/bin/python \
    "$server_image" -B -m unittest "${@:-discover}" -v
