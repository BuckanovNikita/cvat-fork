#!/usr/bin/env bash
# Thin wrapper: run a SQL file (multi-statement) in the benchmark container.
# usage: ch.sh file.sql [extra clickhouse-client args...]
set -euo pipefail
f="$1"; shift
docker exec -i ta-chbench-f0f6 clickhouse-client -n --max_threads=6 "$@" < "$f"
