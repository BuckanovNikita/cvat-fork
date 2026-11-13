#!/usr/bin/env bash
# Team Analytics test stack: a disposable CVAT v2.82.0 with analytics in its own namespace
# of the local docker-desktop cluster, reached at http://localhost:$TA_HOST_PORT.
# See README.md beside this file.
#
#   run.sh up             namespace, chart, proxy, port-forward, seed, client-event check
#   run.sh down           remove everything up created (succeeds when nothing exists)
#   run.sh cycle          up, then down
#   run.sh seed           (re)load the synthetic accounts into a running stack
#   run.sh check-event    send a client event through the API and find it in ClickHouse
#   run.sh forward        (re)start the port-forward of a running stack
#   run.sh status         what exists now
#   run.sh fetch-chart    only download the chart and build its pinned dependencies
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=stack.env
. "$HERE/stack.env"

MANAGED_BY=cvat-fork-team-analytics-stack
UPSTREAM_DIR="$TA_CACHE_DIR/upstream-$TA_UPSTREAM_COMMIT"
LOCK_SUM="$(sha256sum "$HERE/Chart.lock" | cut -c1-12)"
BUILD_DIR="$TA_CACHE_DIR/build-$TA_UPSTREAM_COMMIT-$LOCK_SUM"
CHART_DIR="$BUILD_DIR/helm-chart"
STATE_DIR="$TA_CACHE_DIR/state/$TA_NAMESPACE"
PF_STATE="$STATE_DIR/port-forward"
BASE_URL="http://localhost:$TA_HOST_PORT"

K=(kubectl --context "$TA_KUBE_CONTEXT")
H=(helm --kube-context "$TA_KUBE_CONTEXT")

log() { printf '[ta-stack] %s\n' "$*" >&2; }
die() { log "error: $*"; exit 1; }

case "$TA_NAMESPACE" in
    *[!a-z0-9-]* | -* | *- | "") die "TA_NAMESPACE '$TA_NAMESPACE' is not a DNS label" ;;
esac

# ---------------------------------------------------------------- chart

# Downloads helm-chart/ and the components/analytics/ it links to from the pinned upstream
# commit into the cache (once).
fetch_upstream() {
    [ -f "$UPSTREAM_DIR/helm-chart/Chart.yaml" ] && return 0
    mkdir -p "$TA_CACHE_DIR"
    local tmp top="cvat-$TA_UPSTREAM_COMMIT"
    tmp="$(mktemp -d "$TA_CACHE_DIR/fetch.XXXXXX")"
    log "downloading upstream $TA_UPSTREAM_COMMIT (once)"
    nice -n19 curl -fsSL "$TA_UPSTREAM_ARCHIVE_URL" -o "$tmp/src.tar.gz"
    nice -n19 tar -xzf "$tmp/src.tar.gz" -C "$tmp" --wildcards "$top/helm-chart/*" "$top/components/analytics/*"
    rm -rf "$UPSTREAM_DIR"
    mv "$tmp/$top" "$UPSTREAM_DIR"
    rm -rf "$tmp"
}

# Copies the pristine chart, adds the pinned Chart.lock and downloads exactly the locked
# dependency versions (helm dependency build refuses a lock that does not match Chart.yaml).
build_chart() {
    fetch_upstream
    [ -f "$BUILD_DIR/.complete" ] && return 0
    local tmp
    tmp="$(mktemp -d "$TA_CACHE_DIR/build.XXXXXX")"
    cp -a "$UPSTREAM_DIR/." "$tmp/"
    cp "$HERE/Chart.lock" "$tmp/helm-chart/Chart.lock"
    log "building chart dependencies from the pinned Chart.lock"
    # A private repository list, so the user's own helm repositories stay untouched.
    export HELM_REPOSITORY_CONFIG="$tmp/repositories.yaml" HELM_REPOSITORY_CACHE="$TA_CACHE_DIR/helm-repository-cache"
    local url i=0
    for url in $(awk '/repository:/{print $2}' "$HERE/Chart.lock" | sort -u); do
        i=$((i + 1))
        helm repo add "ta-dep-$i" "$url" --force-update >&2
    done
    nice -n19 helm dependency build "$tmp/helm-chart" >&2
    rm -f "$tmp/repositories.yaml" "$tmp/repositories.lock"
    # Every locked dependency must be exactly the archive recorded in the dated evidence.
    (cd "$tmp/helm-chart" && sha256sum --quiet -c "$HERE/chart-deps.sha256") \
        || die "chart dependency archives differ from chart-deps.sha256"
    [ "$(find "$tmp/helm-chart/charts" -name '*.tgz' | wc -l)" = "$(wc -l <"$HERE/chart-deps.sha256")" ] \
        || die "unexpected chart dependency archives"
    rm -rf "$BUILD_DIR"
    mv "$tmp" "$BUILD_DIR"
    touch "$BUILD_DIR/.complete"
}

