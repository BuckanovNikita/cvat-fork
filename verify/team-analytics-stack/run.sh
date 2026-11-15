#!/usr/bin/env bash
# Team Analytics test stack: a disposable CVAT v2.82.0 with analytics in its own namespace
# of the local docker-desktop cluster, reached at http://localhost:$TA_HOST_PORT.
# See README.md beside this file.
#
#   run.sh up             preflight, then namespace, chart (with the analytics worker), proxy,
#                         port-forward, seed, checks
#   run.sh down           remove everything up created (succeeds when nothing exists)
#   run.sh cycle          up, then down (also when up fails)
#   run.sh seed           (re)load the synthetic accounts into a running stack and set the Technical
#                         accounts list to TA_TECHNICAL_ACCOUNTS through the settings API
#   run.sh check-worker   the analytics worker: its processes registered (the liveness probe's own
#                         command), its restarts, its log since start
#   run.sh check-event    send a client event through the API and find it in ClickHouse
#   run.sh check-tracer   load working time as real accounts, wait for the scheduled refresh,
#                         check the figures and refusals of /api/team-analytics/, then the page in a browser
#   run.sh check-final    the final run: the real UI annotates in a browser and its records arrive,
#                         figures for that work and for loaded volume, every account and endpoint,
#                         the page, then the page and annotation with the analytics worker at zero
#   run.sh check-final-ui only the real UI's part of check-final and its figures (a new
#                         project each run; no volume, no worker stop)
#   run.sh load-volume [N] only the volume part of check-final: the annotators' accounts, then
#                         what is missing of the load (with N only the current week of the first N
#                         annotators); TA_VOLUME_ORG loads into another organization than ta-org-v
#   run.sh check-volume   only the volume's figures of check-final
#   run.sh check-task-progress  tasks with a job in every stage and state, then the tasks list
#                         in a browser with the stack's UI image: legend, segments, colours, total
#   run.sh check-policies fetch the policy bundle the running server serves and check both
#                         patched policies in it, each by itself
#   run.sh forward        (re)start the port-forward of a running stack; every subcommand that talks to the
#                         stack over HTTP first checks that localhost:$TA_HOST_PORT is this namespace's own
#                         port-forward (its arguments and the port's listener) and stops otherwise
#   run.sh restore-chart  the release back to the stack's own values with analytics on (a release left
#                         pending by a cut-off upgrade is rolled back first), the port-forward on the proxy;
#                         what the evidence steps run when they end or fail, and print when that fails
#   run.sh status        what exists now, and whether the namespace predates the cluster's last restart
#   run.sh preflight      what up does before it touches the cluster: the server image check,
#                         check-issue-policies on both sides, the chart build and the render
#                         checks (render_guard.py, analytics on and off); creates and pulls nothing
#   run.sh build-chart    only build the import's chart with its pinned dependencies
#   run.sh render         print the chart render, CRDs included, that up checks and installs (unchecked);
#                         TA_ANALYTICS=off renders it with analytics disabled
#   run.sh check-render F apply up's render checks to the render in file F
#   run.sh check-bundle   check a policy bundle (tar.gz) given on stdin as check-policies does,
#                         e.g. one from verify/policy_bundle.sh from-image IMAGE
#   run.sh render-proxy   print the proxy's manifests as up checks and applies them
#   run.sh seed-access    (re)load the access cases' accounts (access_accounts.json)
#   run.sh check-access [CASE]
#                         the access cases against the real CVAT: revoked-admin, group-admin,
#                         personal-workspace, header-credentials (all of them without CASE)
#   run.sh check-org-creation
#                         only administrators create organizations: user, worker, owner and maintainer refused
#                         (403, nothing created), an administrator creates one (deleted again); part of up
#   run.sh check-settings the Team Analytics settings API: non-administrators refused, bad bodies refused, a save
#                         one generation step, the user search, project names, a deleted user kept on the list,
#                         and an account joining and leaving the list changing and restoring the week's
#                         figures (ta-org-s); part of up after check-final (its search needs more than 20 users)
#   run.sh check-issues   the issue and comment matrix through the real API, with its own accounts
#                         (issue_accounts.json, one without a global role), judged pass or fail
#   run.sh check-issue-policies [patched|stock]
#                         the same matrix's expectations against the policy engine, no server
#   run.sh check-fixes [STEP]
#                         the defect fixes along the path that failed (fixes_run.py, fixes_browser.cjs), each
#                         judged: status-roles, technical-project, gestures, look, page (the filter bar, the
#                         operations card over a width sweep, the selectors, the terms' tooltips, the settings
#                         modal), unprocessed (holds the
#                         refresh lock), sessions-at-limit (a record), cutover-restart (restarts the analytics
#                         worker); all, in this order, without STEP. Not part of up: run it on a stack up has
#                         passed on
#   Acceptance of the backend path (acceptance.py), not part of up, each judged and printing its numbers:
#   run.sh check-cross-org  an administrator's cached answer is not served for another organization or for
#                         instance scope (nor the instance answer for an organization), nor to a maintainer
#   run.sh check-isolation [PART]
#                         CVAT's core operations with the analytics worker at zero (twelve analytics requests
#                         waiting), with ClickHouse at zero, and with the totals database dropped (parts
#                         worker-down, clickhouse-down, totals-dropped), then the in-memory Redis at zero
#                         (redis-down: reads 503, the schedule and the figures back; always last); restores what
#                         it changed
#   run.sh check-load     p95 of the task list and of a job's annotations before and during twelve concurrent
#                         uncached overviews, during a refresh and while history is filled (needs the volume), with
#                         Postgres connections and Redis memory sampled; TA_LOAD_HEAVY=1: ClickHouse at 4 CPUs,
#                         three volume organizations, the bursts at instance scope (chart upgraded and back)
#   run.sh check-evidence STEP
#                         ticket 09's evidence (evidence.py): rq-start-race (read-only), liveness, killed-worker,
#                         idle-generation (refresh interval 600 s, upgraded and back), two-replicas (two worker
#                         replicas, upgraded and back), off-then-on (analytics off and on by upgrades in place); each
#                         puts the stack's own values back also on a failure or an interrupt
#   run.sh check-review   the review fixes: ignored parameters from the cache, length limits, no-store on
#                         refusals and 429, the generation a counter, the piled-up refresh copies removed
#   run.sh check-analytics-off
#                         reinstalls the release with analytics disabled and checks that the server answers,
#                         no worker runs, no refresh is scheduled and /api/team-analytics/ is 404; leaves the
#                         stack so (run down after it)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
# The chart of the tree, and the analytics component its analytics link points to.
IMPORT_DIR="$ROOT"
CHART_PATHS=(helm-chart components/analytics)
# shellcheck source=stack.env
. "$HERE/stack.env"

MANAGED_BY=cvat-fork-team-analytics-stack
STATE_DIR="$TA_CACHE_DIR/state/$TA_NAMESPACE"
PF_STATE="$STATE_DIR/port-forward"
BASE_URL="http://localhost:$TA_HOST_PORT"

K=(kubectl --context "$TA_KUBE_CONTEXT")
H=(helm_run --kube-context "$TA_KUBE_CONTEXT")

