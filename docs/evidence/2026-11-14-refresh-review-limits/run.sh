#!/usr/bin/env bash
# Runs probe_limits.py against one throwaway ClickHouse; image from $1 (default the chart's).
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
image="${1:-cvat/clickhouse:23.12.2-debian-11-r0}"
id="ta-fixrefresh-$$-$RANDOM"
cleanup() {
    docker rm -f -v "$id-ch" "$id-py" >/dev/null 2>&1 || true
    docker network rm "$id" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker network create "$id" >/dev/null
docker run -d --name "$id-ch" --network "$id" --network-alias clickhouse --cpus 2 --memory 2g \
    -e CLICKHOUSE_ADMIN_USER=user -e CLICKHOUSE_ADMIN_PASSWORD=user -e CLICKHOUSE_USER=user \
    -e CLICKHOUSE_PASSWORD=user -e CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1 "$image" >/dev/null
echo "image: $image"
docker run --rm --name "$id-py" --network "$id" --cpus 1 -v "$here:/probe:ro" \
    --entrypoint /opt/venv/bin/python cvat/server:v2.82.0 -I -B /probe/probe_limits.py