helm_args() {
    local ui_repo="${TA_UI_IMAGE%:*}" ui_tag="${TA_UI_IMAGE##*:}"
    printf '%s\n' "$TA_RELEASE" "$CHART_DIR" --namespace "$TA_NAMESPACE" \
        -f "$HERE/values.yaml" \
        --set "cvat.frontend.image=$ui_repo" --set "cvat.frontend.tag=$ui_tag" \
        --set "grafana.grafana\.ini.server.root_url=$BASE_URL/analytics"
}

render() {
    local args
    mapfile -t args < <(helm_args)
    nice -n19 "${H[@]}" template "${args[@]}" 2>/dev/null
}

# Refuses a render that would create cluster-wide objects, pull from outside the approved
# list, or force pulls.
guard_render() {
    local rendered="$1" kinds cluster_kinds image bad=0
    cluster_kinds="$("${K[@]}" api-resources --namespaced=false --no-headers -o wide | awk '{print $(NF-1)}' | sort -u)"
    kinds="$(grep -h '^kind:' "$rendered" | awk '{print $2}' | sort -u)"
    for k in $kinds; do
        if grep -qx "$k" <<<"$cluster_kinds"; then log "cluster-wide kind in render: $k"; bad=1; fi
    done
    if grep -q 'imagePullPolicy: *"\?Always' "$rendered"; then log "render forces image pulls"; bad=1; fi
    for image in $(render_images "$rendered"); do
        image_local "$image" && continue
        approved "$image" || { log "image neither local nor approved: $image"; bad=1; }
    done
    [ "$bad" = 0 ] || die "render refused"
}

render_images() { grep -h '^ *image: ' "$1" | sed -E 's/^ *image: *"?([^"]+)"?.*/\1/' | sort -u; }
normalize_image() { local i="${1#docker.io/}"; echo "${i#library/}"; }
image_local() { docker image inspect "$1" >/dev/null 2>&1 || docker image inspect "$(normalize_image "$1")" >/dev/null 2>&1; }
approved() {
    local n
    n="$(normalize_image "$1")"
    for a in $TA_APPROVED_PULLS; do [ "$a" = "$n" ] && return 0; done
    return 1
}

# Pulls missing approved images one at a time, at low priority.
pull_images() {
    local image
    for image in $(render_images "$1"); do
        image_local "$image" && continue
        log "pulling $(normalize_image "$image")"
        nice -n19 docker pull -q "$(normalize_image "$image")" >&2
    done
    image_local "$TA_PROXY_IMAGE" || die "proxy image $TA_PROXY_IMAGE is not local (it is never pulled)"
}

# ---------------------------------------------------------------- namespace