log() { printf '[ta-stack %s] %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
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

# What the tools the launcher runs print when they fail (a Python traceback, a Node stack, a
# Bash error) names files by their full path, which show_path cannot reach. Everything the
# launcher and those tools write to stderr passes through redact_paths, which writes the
# repository root as . and the home directory, by each of its names, as ~. Stdout carries data
# (a render, a bundle check's verdicts) and is left as it is.
redact_paths() {
    local args=() p
    sed_literal() { printf '%s' "$1" | sed 's/[][\.*^$|/]/\\&/g'; }
    for p in "$(realpath -m -- "$HERE/../..")" "$HERE/../.."; do
        args+=(-e "s/$(sed_literal "$p")/./g")
    done
    if [ "$(realpath -m -- "${HOME:-/}")" != / ]; then
        for p in "$(realpath -m -- "$HOME")" "$HOME" "/home/$(id -un)"; do
            args+=(-e "s/$(sed_literal "$p")/~/g")
        done
    fi
    sed -u "${args[@]}"
}
if [ -z "${TA_STDERR_REDACTED:-}" ]; then
    export TA_STDERR_REDACTED=1
    exec 2> >(redact_paths >&2)
fi

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
    # another checkout's stack may have built the same chart meanwhile (the build directory is shared by
    # every stack of this user and named by the chart's content): that build is used, this one dropped
    if [ -f "$build/.complete" ]; then rm -rf "$tmp"; return 0; fi
    rm -rf "$build"
    mv "$tmp" "$build"
    touch "$build/.complete"
}

# The Team Analytics app's settings on every backend pod (cvat/apps/team_analytics/default_settings.py),
# as the chart's additionalEnv (JSON, so a value is passed as it is). The Technical accounts list is no
# setting: the seed sets it through the settings API (stack_api.py seed, TA_TECHNICAL_ACCOUNTS).
analytics_env() {
    python3 -I -c 'import json, sys; a = sys.argv[1:]; print(json.dumps([{"name": n, "value": v} for n, v in zip(a[::2], a[1::2])]))' \
        TEAM_ANALYTICS_REFRESH_INTERVAL_S "$TA_REFRESH_INTERVAL_S"
}

# TA_ANALYTICS=off: the same release with analytics disabled (check-analytics-off and its render check).
helm_args() {
    local ui_repo="${TA_UI_IMAGE%:*}" ui_tag="${TA_UI_IMAGE##*:}"
    printf '%s\n' "$TA_RELEASE" "$CHART_DIR" --namespace "$TA_NAMESPACE" \
        -f "$HERE/values.yaml" \
        --set "cvat.backend.image=${TA_SERVER_IMAGE%:*}" --set "cvat.backend.tag=${TA_SERVER_IMAGE##*:}" \
        --set "cvat.frontend.image=$ui_repo" --set "cvat.frontend.tag=$ui_tag" \
        --set "grafana.grafana\.ini.server.root_url=$BASE_URL/analytics" \
        --set-json "cvat.backend.additionalEnv=$(analytics_env)"
    if [ "${TA_ANALYTICS:-on}" = off ]; then printf '%s\n' --set analytics.enabled=false; fi
    # chart values an evidence step sets for itself (key=value, separated by spaces) and takes back after it
    local s
    for s in ${TA_EXTRA_SET:-}; do printf '%s\n' --set "$s"; done
}

render() {
    local args
    mapfile -t args < <(helm_args)
    # With the CRDs of every chart's crds/ directory, which helm install creates as well.
    "${H[@]}" template --include-crds "${args[@]}"
}

# The images a render may name: the approved pulls, and the images the launcher names itself
# or requires locally. Any other image is refused.
stack_images() {
    printf '%s\n' $TA_APPROVED_PULLS $TA_LOCAL_IMAGES "$TA_SERVER_IMAGE" "$TA_UI_IMAGE" "$TA_PROXY_IMAGE"
}

# Reads a render as the stream of objects kubectl would create from it (kubectl parses each
# document, YAML or JSON, and flattens Lists; --local contacts no server) and has
# render_guard.py judge every object against the cluster's resource list: a namespaced kind
# only, no other namespace than the stack's, every image field on the stack's list and with a
# tag other than latest, no pull policy other than IfNotPresent or Never, nothing that reaches
# the host or the outside (a Service other than ClusterIP, host networking, a host port or path,
# privileged mode, added capabilities), no role binding to a ClusterRole or to a subject
# outside the namespace, and, by allowlist, only the volume sources the genuine render uses, no
# claim that names a volume, no Ingress at all, no Endpoints or EndpointSlice written by hand, and only the
# genuine Secret types. With a second argument, the backend check too: the fork server image is in the
# render and no other image of its repository is, so a fallback to the stock image is refused although it
# is approved. With a third (on or off), the Team Analytics worker must be in the render, or must not.
# Writes the render's images, one per line, to the file named by GUARD_IMAGES when it is set.
guard_render() {
    local rendered="$1" backend="${2:-}" analytics="${3:-}" work rc=0 images
    work="$(mktemp -d)"
    "${K[@]}" api-resources --no-headers >"$work/resources" || { rm -rf "$work"; die "could not list the cluster's resource kinds"; }
    if ! "${K[@]}" label --local --overwrite -f "$rendered" ta-stack-guard=read -o json >"$work/objects.json"; then
        rm -rf "$work"; die "render refused: kubectl cannot read it as Kubernetes objects"
    fi
    mapfile -t images < <(stack_images)
    python3 -I -B "$HERE/render_guard.py" --namespace "$TA_NAMESPACE" --resources "$work/resources" \
        --allow "${images[@]}" ${backend:+--backend "$backend"} ${analytics:+--analytics "$analytics"} <"$work/objects.json" >"$work/images" || rc=$?
    if [ "$rc" = 0 ] && [ -n "${GUARD_IMAGES:-}" ]; then cp "$work/images" "$GUARD_IMAGES"; fi
    rm -rf "$work"
    [ "$rc" = 0 ] || die "render refused"
}

normalize_image() { local i="${1#docker.io/}"; i="${i#index.docker.io/}"; echo "${i#library/}"; }
image_local() { docker image inspect "$1" >/dev/null 2>&1 || docker image inspect "$(normalize_image "$1")" >/dev/null 2>&1; }
approved() {
    local n
    n="$(normalize_image "$1")"
    for a in $TA_APPROVED_PULLS; do [ "$a" = "$n" ] && return 0; done
    return 1
}

