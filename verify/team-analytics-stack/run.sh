#!/usr/bin/env bash
# Team Analytics test stack: a disposable CVAT v2.82.0 with analytics in its own namespace
# of the local docker-desktop cluster, reached at http://localhost:$TA_HOST_PORT.
# See README.md beside this file.
#
#   run.sh up             namespace, chart, service, proxy, port-forward, seed, checks
#   run.sh down           remove everything up created (succeeds when nothing exists)
#   run.sh cycle          up, then down (also when up fails)
#   run.sh seed           (re)load the synthetic accounts into a running stack
#   run.sh check-event    send a client event through the API and find it in ClickHouse
#   run.sh check-tracer   load working time as real accounts, wait for the scheduled refresh,
#                         check the service's figures and refusals, then the page in a browser
#   run.sh check-final    the final run: the real UI annotates in a browser and its records arrive,
#                         figures for that work and for loaded volume, every account and endpoint,
#                         the page, then the page and annotation with the service stopped
#   run.sh check-policies fetch the policy bundle the running server serves and check both
#                         patched policies in it, each by itself
#   run.sh forward        (re)start the port-forward of a running stack
#   run.sh status         what exists now
#   run.sh preflight      what up does before it touches the cluster: the server image check,
#                         the chart build and the render checks; creates and pulls nothing
#   run.sh build-chart    only build the import's chart with its pinned dependencies
#   run.sh render         print the chart render that up checks and installs (unchecked)
#   run.sh check-render F apply up's render checks to the render in file F
#   run.sh check-bundle   check a policy bundle (tar.gz) given on stdin as check-policies does,
#                         e.g. one from verify/policy_bundle.sh from-image IMAGE
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
SERVICE_K8S="$ROOT/team-analytics/k8s"
# The chart of the import, and the analytics component its analytics link points to.
IMPORT_DIR="$ROOT/cvat"
CHART_PATHS=(helm-chart components/analytics)
# shellcheck source=stack.env
. "$HERE/stack.env"

MANAGED_BY=cvat-fork-team-analytics-stack
STATE_DIR="$TA_CACHE_DIR/state/$TA_NAMESPACE"
PF_STATE="$STATE_DIR/port-forward"
BASE_URL="http://localhost:$TA_HOST_PORT"

K=(kubectl --context "$TA_KUBE_CONTEXT")
H=(helm_run --kube-context "$TA_KUBE_CONTEXT")

log() { printf '[ta-stack] %s\n' "$*" >&2; }
die() { log "error: $*"; exit 1; }

# Every helm call goes through helm_run. Whenever helm reads the chart it notes the chart's
# analytics symlink and prints the chart's full local path; that line is dropped so that no
# captured log carries the path, and every other message is kept. nice is here because it
# cannot run a shell function.
helm_run() { nice -n19 helm "$@" 2> >(grep -v 'found symbolic link in path' >&2); }

# Every path the launcher prints goes through show_path, so that no captured output names
# the machine's own directories: a path inside the repository is shown relative to the
# repository root, a path under the home directory with ~ for it, any other path as it is.
# Paths are compared resolved, so another name of the same directory is recognised too.
show_path() {
    local p root home
    p="$(realpath -m -- "$1")"
    root="$(realpath -m -- "$HERE/../..")"
    home="$(realpath -m -- "${HOME:-/}")"
    if [ "$p" = "$root" ]; then printf '.\n'
    elif [ "${p#"$root"/}" != "$p" ]; then printf '%s\n' "${p#"$root"/}"
    elif [ "$home" != / ] && [ "$p" = "$home" ]; then printf '~\n'
    elif [ "$home" != / ] && [ "${p#"$home"/}" != "$p" ]; then printf '~/%s\n' "${p#"$home"/}"
    else printf '%s\n' "$1"
    fi
}

case "$TA_NAMESPACE" in
    *[!a-z0-9-]* | -* | *- | "") die "TA_NAMESPACE '$TA_NAMESPACE' is not a DNS label" ;;
esac

# ---------------------------------------------------------------- chart