ns_phase() { "${K[@]}" get ns "$TA_NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null || true; }
ns_owned() {
    [ "$("${K[@]}" get ns "$TA_NAMESPACE" -o jsonpath="{.metadata.labels.app\.kubernetes\.io/managed-by}" 2>/dev/null)" = "$MANAGED_BY" ]
}
ns_age_hours() {
    local created
    created="$("${K[@]}" get ns "$TA_NAMESPACE" -o jsonpath='{.metadata.creationTimestamp}')"
    echo $(( ($(date +%s) - $(date -d "$created" +%s)) / 3600 ))
}

wait_ns_gone() {
    local i
    for i in $(seq 1 120); do
        [ -z "$(ns_phase)" ] && return 0
        sleep 5
    done
    die "namespace $TA_NAMESPACE still exists after 10 minutes"
}

ensure_namespace() {
    local phase
    phase="$(ns_phase)"
    if [ -n "$phase" ]; then
        ns_owned || die "namespace $TA_NAMESPACE exists but was not created by this tool; refusing to use it"
        if [ "$phase" = Terminating ]; then
            log "namespace $TA_NAMESPACE is terminating; waiting"
            wait_ns_gone
        elif [ "$(ns_age_hours)" -ge "$TA_MAX_REUSE_HOURS" ]; then
            log "namespace $TA_NAMESPACE is older than $TA_MAX_REUSE_HOURS h; recreating"
            teardown
        fi
    fi
    if [ -z "$(ns_phase)" ]; then
        log "creating namespace $TA_NAMESPACE"
        stop_port_forward
    fi
    sed "s/__NAMESPACE__/$TA_NAMESPACE/g" "$HERE/namespace.yaml" | "${K[@]}" apply -f - >&2
}

# ---------------------------------------------------------------- install

install_chart() {
    local args
    mapfile -t args < <(helm_args)
    log "installing chart release $TA_RELEASE"
    nice -n19 "${H[@]}" upgrade --install "${args[@]}" --timeout 20m >&2
}

# Waits for what the checks need; Grafana is not among them (it downloads a plugin at start).
wait_ready() {
    local w
    log "waiting for the initializer job and core workloads"
    "${K[@]}" -n "$TA_NAMESPACE" wait --for=condition=complete --timeout=20m job -l "app.kubernetes.io/instance=$TA_RELEASE,tier=backend,component=initializer" >&2 \
        || { report_failures; die "initializer job did not complete"; }
    for w in deploy/"$TA_RELEASE"-backend-server deploy/"$TA_RELEASE"-backend-worker-utils \
             deploy/"$TA_RELEASE"-backend-worker-webhooks deploy/"$TA_RELEASE"-frontend deploy/"$TA_RELEASE"-opa \
             statefulset/"$TA_RELEASE"-kvrocks statefulset/"$TA_RELEASE"-clickhouse-shard0 \
             statefulset/"$TA_RELEASE"-vector deploy/ta-proxy; do
        "${K[@]}" -n "$TA_NAMESPACE" rollout status "$w" --timeout=15m >&2 || { report_failures; die "$w not ready"; }
    done
}

# Quota refusals do not reach helm; they show up as FailedCreate events.
report_failures() {
    "${K[@]}" -n "$TA_NAMESPACE" get events --field-selector reason=FailedCreate -o custom-columns=OBJ:.involvedObject.name,MSG:.message --no-headers >&2 || true
    "${K[@]}" -n "$TA_NAMESPACE" describe quota >&2 || true
    "${K[@]}" -n "$TA_NAMESPACE" get pods >&2 || true
}

apply_proxy() {
    local rev
    rev="$(sha256sum "$HERE/proxy.yaml" | cut -c1-12)"
    sed -e "s/__RELEASE__/$TA_RELEASE/g" -e "s|__PROXY_IMAGE__|$TA_PROXY_IMAGE|g" -e "s/__CONFIG_REVISION__/$rev/g" \
        "$HERE/proxy.yaml" | "${K[@]}" -n "$TA_NAMESPACE" apply -f - >&2
}

# ---------------------------------------------------------------- port-forward

# The state file holds the PID and the process start time; a process is ours only when both
# still match, so a reused PID is never signalled.
pf_alive() {
    [ -f "$PF_STATE" ] || return 1
    local pid start
    read -r pid start <"$PF_STATE"
    [ -r "/proc/$pid/stat" ] && [ "$(awk '{print $22}' "/proc/$pid/stat")" = "$start" ]
}

stop_port_forward() {
    if pf_alive; then
        local pid
        read -r pid _ <"$PF_STATE"
        log "stopping port-forward (pid $pid)"
        kill "$pid" 2>/dev/null || true
        for _ in 1 2 3 4 5 6 7 8 9 10; do [ -d "/proc/$pid" ] || break; sleep 0.5; done
    fi
    rm -f "$PF_STATE"
}

port_listening() { ss -Hltn "sport = :$TA_HOST_PORT" | grep -q .; }

start_port_forward() {
    stop_port_forward
    port_listening && die "host port $TA_HOST_PORT is in use by another process; not touching it"
    mkdir -p "$STATE_DIR"
    setsid "${K[@]}" -n "$TA_NAMESPACE" port-forward --address 127.0.0.1 svc/ta-proxy "$TA_HOST_PORT:8080" \
        >"$STATE_DIR/port-forward.log" 2>&1 </dev/null &
    local pid=$!
    echo "$pid $(awk '{print $22}' "/proc/$pid/stat")" >"$PF_STATE"
    for _ in $(seq 1 40); do
        if curl -fs -o /dev/null "$BASE_URL/api/server/about"; then
            log "stack reachable at $BASE_URL"
            return 0
        fi
        pf_alive || { cat "$STATE_DIR/port-forward.log" >&2; die "port-forward exited"; }
        sleep 0.5
    done
    die "no answer from $BASE_URL/api/server/about"
}

# ---------------------------------------------------------------- data

backend_pod() {
    "${K[@]}" -n "$TA_NAMESPACE" get pods -l "app.kubernetes.io/instance=$TA_RELEASE,tier=backend,component=server" \
        --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}'
}