# The fork server image (ADR 0007, build-server.sh: a full build from public bases) is in no
# registry: without it locally the release could not start, so up stops here, before anything is
# built, pulled or created. Then, each in a one-off container without network: the image is
# Debian 12 and the python3 on its PATH is 3.12 (Debian's own 3.11 serves supervisord only), and
# the policy bundle its server builds carries the tree's issue and comment policies, and with
# analytics also the Team Analytics policy (verify/policy_bundle.sh, as build-server.sh checks).
check_server_image() {
    local os py work rc=0
    image_local "$TA_SERVER_IMAGE" \
        || die "fork server image $TA_SERVER_IMAGE is not local (IMAGE=$TA_SERVER_IMAGE ./build-server.sh); it is never pulled"
    os="$(docker run --rm --pull=never --network none --cpus=1 --entrypoint sh "$TA_SERVER_IMAGE" -c '. /etc/os-release && echo "$ID $VERSION_ID"')" \
        || die "could not read /etc/os-release in $TA_SERVER_IMAGE"
    [ "$os" = "debian 12" ] || die "$TA_SERVER_IMAGE is '$os', expected 'debian 12' (ADR 0007)"
    py="$(docker run --rm --pull=never --network none --cpus=1 --entrypoint sh "$TA_SERVER_IMAGE" -c 'python3 -c "import sys; print(\"%d.%d\" % sys.version_info[:2])"')" \
        || die "could not run python3 in $TA_SERVER_IMAGE"
    [ "$py" = "3.12" ] || die "python3 on the PATH of $TA_SERVER_IMAGE is $py, expected 3.12"
    log "server image $TA_SERVER_IMAGE: $os, python3 $py"
    work="$(mktemp -d)"
    { "$ROOT/verify/policy_bundle.sh" from-image "$TA_SERVER_IMAGE" >"$work/fork.tar.gz" \
        && "$ROOT/verify/policy_bundle.sh" check <"$work/fork.tar.gz" >&2; } || rc=1
    { "$ROOT/verify/policy_bundle.sh" from-image "$TA_SERVER_IMAGE" analytics >"$work/analytics.tar.gz" \
        && "$ROOT/verify/policy_bundle.sh" check-analytics <"$work/analytics.tar.gz" >&2; } || rc=1
    rm -rf "$work"
    [ "$rc" = 0 ] || die "the policy bundle of $TA_SERVER_IMAGE differs from the tree's policies (build it again from this tree)"
    log "server image $TA_SERVER_IMAGE: its policy bundles, with and without analytics, carry the tree's policies"
}

# Pulls the render's missing images one at a time, at low priority, when they are approved
# pulls; any other missing image stops the run (it must be local, never pulled). $1 is the
# guard's image list.
pull_images() {
    local image
    while read -r image; do
        image_local "$image" && continue
        approved "$image" || die "image $image is not local and is not an approved pull (it is never pulled)"
        log "pulling $(normalize_image "$image")"
        nice -n19 docker pull -q "$(normalize_image "$image")" >&2
    done <"$1"
    image_local "$TA_PROXY_IMAGE" || die "proxy image $TA_PROXY_IMAGE is not local (it is never pulled)"
}

# ---------------------------------------------------------------- namespace

ns_phase() { "${K[@]}" get ns "$TA_NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null || true; }
ns_owned() {
    [ "$("${K[@]}" get ns "$TA_NAMESPACE" -o jsonpath="{.metadata.labels.app\.kubernetes\.io/managed-by}" 2>/dev/null)" = "$MANAGED_BY" ]
}
ns_created() { "${K[@]}" get ns "$TA_NAMESPACE" -o jsonpath='{.metadata.creationTimestamp}'; }
ns_age_hours() {
    echo $(( ($(date +%s) - $(date -d "$(ns_created)" +%s)) / 3600 ))
}

# The cluster sweeper also drops a namespace created before the cluster's last restart. Its
# restart time is the one the sweeper itself recorded on its last tick (k8s-infra: the
# last-run ConfigMap of infra-janitor, restart_at); empty when it cannot be read or when that
# tick had no restart rule. It can lag a restart by one tick, and k8s-infra does not yet count
# the sweeper's restart detection as proven.
cluster_restart_at() {
    "${K[@]}" -n infra-janitor get configmap last-run -o jsonpath='{.data.restart_at}' 2>/dev/null || true
}
# yes, no, or unknown (no readable restart time)
ns_predates_restart() {
    local restart
    restart="$(cluster_restart_at)"
    if [ -z "$restart" ] || ! date -d "$restart" +%s >/dev/null 2>&1; then echo unknown
    elif [ "$(date -d "$(ns_created)" +%s)" -lt "$(date -d "$restart" +%s)" ]; then echo yes
    else echo no
    fi
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
        else
            case "$(ns_predates_restart)" in
                yes) log "namespace $TA_NAMESPACE was created before the cluster's last restart ($(cluster_restart_at)); recreating"
                     teardown ;;
                unknown) log "the cluster's last restart time is not readable (infra-janitor/last-run); only the age rule applies" ;;
            esac
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
             statefulset/"$TA_RELEASE"-redis-master statefulset/"$TA_RELEASE"-vector \
             deploy/"$TA_RELEASE"-backend-worker-team-analytics deploy/ta-proxy; do
        "${K[@]}" -n "$TA_NAMESPACE" rollout status "$w" --timeout=15m >&2 || { report_failures; die "$w not ready"; }
    done
}

# Quota refusals do not reach helm; they show up as FailedCreate events.
report_failures() {
    "${K[@]}" -n "$TA_NAMESPACE" get events --field-selector reason=FailedCreate -o custom-columns=OBJ:.involvedObject.name,MSG:.message --no-headers >&2 || true
    "${K[@]}" -n "$TA_NAMESPACE" describe quota >&2 || true
    "${K[@]}" -n "$TA_NAMESPACE" get pods >&2 || true
}

render_proxy() {
    local rev
    rev="$(sha256sum "$HERE/proxy.yaml" | cut -c1-12)"
    sed -e "s/__RELEASE__/$TA_RELEASE/g" -e "s|__PROXY_IMAGE__|$TA_PROXY_IMAGE|g" -e "s/__CONFIG_REVISION__/$rev/g" \
        "$HERE/proxy.yaml"
}

apply_proxy() {
    local rendered="$STATE_DIR/proxy.yaml"
    mkdir -p "$STATE_DIR"
    render_proxy >"$rendered"
    guard_render "$rendered"
    "${K[@]}" -n "$TA_NAMESPACE" apply -f "$rendered" >&2
}

# ---------------------------------------------------------------- port-forward

# The state file (one per namespace) holds the PID, the process start time and the host port; a
# process is ours only when the PID and the start time still match, so a reused PID is never
# signalled.
pf_owned() {
    [ -f "$PF_STATE" ] || return 1
    local pid start
    read -r pid start _ <"$PF_STATE"
    [ -r "/proc/$pid/stat" ] && [ "$(awk '{print $22}' "/proc/$pid/stat")" = "$start" ]
}
# Ours, and forwarding TA_HOST_PORT: a namespace's port-forward on another port does not count.
pf_alive() {
    pf_owned || return 1
    local port
    read -r _ _ port <"$PF_STATE"
    [ "$port" = "$TA_HOST_PORT" ]
}

# Every step that reads, writes or disrupts through $BASE_URL first makes sure that the address
# serves TA_NAMESPACE: the namespace's own port-forward runs, its arguments name this namespace
# and this port, and it is the process listening on the port. Otherwise kubectl would act on one
# namespace while HTTP went to another stack (a TA_RUN_ID given without its TA_HOST_PORT).
require_own_stack() {
    local pid args listener recorded="" hint=""
    if ! pf_alive; then
        if pf_owned; then
            read -r _ _ recorded <"$PF_STATE"
            hint=" (the port-forward of $TA_NAMESPACE that runs forwards port ${recorded:-unrecorded}; set TA_HOST_PORT to it, or run.sh forward again)"
        fi
        die "no port-forward of $TA_NAMESPACE on port $TA_HOST_PORT is running$hint; run.sh forward with the same TA_RUN_ID (or TA_NAMESPACE) and TA_HOST_PORT"
    fi
    read -r pid _ <"$PF_STATE"
    args=" $(tr '\0' ' ' <"/proc/$pid/cmdline")"
    [[ "$args" == *" -n $TA_NAMESPACE "* && "$args" == *" port-forward "* && "$args" == *" $TA_HOST_PORT:8080 "* ]] \
        || die "the port-forward (pid $pid) is not the one of $TA_NAMESPACE on port $TA_HOST_PORT: its arguments are$args"
    listener="$(ss -Hltnp "sport = :$TA_HOST_PORT" || true)"
    grep -q "pid=$pid," <<<"$listener" \
        || die "port $TA_HOST_PORT is not served by the port-forward of $TA_NAMESPACE (pid $pid); listening there: ${listener:-nothing}"
}