# A hash of the import's chart files as they are in the working tree, and of the pinned lock.
# The build directory is named by it, so a change to either builds the chart afresh.
chart_source_sum() {
    {
        tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner -cf - -C "$IMPORT_DIR" "${CHART_PATHS[@]}"
        cat "$HERE/Chart.lock"
    } | sha256sum | cut -c1-16
}

# Sets CHART_DIR to the build of the import's chart, building it first when needed: a copy of
# the chart and of the analytics component it links to (helm dependency build writes into the
# chart directory; the import stays untouched), the pinned Chart.lock, and exactly the locked
# dependency versions (helm dependency build refuses a lock that does not match Chart.yaml),
# checked against chart-deps.sha256.
build_chart() {
    local sum build tmp p
    [ -f "$IMPORT_DIR/helm-chart/Chart.yaml" ] || die "no chart in the import at $(show_path "$IMPORT_DIR/helm-chart")"
    sum="$(chart_source_sum)"
    build="$TA_CACHE_DIR/chart-$sum"
    CHART_DIR="$build/helm-chart"
    [ -f "$build/.complete" ] && return 0
    mkdir -p "$TA_CACHE_DIR"
    tmp="$(mktemp -d "$TA_CACHE_DIR/build.XXXXXX")"
    for p in "${CHART_PATHS[@]}"; do
        mkdir -p "$tmp/$(dirname "$p")"
        cp -a "$IMPORT_DIR/$p" "$tmp/$p"
    done
    [ -z "$(find "$tmp/helm-chart" -maxdepth 1 \( -name Chart.lock -o -name charts \))" ] \
        || die "the import's chart directory holds a Chart.lock or charts/; the lock is the stack's own"
    cp "$HERE/Chart.lock" "$tmp/helm-chart/Chart.lock"
    log "building chart dependencies from the pinned Chart.lock"
    # A private repository list, so the user's own helm repositories stay untouched.
    (
        export HELM_REPOSITORY_CONFIG="$tmp/repositories.yaml" HELM_REPOSITORY_CACHE="$TA_CACHE_DIR/helm-repository-cache"
        i=0
        for url in $(awk '/repository:/{print $2}' "$HERE/Chart.lock" | sort -u); do
            i=$((i + 1))
            helm_run repo add "ta-dep-$i" "$url" --force-update >&2
        done
        helm_run dependency build "$tmp/helm-chart" >&2
    ) || die "chart dependency build failed"
    rm -f "$tmp/repositories.yaml" "$tmp/repositories.lock"
    # Every locked dependency must be exactly the archive recorded in the dated evidence.
    (cd "$tmp/helm-chart" && sha256sum --quiet -c "$HERE/chart-deps.sha256") \
        || die "chart dependency archives differ from chart-deps.sha256"
    [ "$(find "$tmp/helm-chart/charts" -name '*.tgz' | wc -l)" = "$(wc -l <"$HERE/chart-deps.sha256")" ] \
        || die "unexpected chart dependency archives"
    [ "$(chart_source_sum)" = "$sum" ] || die "the import's chart changed during the build"
    rm -rf "$build"
    mv "$tmp" "$build"
    touch "$build/.complete"
}

helm_args() {
    local ui_repo="${TA_UI_IMAGE%:*}" ui_tag="${TA_UI_IMAGE##*:}"
    printf '%s\n' "$TA_RELEASE" "$CHART_DIR" --namespace "$TA_NAMESPACE" \
        -f "$HERE/values.yaml" \
        --set "cvat.backend.image=${TA_SERVER_IMAGE%:*}" --set "cvat.backend.tag=${TA_SERVER_IMAGE##*:}" \
        --set "cvat.frontend.image=$ui_repo" --set "cvat.frontend.tag=$ui_tag" \
        --set "grafana.grafana\.ini.server.root_url=$BASE_URL/analytics"
}

render() {
    local args
    mapfile -t args < <(helm_args)
    "${H[@]}" template "${args[@]}"
}