seed() {
    log "loading synthetic accounts"
    "${K[@]}" -n "$TA_NAMESPACE" exec -i "$(backend_pod)" -c cvat-backend -- \
        env TA_SEED_PASSWORD="$TA_SEED_PASSWORD" TA_ACCOUNTS="$(cat "$HERE/accounts.json")" \
        python manage.py shell <"$HERE/seed_users.py" >&2
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" python3 -I "$HERE/stack_api.py" seed
}

clickhouse_query() {
    "${K[@]}" -n "$TA_NAMESPACE" exec -i "$TA_RELEASE-clickhouse-shard0-0" -c clickhouse -- \
        sh -c 'clickhouse-client --user "$CLICKHOUSE_USER" --password "$CLICKHOUSE_PASSWORD" --database "$CLICKHOUSE_DB" --format TSV --query "$0"' "$1"
}

check_event() {
    local marker="ta-stack-check-$(date +%s)-$$" rows
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" python3 -I "$HERE/stack_api.py" send-event "$marker"
    for _ in $(seq 1 60); do
        rows="$(clickhouse_query "SELECT user_name, scope, obj_name, JSONExtractString(payload, 'shape_type') FROM events WHERE obj_name = '$marker'")"
        if [ -n "$rows" ]; then
            log "event found in ClickHouse (user, scope, obj_name, payload.shape_type): $rows"
            [ "$(cut -f1 <<<"$rows")" = ta-worker ] || die "event stored for another user"
            [ "$(cut -f4 <<<"$rows")" = rectangle ] || die "payload field shape_type was dropped on the way"
            return 0
        fi
        sleep 2
    done
    die "event $marker did not reach ClickHouse within 2 minutes"
}

# ---------------------------------------------------------------- teardown

teardown() {
    stop_port_forward
    local phase
    phase="$(ns_phase)"
    if [ -n "$phase" ]; then
        ns_owned || die "namespace $TA_NAMESPACE was not created by this tool; refusing to delete it"
        log "deleting namespace $TA_NAMESPACE (with every volume claim in it)"
        "${K[@]}" delete ns "$TA_NAMESPACE" --ignore-not-found --wait=false >&2
        wait_ns_gone
    fi
    # Volumes of the default class are deleted with their claims; wait until none is left.
    for _ in $(seq 1 60); do
        "${K[@]}" get pv -o jsonpath='{range .items[*]}{.spec.claimRef.namespace}{"\n"}{end}' | grep -qx "$TA_NAMESPACE" || break
        sleep 5
    done
    if "${K[@]}" get pv -o jsonpath='{range .items[*]}{.spec.claimRef.namespace}{"\n"}{end}' | grep -qx "$TA_NAMESPACE"; then
        die "persistent volumes bound to $TA_NAMESPACE remain"
    fi
    rm -rf "$STATE_DIR"
    log "nothing of $TA_NAMESPACE remains"
}

status() {
    echo "namespace: $TA_NAMESPACE ($(ns_phase || true))"
    echo "address:   $BASE_URL"
    if pf_alive; then echo "port-forward: running (pid $(cut -d' ' -f1 "$PF_STATE"))"; else echo "port-forward: not running"; fi
    [ -n "$(ns_phase)" ] && "${K[@]}" -n "$TA_NAMESPACE" get pods,pvc
    return 0
}

up() {
    build_chart
    local rendered
    rendered="$(mktemp)"
    trap 'rm -f "$rendered"' RETURN
    render >"$rendered"
    guard_render "$rendered"
    pull_images "$rendered"
    ensure_namespace
    install_chart
    apply_proxy
    wait_ready
    start_port_forward
    seed
    check_event
    log "up: $BASE_URL (accounts: see README.md, password \$TA_SEED_PASSWORD)"
}

case "${1:-}" in
    up) up ;;
    down) teardown ;;
    cycle) up; teardown ;;
    seed) seed ;;
    check-event) check_event ;;
    forward) start_port_forward ;;
    status) status ;;
    fetch-chart) build_chart; echo "$CHART_DIR" ;;
    *) sed -n '5,13p' "$0" >&2; exit 2 ;;
esac