stop_port_forward() {
    if pf_owned; then
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
    setsid "${K[@]}" -n "$TA_NAMESPACE" port-forward --address 127.0.0.1 "${PF_TARGET:-svc/ta-proxy}" "$TA_HOST_PORT:8080" \
        >"$STATE_DIR/port-forward.log" 2>&1 </dev/null &
    local pid=$!
    echo "$pid $(awk '{print $22}' "/proc/$pid/stat") $TA_HOST_PORT" >"$PF_STATE"
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

# Runs a seed script ($1) in the backend's Django shell with the seed password and the accounts
# ($2, JSON) in its environment. Both travel in the script's standard input, as a first line that
# sets them, and never on a command line (kubectl's arguments are visible to every local user in
# the process list): the line is built by a child that reads them from its environment.
backend_shell() {
    local preamble
    preamble="$(TA_SEED_PASSWORD="$TA_SEED_PASSWORD" TA_ACCOUNTS="$2" python3 -I -c '
import base64, json, os
values = {k: os.environ[k] for k in ("TA_SEED_PASSWORD", "TA_ACCOUNTS")}
print(base64.b64encode(json.dumps(values).encode()).decode())')"
    { printf 'import base64, json, os; os.environ.update(json.loads(base64.b64decode("%s")))\n' "$preamble"; cat "$1"; } |
        "${K[@]}" -n "$TA_NAMESPACE" exec -i "$(backend_pod)" -c cvat-backend -- python manage.py shell
}

# The accounts of accounts.json, read back through the API; then the Technical accounts list set to
# TA_TECHNICAL_ACCOUNTS through the settings API as the administrator (unchanged when it already is).
seed() {
    log "loading synthetic accounts"
    backend_shell "$HERE/seed_users.py" "$(cat "$HERE/accounts.json")" >&2
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" TA_TECHNICAL_ACCOUNTS="$TA_TECHNICAL_ACCOUNTS" \
        python3 -I "$HERE/stack_api.py" seed
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

# The analytics worker (templates/cvat_backend/worker_team_analytics): its pod, the liveness probe's own
# command (every process of the queue registered), restarts, and what it logged since start.
worker_pod() {
    "${K[@]}" -n "$TA_NAMESPACE" get pods -l "app.kubernetes.io/instance=$TA_RELEASE,tier=backend,component=worker-team-analytics" \
        --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}'
}
check_worker() {
    local pod procs restarts
    pod="$(worker_pod)"
    [ -n "$pod" ] || die "no running analytics worker pod"
    procs="$("${K[@]}" -n "$TA_NAMESPACE" get pod "$pod" -o jsonpath='{.spec.containers[0].env[?(@.name=="NUMPROCS")].value}')"
    # the processes register a few seconds after the pod is running
    local i
    for i in $(seq 1 30); do
        "${K[@]}" -n "$TA_NAMESPACE" exec "$pod" -c cvat-backend -- django-admin workerprobe team_analytics --expected-num-workers "$procs" >&2 && break
        [ "$i" = 30 ] && die "the analytics worker's probe fails: fewer than $procs processes of the team_analytics queue registered after 90 s"
        sleep 3
    done
    restarts="$("${K[@]}" -n "$TA_NAMESPACE" get pod "$pod" -o jsonpath='{.status.containerStatuses[0].restartCount}')"
    log "analytics worker $pod: $procs processes of the team_analytics queue registered (workerprobe), $restarts restarts, args $("${K[@]}" -n "$TA_NAMESPACE" get pod "$pod" -o jsonpath='{.spec.containers[0].args}')"
    "${K[@]}" -n "$TA_NAMESPACE" get events --field-selector "involvedObject.name=$pod,reason=Unhealthy" \
        -o custom-columns=AT:.lastTimestamp,MSG:.message --no-headers >&2 || true
    mkdir -p "$STATE_DIR"
    "${K[@]}" -n "$TA_NAMESPACE" logs "$pod" -c cvat-backend >"$STATE_DIR/worker.log" 2>&1 || true
    log "the worker's log: $(wc -l <"$STATE_DIR/worker.log") lines in $(show_path "$STATE_DIR/worker.log"); its last lines:"
    tail -n 15 "$STATE_DIR/worker.log" >&2
}

# Working time loaded through the CVAT API as real accounts, so only a scheduled refresh can bring it to
# the figures; nothing triggers one. A refresh is seen by the status endpoint's stamp
# (refresh.last_success_at), which must advance twice while the worker's container keeps running.
check_tracer() {
    local pod started
    pod="$(worker_pod)"
    container_started() {
        "${K[@]}" -n "$TA_NAMESPACE" get pod "$pod" -o jsonpath='{.status.containerStatuses[0].state.running.startedAt}'
    }
    started="$(container_started)"
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" python3 -I "$HERE/stack_api.py" seed-work
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" \
        python3 -I "$HERE/stack_api.py" check-tracer "$((TA_REFRESH_INTERVAL_S * 3 + 60))"
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" \
        python3 -I "$HERE/stack_api.py" check-refresh "$((TA_REFRESH_INTERVAL_S * 4 + 60))"
    log "analytics worker $pod running since $started"
    [ -n "$started" ] && [ "$started" = "$(container_started)" ] \
        || die "the analytics worker's container restarted while the figures were checked"
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" TA_BROWSER_BIN="$TA_BROWSER_BIN" \
        nice -n19 node "$HERE/browser_check.cjs"
}

# The final run (ticket 18): the real UI annotates in a browser and its records reach the events
# table; the figures for that work and for loaded volume; every account against every endpoint; the
# page in a browser; then, with the analytics worker at zero, the error panel and annotation unaffected.
# Every run annotates a new project, so it can be repeated on the same stack.
final_py() {
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" TA_KUBE_CONTEXT="$TA_KUBE_CONTEXT" \
        TA_NAMESPACE="$TA_NAMESPACE" TA_RELEASE="$TA_RELEASE" python3 -I -B "$HERE/final_run.py" "$@"
}
final_browser() {
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" TA_BROWSER_BIN="$TA_BROWSER_BIN" \
        nice -n19 node "$HERE/final_browser.cjs" "$@"
}
# The real UI's part of the final run: a new project in ta-org-c, the browser annotates it (the
# detector with its model list and answers supplied in the browser), the records in ClickHouse.
final_ui() {
    log "final run: the real UI annotates a new job in ta-org-c"
    final_py prepare-ui >"$1"
    final_browser annotate "$1"
    final_py check-ui-records "$1"
}
# Only the real UI's part and its figures (ticket 25): no volume, access, page or worker stop.
check_final_ui() {
    local state="$STATE_DIR/final-ui-only.json"
    mkdir -p "$STATE_DIR"
    final_ui "$state"
    final_py check-ui-figures "$state" $((TA_REFRESH_INTERVAL_S * 5 + 120))
    log "final run, real UI part: passed"
}
# Scales the analytics worker; back up, it waits until a status read is answered again (the checks that
# follow need figures).
ops_py() {
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" TA_KUBE_CONTEXT="$TA_KUBE_CONTEXT" \
        TA_NAMESPACE="$TA_NAMESPACE" TA_RELEASE="$TA_RELEASE" TA_REFRESH_INTERVAL_S="$TA_REFRESH_INTERVAL_S" \
        python3 -I -B "$HERE/acceptance.py" "$@"
}
worker_replicas() { ops_py worker-replicas "$1"; }

# The volume (ticket 26): the annotators' accounts and their memberships through seed_users.py (and the
# organization, owned by ta-owner-v, when it is missing), then final_run.py lays out their jobs, inserts
# the older weeks and has every annotator send the current week through the events API in its own
# session. A later run loads only what is missing.
load_volume() {
    local accounts started=$SECONDS
    log "volume: the annotators' accounts in ${TA_VOLUME_ORG:-ta-org-v}"
    accounts="$(final_py volume-accounts)"
    backend_shell "$HERE/seed_users.py" "$accounts" >/dev/null
    log "volume: accounts ready after $((SECONDS - started)) s"
    final_py load-volume ${1:+"$1"}
    log "volume: done after $((SECONDS - started)) s"
}

check_final() {
    local state="$STATE_DIR/final-ui.json" page="$STATE_DIR/final-page.json"
    mkdir -p "$STATE_DIR"
    log "final run: synthetic volume in ${TA_VOLUME_ORG:-ta-org-v} (history fills while the browser works)"
    load_volume
    final_ui "$state"
    log "final run: figures, access, page"
    final_py check-ui-figures "$state" $((TA_REFRESH_INTERVAL_S * 5 + 120))
    final_py check-volume 1200
    final_py check-access
    final_py page-context "$state" >"$page"
    final_browser page "$page"
    log "final run: the analytics worker at zero"
    trap 'worker_replicas 1' EXIT
    worker_replicas 0
    # answers the page read before are cached under the current generation; a new one makes every read a miss
    ops_py cache advance
    final_browser service-down "$state"
    worker_replicas 1
    trap - EXIT
    log "final run passed"
}

# ---------------------------------------------------------------- task progress

# The fork's task-progress summary on the tasks list (ticket 10): the seed creates, as ta-admin in
# its personal workspace, a task with one job in each stage and state the server's schema names and
# a task with a single annotation/new job; a headless browser then reads both task cards from the
# UI the stack serves, which must be TA_UI_IMAGE. Every run seeds new tasks.
check_task_progress() {
    local state="$STATE_DIR/task-progress.json" ui
    mkdir -p "$STATE_DIR"
    ui="$("${K[@]}" -n "$TA_NAMESPACE" get deploy "$TA_RELEASE-frontend" -o jsonpath='{.spec.template.spec.containers[*].image}')"
    [ "$ui" = "$TA_UI_IMAGE" ] || die "the frontend runs '$ui', not the UI image under test $TA_UI_IMAGE"
    log "task progress: UI image $TA_UI_IMAGE (local $(docker image inspect --format '{{.Id}}' "$TA_UI_IMAGE" 2>/dev/null || echo 'none'); running $("${K[@]}" -n "$TA_NAMESPACE" get pods -l "app.kubernetes.io/instance=$TA_RELEASE,tier=frontend" -o jsonpath='{.items[*].status.containerStatuses[*].imageID}'))"
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" python3 -I -B "$HERE/task_progress.py" seed >"$state"
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" TA_BROWSER_BIN="$TA_BROWSER_BIN" \
        nice -n19 node "$HERE/task_progress_browser.cjs" "$state"
    log "task progress check passed"
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
    # Only an archive the check accepted is extracted: it holds each policy once, as a file.
    # The markers are looked for only then.
    [ "$status" = 0 ] && { tar -xzf "$work/bundle.tar.gz" -C "$work/bundle" || status=1; }
    local extracted="$status"
    for name in issues.rego comments.rego; do
        [ "$extracted" = 0 ] || break
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

# ---------------------------------------------------------------- access cases

access_py() {
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" python3 -I -B "$HERE/access_cases.py" "$@"
}

# The access cases' own accounts (access_accounts.json); puts the revoked administrator back in the admin group.
seed_access() {
    log "loading the access cases' accounts"
    backend_shell "$HERE/seed_access.py" "$(cat "$HERE/access_accounts.json")" >&2
}

# The four access cases against the real CVAT, each judged by access_cases.py; with an argument,
# only that case.
ACCESS_CASES=(revoked-admin group-admin personal-workspace header-credentials)
check_access_cases() {
    local only="${1:-}" c
    [ -z "$only" ] || [[ " ${ACCESS_CASES[*]} " == *" $only "* ]] || die "unknown access case $only (${ACCESS_CASES[*]})"
    seed_access
    for c in "${ACCESS_CASES[@]}"; do
        [ -z "$only" ] || [ "$c" = "$only" ] || continue
        log "access case: $c"
        if [ "$c" = personal-workspace ]; then
            access_py "$c" "$((TA_REFRESH_INTERVAL_S * 3 + 60))"
        else
            access_py "$c"
        fi
    done
}

# Only administrators create organizations (ORGANIZATIONS_MIN_ROLE_TO_CREATE = "admin" in the fork's settings):
# org_creation.py has accounts with the global role user and worker and an owner and a maintainer of an
# organization refused, an administrator create one (deleted again), and the administrator read both seeded
# organizations. Its worker and user accounts come from issue_accounts.json and accounts.json, loaded here (the
# seed creates organizations through the ORM, not through the API the rule guards).
check_org_creation() {
    log "organization creation: loading the accounts of accounts.json and issue_accounts.json"
    backend_shell "$HERE/seed_users.py" "$(cat "$HERE/accounts.json")" >/dev/null
    backend_shell "$HERE/seed_users.py" "$(cat "$HERE/issue_accounts.json")" >/dev/null
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" python3 -I -B "$HERE/org_creation.py" check
}

# ---------------------------------------------------------------- settings

# The Team Analytics settings API (settings_check.py): refusals, bad bodies, the generation step of a save, the user
# search, project names, a deleted user kept on the list, and the list's retroactive effect on ta-org-s's week. The
# accounts of accounts.json are loaded first (ta-org-s's probe accounts with them), and a throwaway user for the
# deleted-account part, which deletes it. The Technical accounts list is put back as the seed set it.
check_settings() {
    local gone="ta-gone-$(date +%s)"
    log "settings: loading the accounts of accounts.json and the throwaway user $gone"
    backend_shell "$HERE/seed_users.py" "$(cat "$HERE/accounts.json")" >/dev/null
    backend_shell "$HERE/seed_users.py" "{\"users\": {\"$gone\": {\"admin\": false}}, \"organizations\": {}}" >/dev/null
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" TA_KUBE_CONTEXT="$TA_KUBE_CONTEXT" \
        TA_NAMESPACE="$TA_NAMESPACE" TA_RELEASE="$TA_RELEASE" \
        python3 -I -B "$HERE/settings_check.py" check "$((TA_REFRESH_INTERVAL_S * 3 + 60))" "$gone"
    log "settings check passed"
}

# ---------------------------------------------------------------- issue matrix

# The issue and comment matrix (ticket 09) through the real API: seed_users.py loads the accounts
# and two organizations of issue_accounts.json, issue_matrix.py sets their global roles through
# the admin API (one has none), lays out jobs, issues and comments, runs every row and judges it.
# Needs the stack's own seed (ta-admin). Repeatable on the same stack.
check_issues() {
    local out="$STATE_DIR/issue-matrix.json"
    mkdir -p "$STATE_DIR"
    log "issue matrix: loading the accounts of issue_accounts.json"
    backend_shell "$HERE/seed_users.py" "$(cat "$HERE/issue_accounts.json")" >&2
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" python3 -I -B "$HERE/issue_matrix.py" live "$out"
    log "issue matrix results: $(show_path "$out")"
}

# The same matrix's expectations against the policy engine, without a server: issue_matrix.py
# builds the input the stock server would send for every row, OPA (local image, no network) decides,
# and issue_matrix.py judges. MODE patched reads the import's policies, MODE stock those of
# STOCK_TAG, as verify/policy_test.sh does; each mode has its own expectation column.
check_issue_policies() {
    local mode="${1:-patched}" work p image="${OPA_IMAGE:-openpolicyagent/opa:1.12.2}" stock_tag="${STOCK_TAG:-v2.82.0}"
    local policies=(cvat/apps/engine/rules/issues.rego cvat/apps/engine/rules/comments.rego
        cvat/apps/iam/rules/utils.rego cvat/apps/organizations/rules/organizations.rego)
    case "$mode" in patched | stock) ;; *) die "usage: run.sh check-issue-policies [patched|stock]" ;; esac
    image_local "$image" || die "OPA image $image is not local (it is never pulled)"
    work="$(mktemp -d)"
    for p in "${policies[@]}"; do
        mkdir -p "$work/policies/$(dirname "$p")"
        if [ "$mode" = patched ]; then cp "$IMPORT_DIR/$p" "$work/policies/$p"
        else git -C "$ROOT" show "$stock_tag:$p" >"$work/policies/$p" || { rm -rf "$work"; die "no $p in $stock_tag"; }; fi
    done
    python3 -I -B "$HERE/issue_matrix.py" opa-cases >"$work/cases.json"
    chmod -R a+rX "$work"
    local rc=0
    # The OPA image is one of TA_LOCAL_IMAGES: never pulled, also not by this check in preflight.
    docker run --rm --pull=never --network none --cpus=1 --memory=256m -v "$work:/work:ro" "$image" \
        eval --format json --data /work/policies --data /work/cases.json \
        "$(python3 -I -B -c 'import sys; sys.path.insert(0, sys.argv[1]); import issue_matrix; print(issue_matrix.OPA_QUERY)' "$HERE")" \
        >"$work/answers.json" || rc=$?
    [ "$rc" = 0 ] && { python3 -I -B "$HERE/issue_matrix.py" opa-judge "$mode" <"$work/answers.json" || rc=$?; }
    rm -rf "$work"
    [ "$rc" = 0 ] || die "issue matrix expectations differ from the $mode policies"
}