# Refuses a render that would create cluster-wide objects, pull from outside the approved
# list, or force pulls.
guard_render() {
    local rendered="$1" kinds cluster_kinds image bad=0
    cluster_kinds="$("${K[@]}" api-resources --namespaced=false --no-headers | awk '{print $NF}' | sort -u)"
    grep -qx CustomResourceDefinition <<<"$cluster_kinds" || die "could not list cluster-scoped kinds"
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

# The backend (server, workers, initializer and their init containers) runs the fork server
# image and no other server image: a render that falls back to the stock image is refused,
# although that image may be local and is approved.
check_backend_image() {
    local rendered="$1" image found=0 bad=0
    for image in $(render_images "$rendered"); do
        image="$(normalize_image "$image")"
        if [ "$image" = "$TA_SERVER_IMAGE" ]; then
            found=1
        elif [ "${image%%[:@]*}" = cvat/server ]; then
            log "server image other than the fork server image in render: $image"; bad=1
        fi
    done
    [ "$found" = 1 ] || { log "the fork server image $TA_SERVER_IMAGE is not in the render"; bad=1; }
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

# The fork server image (ADR 0004, build-server.sh) is in no registry: without it locally the
# release could not start, so up stops here, before anything is built, pulled or created.
check_server_image() {
    image_local "$TA_SERVER_IMAGE" \
        || die "fork server image $TA_SERVER_IMAGE is not local (IMAGE=$TA_SERVER_IMAGE ./build-server.sh); it is never pulled"
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
    image_local "$TA_SERVICE_IMAGE" || die "service image $TA_SERVICE_IMAGE is not local (build-team-analytics-service.sh)"
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
    "${H[@]}" upgrade --install "${args[@]}" --timeout 20m >&2
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
             statefulset/"$TA_RELEASE"-vector deploy/team-analytics deploy/ta-proxy; do
        "${K[@]}" -n "$TA_NAMESPACE" rollout status "$w" --timeout=15m >&2 || { report_failures; die "$w not ready"; }
    done
}

# Quota refusals do not reach helm; they show up as FailedCreate events.
report_failures() {
    "${K[@]}" -n "$TA_NAMESPACE" get events --field-selector reason=FailedCreate -o custom-columns=OBJ:.involvedObject.name,MSG:.message --no-headers >&2 || true
    "${K[@]}" -n "$TA_NAMESPACE" describe quota >&2 || true
    "${K[@]}" -n "$TA_NAMESPACE" get pods >&2 || true
}

# The service's own manifests (team-analytics/k8s) with the stack's image, release and refresh
# interval. Its Ingress is not applied: the proxy is the route here. Applied before the proxy,
# whose nginx resolves the service name at start.
apply_service() {
    local rendered
    rendered="$(for f in config.yaml deployment.yaml service.yaml; do cat "$SERVICE_K8S/$f"; echo ---; done |
        sed -e "s|image: cvat/team-analytics:v2.82.0|image: $TA_SERVICE_IMAGE|" \
            -e "s|imagePullPolicy: IfNotPresent|imagePullPolicy: Never|" \
            -e "s|http://cvat-backend-service:8080|http://$TA_RELEASE-backend-service:8080|" \
            -e "s|TEAM_ANALYTICS_REFRESH_INTERVAL_S: \"600\"|TEAM_ANALYTICS_REFRESH_INTERVAL_S: \"$TA_REFRESH_INTERVAL_S\"|" \
            -e "s|TEAM_ANALYTICS_TECHNICAL_ACCOUNTS: \"\"|TEAM_ANALYTICS_TECHNICAL_ACCOUNTS: \"$TA_TECHNICAL_ACCOUNTS\"|")"
    grep -q "image: $TA_SERVICE_IMAGE\$" <<<"$rendered" && grep -q "INTERVAL_S: \"$TA_REFRESH_INTERVAL_S\"" <<<"$rendered" \
        && grep -q "TECHNICAL_ACCOUNTS: \"$TA_TECHNICAL_ACCOUNTS\"" <<<"$rendered" \
        || die "could not set the service image or refresh interval in team-analytics/k8s"
    log "applying the Team Analytics service ($TA_SERVICE_IMAGE, refresh every $TA_REFRESH_INTERVAL_S s)"
    "${K[@]}" -n "$TA_NAMESPACE" apply -f - <<<"$rendered" >&2
    # the service reads its ConfigMap at start: a changed configuration restarts it on a rerun
    "${K[@]}" -n "$TA_NAMESPACE" patch deploy team-analytics --type merge -p \
        "{\"spec\":{\"template\":{\"metadata\":{\"annotations\":{\"ta-stack/config-revision\":\"$(sha256sum <<<"$rendered" | cut -c1-12)\"}}}}}" >&2
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

# Working time loaded through the CVAT API as real accounts after the service started, so only a
# scheduled refresh can bring it to the figures; nothing triggers one.
check_tracer() {
    local pod started seeded_at refreshes=0
    pod="$("${K[@]}" -n "$TA_NAMESPACE" get pods -l app.kubernetes.io/name=team-analytics \
        --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')"
    container_started() {
        "${K[@]}" -n "$TA_NAMESPACE" get pod "$pod" -o jsonpath='{.status.containerStatuses[0].state.running.startedAt}'
    }
    # log lines start with the container's UTC time, so they compare as text
    refreshes_since() {
        "${K[@]}" -n "$TA_NAMESPACE" logs "$pod" | { grep ' refreshed ' || true; } | awk -v t="$1" '$1 " " substr($2, 1, 8) >= t' | wc -l
    }
    started="$(container_started)"
    seeded_at="$(date -u '+%Y-%m-%d %H:%M:%S')"
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" python3 -I "$HERE/stack_api.py" seed-work
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" \
        python3 -I "$HERE/stack_api.py" check-tracer "$((TA_REFRESH_INTERVAL_S * 3 + 60))"
    # a rerun finds the figures already there; it still sees a refresh the schedule ran after loading
    for _ in $(seq 1 $((TA_REFRESH_INTERVAL_S * 2 / 5 + 2))); do
        refreshes="$(refreshes_since "$seeded_at")"
        [ "$refreshes" -ge 1 ] && break
        sleep 5
    done
    "${K[@]}" -n "$TA_NAMESPACE" logs "$pod" | { grep ' refreshed ' || true; } | tail -n 3 >&2
    log "service container running since $started; $refreshes scheduled refreshes since the load at $seeded_at UTC"
    [ -n "$started" ] && [ "$started" = "$(container_started)" ] && [ "$refreshes" -ge 1 ] \
        || die "the figures did not come from a scheduled refresh of the running service"
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" TA_BROWSER_BIN="$TA_BROWSER_BIN" \
        nice -n19 node "$HERE/browser_check.cjs"
}

# The final run (ticket 18): the real UI annotates in a browser and its records reach the events
# table; the figures for that work and for loaded volume; every account against every endpoint; the
# page in a browser; then, with the service stopped, the error panel and annotation unaffected.
# Every run annotates a new project, so it can be repeated on the same stack.
final_py() {
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" TA_KUBE_CONTEXT="$TA_KUBE_CONTEXT" \
        TA_NAMESPACE="$TA_NAMESPACE" TA_RELEASE="$TA_RELEASE" python3 -I -B "$HERE/final_run.py" "$@"
}
final_browser() {
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" TA_BROWSER_BIN="$TA_BROWSER_BIN" \
        nice -n19 node "$HERE/final_browser.cjs" "$@"
}
service_replicas() {
    "${K[@]}" -n "$TA_NAMESPACE" scale deploy/team-analytics --replicas="$1" >&2
    if [ "$1" = 0 ]; then
        "${K[@]}" -n "$TA_NAMESPACE" wait --for=delete pod -l app.kubernetes.io/name=team-analytics --timeout=5m >&2
    else
        "${K[@]}" -n "$TA_NAMESPACE" rollout status deploy/team-analytics --timeout=10m >&2
    fi
}

check_final() {
    local state="$STATE_DIR/final-ui.json" page="$STATE_DIR/final-page.json"
    mkdir -p "$STATE_DIR"
    log "final run: synthetic volume in ta-org-v (history fills while the browser works)"
    final_py load-volume
    log "final run: the real UI annotates a new job in ta-org-c"
    final_py prepare-ui >"$state"
    final_browser annotate "$state"
    final_py check-ui-records "$state"
    log "final run: figures, access, page"
    final_py check-ui-figures "$state" $((TA_REFRESH_INTERVAL_S * 5 + 120))
    final_py check-volume 1200
    final_py check-access
    final_py page-context "$state" >"$page"
    final_browser page "$page"
    log "final run: the service stopped"
    trap 'service_replicas 1' EXIT
    service_replicas 0
    final_browser service-down "$state"
    service_replicas 1
    trap - EXIT
    log "final run passed"
}

# ---------------------------------------------------------------- policies

# The policies the running server serves to OPA (/api/auth/rules, the bundle the chart's OPA
# polls) are checked one at a time: each must equal the import's patched file
# (verify/policy_bundle.sh check) and carry the patch's marker, so a bundle in which either
# policy is the stock one fails.
POLICY_MARKER='Local patch (role floor)'
check_bundle() {
    local work name status=0
    work="$(mktemp -d)"
    cat >"$work/bundle.tar.gz"
    "$ROOT/verify/policy_bundle.sh" check <"$work/bundle.tar.gz" >&2 || status=1
    mkdir "$work/bundle"
    tar -xzf "$work/bundle.tar.gz" -C "$work/bundle" || status=1
    for name in issues.rego comments.rego; do
        if ! grep -qF "$POLICY_MARKER" "$IMPORT_DIR/cvat/apps/engine/rules/$name"; then
            log "the import's $name lacks the patch marker '$POLICY_MARKER'"; status=1
        elif ! grep -qF "$POLICY_MARKER" "$work/bundle/rules/$name" 2>/dev/null; then
            log "rules/$name in the bundle is not the patched policy (missing, or the stock one)"; status=1
        else
            log "rules/$name in the bundle is the patched policy"
        fi
    done
    rm -rf "$work"
    [ "$status" = 0 ] || die "policy bundle check failed"
    log "policy bundle check passed"
}

check_policies() {
    local bundle rc=0
    bundle="$(mktemp)"
    curl -fsS "$BASE_URL/api/auth/rules" -o "$bundle" || { rm -f "$bundle"; die "could not fetch $BASE_URL/api/auth/rules"; }
    log "checking the policy bundle served at $BASE_URL/api/auth/rules"
    (check_bundle <"$bundle") || rc=$?
    rm -f "$bundle"
    [ "$rc" = 0 ] || exit "$rc"
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

# What up does before its first change to the cluster or to the local images: the server image,
# the chart build, the render and its checks. Leaves the render in RENDERED for pull_images.
preflight() {
    check_server_image
    build_chart
    RENDERED="$(mktemp)"
    trap 'rm -f "$RENDERED"' EXIT
    render >"$RENDERED"
    guard_render "$RENDERED"
    check_backend_image "$RENDERED"
}

up() {
    preflight
    pull_images "$RENDERED"
    rm -f "$RENDERED"
    trap - EXIT
    ensure_namespace
    install_chart
    apply_service
    apply_proxy
    wait_ready
    start_port_forward
    check_policies
    seed
    check_event
    check_tracer
    check_final
    log "up:$BASE_URL (accounts: see README.md, password \$TA_SEED_PASSWORD)"
}

case "${1:-}" in
    up) up ;;
    down) teardown ;;
    cycle) rc=0; bash "$0" up || rc=$?; teardown; exit "$rc" ;;
    seed) seed ;;
    check-event) check_event ;;
    check-tracer) check_tracer ;;
    check-final) check_final ;;
    check-policies) check_policies ;;
    check-bundle) check_bundle ;;
    forward) start_port_forward ;;
    status) status ;;
    preflight) preflight; log "preflight passed; nothing was created or pulled" ;;
    build-chart) build_chart; show_path "$CHART_DIR" ;;
    render) build_chart; render ;;
    check-render) [ -f "${2:-}" ] || die "usage: run.sh check-render FILE"
        guard_render "$2"; check_backend_image "$2"; log "render accepted" ;;
    *) sed -n '5,/^set -euo/p' "$0" | sed '$d' >&2; exit 2 ;;
esac