# ---------------------------------------------------------------- defect fixes

# Each fix of the defect-fixes spec along the path that failed (ticket 27), on a stack up has passed on (it
# needs the final run's tagged work and volume). Steps that change the stack's own state come last:
# unprocessed holds the refresh lock and adds a marker event for at most two minutes, cutover-restart
# scales the analytics worker to zero, empties the stored cutover and the ready mark and scales it up again. Screenshots of look go to
# TA_SCREENSHOT_DIR, by default beside the state directory, which down leaves alone.
FIX_STEPS=(status-roles technical-project gestures look page unprocessed sessions-at-limit cutover-restart)
FIX_SHOTS="${TA_SCREENSHOT_DIR:-$TA_CACHE_DIR/screenshots/$TA_NAMESPACE}"
fixes_py() {
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" TA_KUBE_CONTEXT="$TA_KUBE_CONTEXT" \
        TA_NAMESPACE="$TA_NAMESPACE" TA_RELEASE="$TA_RELEASE" TA_REFRESH_INTERVAL_S="$TA_REFRESH_INTERVAL_S" \
        python3 -I -B "$HERE/fixes_run.py" "$@"
}
fixes_browser() {
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" TA_BROWSER_BIN="$TA_BROWSER_BIN" \
        TA_SCREENSHOT_DIR="$FIX_SHOTS" TA_TECHNICAL_ACCOUNTS="$TA_TECHNICAL_ACCOUNTS" TA_VOLUME_ORG="${TA_VOLUME_ORG:-ta-org-v}" \
        nice -n19 node "$HERE/fixes_browser.cjs" "$@"
}
check_fixes() {
    local only="${1:-}" step state="$STATE_DIR/fixes-gestures.json"
    [ -z "$only" ] || [[ " ${FIX_STEPS[*]} " == *" $only "* ]] || die "unknown step $only (${FIX_STEPS[*]})"
    require_own_stack
    mkdir -p "$STATE_DIR"
    for step in "${FIX_STEPS[@]}"; do
        [ -z "$only" ] || [ "$step" = "$only" ] || continue
        log "defect fixes: $step"
        case "$step" in
            gestures)
                fixes_py prepare-gestures >"$state"
                fixes_browser gestures "$state"
                fixes_py check-gestures "$state" ;;
            look)
                # ta-org-c's rows hold every operation (the bars must show several parts); the volume's
                # organization fills both cards with eight rows and long names
                fixes_browser look ta-org-c split
                fixes_browser look "${TA_VOLUME_ORG:-ta-org-v}"
                log "screenshots: $(show_path "$FIX_SHOTS")" ;;
            page)
                # ta-org-c: the real UI's work (Model objects among it) for the bar, the sweep, the terms, the
                # settings modal and the screenshots; the selectors and their popups use the volume's organization
                # (TA_VOLUME_ORG: forty projects, a hundred annotators); instance scope's names are judged against
                # what the organizations' own selectors name
                fixes_browser page ta-org-c ;;
            *) fixes_py "$step" ;;
        esac
    done
    log "defect fixes: ${only:-all steps} passed"
}

# ---------------------------------------------------------------- acceptance of the backend path

# Each judged by acceptance.py, with its measured numbers in the output. They change the stack's state
# for a while (the worker or ClickHouse at zero, the totals database dropped, history marked for
# recomputing) and restore it, also on a failure.
acceptance() {
    require_own_stack
    ops_py "$@"
}

# The release reinstalled with analytics disabled (the same namespace and data): the server starts and
# answers, the render has no analytics worker, none runs, no refresh is scheduled, /api/team-analytics/ is
# 404. Checked through the backend's own Service on the stack's port: the proxy's nginx names Grafana,
# which goes away with analytics. The stack stays so; run down after it.
check_analytics_off() {
    require_own_stack
    build_chart
    TA_ANALYTICS=off install_chart_off
    "${K[@]}" -n "$TA_NAMESPACE" rollout status deploy/"$TA_RELEASE"-backend-server --timeout=15m >&2
    "${K[@]}" -n "$TA_NAMESPACE" wait --for=delete pod -l "app.kubernetes.io/instance=$TA_RELEASE,component=worker-team-analytics" --timeout=5m >&2 || true
    [ -z "$("${K[@]}" -n "$TA_NAMESPACE" get deploy,pod -l "app.kubernetes.io/instance=$TA_RELEASE,component=worker-team-analytics" -o name)" ] \
        || die "an analytics worker is still there with analytics disabled"
    log "analytics disabled: no analytics worker Deployment or pod in $TA_NAMESPACE"
    # the reinstall's initializer job (named by the release revision) runs syncperiodicjobs: with the queue still
    # defined and the schedule no longer configured, it deletes the stored refresh schedule
    local init
    init="$("${K[@]}" -n "$TA_NAMESPACE" get jobs -l "app.kubernetes.io/instance=$TA_RELEASE,component=initializer" \
        --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1:].metadata.name}')"
    "${K[@]}" -n "$TA_NAMESPACE" wait --for=condition=complete --timeout=10m "job/$init" >&2
    log "initializer $init, syncperiodicjobs on the team_analytics queue:"
    "${K[@]}" -n "$TA_NAMESPACE" logs "job/$init" | grep -A3 'Processing queue team_analytics' >&2 || true
    "${K[@]}" -n "$TA_NAMESPACE" logs "job/$init" | grep -q 'Deleting job team_analytics_refresh' \
        || die "the initializer of the reinstall did not delete the refresh schedule"
    stop_port_forward
    PF_TARGET="svc/$TA_RELEASE-backend-service" start_port_forward
    ops_py analytics-off
}
install_chart_off() {
    local args
    mapfile -t args < <(helm_args)
    log "reinstalling chart release $TA_RELEASE with analytics disabled"
    "${H[@]}" upgrade --install "${args[@]}" --timeout 20m >&2
}

# ---------------------------------------------------------------- evidence (ticket 09)

# Evidence checks for a verification stack (its own TA_RUN_ID and port), each judged by evidence.py or
# acceptance.py. Steps that need other chart values upgrade the release in place with them (TA_EXTRA_SET, or
# another TA_REFRESH_INTERVAL_S) and upgrade it back to the stack's own values afterwards, also on a failure or
# an interrupt (an EXIT trap runs chart_restore); off-then-on likewise puts analytics back on and the
# port-forward back on the proxy. When the restore itself fails, it prints the command to run by hand.
EVIDENCE_STEPS=(rq-start-race liveness killed-worker idle-generation two-replicas off-then-on)
ev_py() {
    TA_BASE_URL="$BASE_URL" TA_SEED_PASSWORD="$TA_SEED_PASSWORD" TA_KUBE_CONTEXT="$TA_KUBE_CONTEXT" \
        TA_NAMESPACE="$TA_NAMESPACE" TA_RELEASE="$TA_RELEASE" python3 -I -B "$HERE/evidence.py" "$@"
}

# The release upgraded in place with the environment's TA_EXTRA_SET and TA_REFRESH_INTERVAL_S, then rolled out.
chart_upgrade() {
    log "chart: upgrading in place (extra values: ${TA_EXTRA_SET:-none}; refresh interval ${TA_REFRESH_INTERVAL_S} s)"
    build_chart
    install_chart
    wait_ready
}
# The release's own state. An upgrade, install or rollback cut off (an interrupt during helm upgrade) leaves
# it pending-upgrade, pending-install or pending-rollback, and helm refuses every upgrade while it is: the
# release is first rolled back to its revision before (the last one deployed).
release_settle() {
    local state
    state="$("${H[@]}" status "$TA_RELEASE" -n "$TA_NAMESPACE" -o json \
        | python3 -I -c 'import json, sys; print(json.load(sys.stdin)["info"]["status"])')"
    case "$state" in
        pending-*)
            log "release $TA_RELEASE is $state (an operation was cut off): rolling it back to its revision before"
            "${H[@]}" rollback "$TA_RELEASE" -n "$TA_NAMESPACE" --wait --timeout 20m >&2 ;;
        *) log "release $TA_RELEASE is $state" ;;
    esac
}
# run.sh restore-chart: the stack's own values (stack.env's refresh interval, nothing extra, analytics on), the
# workloads ready, and the port-forward on the proxy again.
restore_chart() {
    release_settle
    log "chart: back to the stack's own values"
    build_chart
    install_chart
    wait_ready
    start_port_forward
}
# The command restore-chart runs with, for a person to run by hand from the repository root.
restore_command() {
    printf 'TA_KUBE_CONTEXT=%q TA_NAMESPACE=%q TA_RELEASE=%q TA_HOST_PORT=%q TA_REFRESH_INTERVAL_S=%q TA_SERVER_IMAGE=%q TA_UI_IMAGE=%q bash verify/team-analytics-stack/run.sh restore-chart' \
        "$TA_KUBE_CONTEXT" "$TA_NAMESPACE" "$TA_RELEASE" "$TA_HOST_PORT" "$STACK_REFRESH_INTERVAL_S" "$TA_SERVER_IMAGE" "$TA_UI_IMAGE"
}
# Back to the stack's own values, in a process of its own: the values a step set for itself (TA_EXTRA_SET,
# TA_ANALYTICS, another TA_REFRESH_INTERVAL_S, PF_TARGET) may still be in force when an interrupt runs the EXIT
# trap in the middle of that step, and a fresh process has set -e in force wherever it is called from.
chart_restore() {
    env -u TA_EXTRA_SET -u TA_ANALYTICS -u PF_TARGET \
        TA_KUBE_CONTEXT="$TA_KUBE_CONTEXT" TA_NAMESPACE="$TA_NAMESPACE" TA_RELEASE="$TA_RELEASE" \
        TA_HOST_PORT="$TA_HOST_PORT" TA_REFRESH_INTERVAL_S="$STACK_REFRESH_INTERVAL_S" \
        TA_SERVER_IMAGE="$TA_SERVER_IMAGE" TA_UI_IMAGE="$TA_UI_IMAGE" bash "$0" restore-chart && return 0
    log "error: the stack could not be put back to its own values; run by hand, from the repository root:"
    log "  $(restore_command)"
    return 1
}
STACK_REFRESH_INTERVAL_S="$TA_REFRESH_INTERVAL_S"

# The newest revision of the release and its description ("Upgrade complete" for an upgrade in place).
helm_last() {
    "${H[@]}" history "$TA_RELEASE" -n "$TA_NAMESPACE" -o json \
        | python3 -I -c 'import json, sys; h = json.load(sys.stdin)[-1]; print(h["revision"], h["description"])'
}
expect_upgrade() {
    local before="$1" what="$2" now rev
    now="$(helm_last)"
    rev="${now%% *}"
    log "helm history after $what: revision $now (before: revision $before)"
    [ "$rev" = "$((before + 1))" ] && [ "${now#* }" = "Upgrade complete" ] \
        || die "$what: expected revision $((before + 1)) 'Upgrade complete' (an upgrade in place), saw '$now'"
}

check_evidence() {
    local step="${1:-}" state rev
    [[ " ${EVIDENCE_STEPS[*]} " == *" $step "* ]] || die "usage: run.sh check-evidence STEP (${EVIDENCE_STEPS[*]})"
    require_own_stack
    mkdir -p "$STATE_DIR"
    case "$step" in
        idle-generation)
            trap chart_restore EXIT
            TA_REFRESH_INTERVAL_S=600 chart_upgrade
            ev_py idle-generation 600
            trap - EXIT
            chart_restore ;;
        two-replicas)
            trap chart_restore EXIT
            TA_EXTRA_SET="cvat.backend.worker.teamAnalytics.replicas=2" chart_upgrade
            ev_py two-replicas
            trap - EXIT
            chart_restore
            [ "$("${K[@]}" -n "$TA_NAMESPACE" get deploy "$TA_RELEASE-backend-worker-team-analytics" -o jsonpath='{.spec.replicas}')" = 1 ] \
                || die "the analytics worker is not back at one replica" ;;
        off-then-on)
            state="$STATE_DIR/evidence-off-then-on.json"
            ev_py snapshot "$state"
            rev="$(helm_last)"; rev="${rev%% *}"
            # from here until analytics is on again and the port-forward is on the proxy, a failure or an
            # interrupt restores both (check_analytics_off leaves analytics off and forwards to the backend)
            trap chart_restore EXIT
            check_analytics_off
            expect_upgrade "$rev" "analytics off"
            log "analytics on again, upgraded in place"
            build_chart
            install_chart
            wait_ready
            expect_upgrade "$((rev + 1))" "analytics on again"
            stop_port_forward
            start_port_forward
            trap - EXIT
            ev_py back-on "$state" ;;
        *) ev_py "$step" ;;
    esac
}

# The heavier load configuration (TA_LOAD_HEAVY=1 run.sh check-load): ClickHouse limited to 4 CPUs instead of 2,
# three times the volume (ta-org-v, then ta-org-v2 and ta-org-v3 loaded the same way, with the same annotators),
# and the bursts read at instance scope over all of it; the chart is upgraded back afterwards.
check_load() {
    if [ "${TA_LOAD_HEAVY:-}" != 1 ]; then acceptance load; return; fi
    local org
    trap chart_restore EXIT
    TA_EXTRA_SET="clickhouse.resources.limits.cpu=4" chart_upgrade
    for org in "${TA_VOLUME_ORG:-ta-org-v}" ta-org-v2 ta-org-v3; do
        TA_VOLUME_ORG="$org" load_volume
    done
    TA_LOAD_SCOPE=instance acceptance load
    trap - EXIT
    chart_restore
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
    if [ -n "$(ns_phase)" ]; then
        echo "created:   $(ns_created); cluster's last restart $(cluster_restart_at || true); created before it: $(ns_predates_restart)"
    fi
    echo "address:   $BASE_URL"
    if pf_alive; then echo "port-forward: running (pid $(cut -d' ' -f1 "$PF_STATE"))"; else echo "port-forward: not running"; fi
    [ -n "$(ns_phase)" ] && "${K[@]}" -n "$TA_NAMESPACE" get pods,pvc
    return 0
}

# What up does before its first change to the cluster or to the local images: the server image,
# the issue matrix's expectations against both sides' policies (no server), the chart build,
# the render and its checks. Leaves the render's images in RENDER_IMAGES for pull_images.
preflight() {
    check_server_image
    check_issue_policies patched
    check_issue_policies stock
    build_chart
    RENDERED="$(mktemp)" RENDER_IMAGES="$(mktemp)"
    trap 'rm -f "$RENDERED" "$RENDER_IMAGES"' EXIT
    render >"$RENDERED"
    GUARD_IMAGES="$RENDER_IMAGES" guard_render "$RENDERED" "$TA_SERVER_IMAGE" on
    log "render accepted, with the analytics worker"
    check_render_off
}

# The render with analytics disabled holds no analytics worker (and passes the same guard).
check_render_off() {
    local off
    off="$(mktemp)"
    TA_ANALYTICS=off render >"$off"
    (guard_render "$off" "$TA_SERVER_IMAGE" off) || { rm -f "$off"; die "the render with analytics disabled was refused"; }
    log "render with analytics disabled accepted: no analytics worker in it ($(grep -c '^kind: Deployment' "$off") Deployments)"
    rm -f "$off"
}

up() {
    local image
    preflight
    pull_images "$RENDER_IMAGES"
    for image in $TA_LOCAL_IMAGES; do
        image_local "$image" || die "image $image is not local (it is never pulled)"
    done
    rm -f "$RENDERED" "$RENDER_IMAGES"
    trap - EXIT
    ensure_namespace
    install_chart
    apply_proxy
    wait_ready
    start_port_forward
    require_own_stack
    check_worker
    check_policies
    seed
    check_event
    check_tracer
    check_task_progress
    check_final
    check_settings
    check_issues
    check_access_cases
    check_org_creation
    log "up:$BASE_URL (accounts: see README.md, password \$TA_SEED_PASSWORD)"
}

# Every subcommand that talks to the stack through $BASE_URL checks first that the address serves TA_NAMESPACE.
case "${1:-}" in
    seed | check-event | check-tracer | check-final | check-final-ui | load-volume | check-volume \
        | check-task-progress | check-policies | check-access | check-org-creation | check-settings | check-issues \
        | check-fixes | check-cross-org | check-isolation | check-load | check-evidence | check-review \
        | check-analytics-off)
        require_own_stack ;;
esac

case "${1:-}" in
    up) up ;;
    down) teardown ;;
    cycle) rc=0; bash "$0" up || rc=$?; teardown; exit "$rc" ;;
    seed) seed ;;
    check-worker) check_worker ;;
    check-event) check_event ;;
    check-tracer) check_tracer ;;
    check-final) check_final ;;
    check-final-ui) check_final_ui ;;
    load-volume) load_volume "${2:-}" ;;
    check-volume) final_py check-volume 1200 ;;
    check-task-progress) check_task_progress ;;
    check-policies) check_policies ;;
    check-bundle) check_bundle ;;
    check-issues) check_issues ;;
    check-issue-policies) check_issue_policies "${2:-patched}" ;;
    forward) start_port_forward ;;
    status) status ;;
    preflight) preflight; log "preflight passed; nothing was created or pulled" ;;
    build-chart) build_chart; show_path "$CHART_DIR" ;;
    render) build_chart; render ;;
    check-render) [ -f "${2:-}" ] || die "usage: run.sh check-render FILE"
        guard_render "$2" "$TA_SERVER_IMAGE" "${TA_ANALYTICS:-on}"; log "render accepted" ;;
    render-proxy) render_proxy ;;
    seed-access) seed_access ;;
    check-access) check_access_cases "${2:-}" ;;
    check-org-creation) check_org_creation ;;
    check-settings) check_settings ;;
    check-fixes) check_fixes "${2:-}" ;;
    check-cross-org) acceptance cross-org ;;
    check-isolation)
        case "${2:-}" in
            redis-down) require_own_stack; ev_py redis-down ;;
            "") acceptance isolation; ev_py redis-down ;;  # Redis last: it restarts what depends on it
            *) acceptance isolation "$2" ;;
        esac ;;
    check-load) check_load ;;
    check-evidence) check_evidence "${2:-}" ;;
    restore-chart) restore_chart ;;
    check-review) acceptance review ;;
    check-analytics-off) check_analytics_off ;;
    *) sed -n '5,/^set -euo/p' "$0" | sed '$d' >&2; exit 2 ;;
esac
