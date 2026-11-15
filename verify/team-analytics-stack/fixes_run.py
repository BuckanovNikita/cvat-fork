"""The defect fixes seen on the test stack along the path that failed (ticket 27 of the defect fixes), driven by
run.sh check-fixes. Each step judges itself and stops at the first difference; sessions-at-limit only records.

    fixes_run.py status-roles           status as a maintainer, an owner and an administrator: only the
                                        administrator gets the first event day and the day counts
    fixes_run.py technical-project      a project whose only work is boxes a technical account saved has its
                                        row in the details table by project
    fixes_run.py prepare-gestures       a new project, task and job in ta-org-c with FRAMES frames, one frame
                                        per chunk, for fixes_browser.cjs gestures (prints JSON)
    fixes_run.py check-gestures FILE    after fixes_browser.cjs gestures: the redo, the group drags and the
                                        held frame key read back from the events table, and their figures
    fixes_run.py unprocessed            a period that is not fully processed, read directly by a maintainer
                                        and an administrator: the envelope only, then figures once processed
    fixes_run.py sessions-at-limit      how many stored sessions reached the one-day limit (a record)
    fixes_run.py cutover-restart        the service restarted on a stack that already holds tagged work and
                                        has no cutover stored: its first status carries the cutover

Environment as final_run.py (TA_BASE_URL, TA_SEED_PASSWORD, TA_KUBE_CONTEXT, TA_NAMESPACE, TA_RELEASE), and
TA_REFRESH_INTERVAL_S. Standard library only.

Two steps change the stack's own state to reach the path that failed; both are supplied boundaries, not an
upgrade from an older release. `unprocessed` holds the refresh lease for at most LEASE_S seconds (no history
step runs meanwhile) and inserts one marker event a few days before the first recorded event, which makes
those days unprocessed; it releases the lease, waits until the service has processed them, and deletes the
marker. `cutover-restart` stops the service, empties the totals database's `cutover` table and drops
`history_today`, which is what a totals database written by a service from before the cutover search and
the short-window history holds, and starts the service again.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run with python3 -I, which leaves it out

from final_run import (  # noqa: E402
    UI_ORG,
    by_key,
    clickhouse,
    log,
    ok,
    payload,
    service,
    wait_figures,
    wait_rows,
)
from stack_api import Session, check, upload_images  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CONTROL_SQL = ROOT / "team-analytics" / "service" / "sql" / "control"
TOTALS = "team_analytics"  # TEAM_ANALYTICS_DB in team-analytics/k8s/config.yaml
REFRESH_S = int(os.environ.get("TA_REFRESH_INTERVAL_S") or "60")
TECHNICAL_ACCOUNT = "ta-bot"
BOT_BOXES = 3
FRAMES = 24
SESSION_GAP_MS = 300_000
DAY_MS = 86_400_000
LEASE_S = 110  # the probe's own lease; the service's is 120 s
PROBE = "ta-stack:unprocessed-probe"
PROBE_DAYS_BEFORE = 3
ADMIN_ONLY_HISTORY = {"ready_from", "ready_from_day", "first_day", "days_ready", "days_total"}
SHARED_HISTORY = {"complete", "percent", "periods", "earliest_month", "complete_weeks", "trends_ready"}
LEGACY_FLAGS = {"legacy", "partly_legacy", "cutover", "shapes"}
# what an answer for a period not fully processed keeps (docs/fork-specification.md, TA-1)
ENVELOPES = {
    "overview": {"period", "filters", "processed", "operations"},
    "list": {"period", "processed", "by"} | LEGACY_FLAGS,
    "details": {"by", "page_size", "processed", "technical_accounts"} | LEGACY_FLAGS,
}
TREND_POINT_FLAGS = {"legacy", "hotkey_recorded"}
# the operation events of control/cutover_find.sql
TAGGED = (
    "source = 'client' AND user_id IS NOT NULL AND job_id IS NOT NULL"
    " AND (scope IN ('draw:object', 'paste:object', 'propagate:object', 'drag:object', 'resize:object', 'delete:object')"
    " OR (scope = 'debug:info' AND obj_name = 'team_analytics:class_change'))"
    " AND JSONHas(ifNull(payload, ''), 'shape_type')"
)


def kubectl(*args: str, capture: bool = False) -> str:
    command = ["kubectl", "--context", os.environ["TA_KUBE_CONTEXT"], "-n", os.environ["TA_NAMESPACE"], *args]
    out = subprocess.run(command, capture_output=True, text=True, check=False)
    if out.returncode:
        raise SystemExit(f"kubectl {' '.join(args)}: {out.stderr.strip()[:300]}")
    return out.stdout if capture else ""


def control_sql(name: str, **params: object) -> str:
    """A statement of the service's own control SQL with its parameters written in as literals."""
    text = (CONTROL_SQL / name).read_text().replace("$totals_db", TOTALS)

    def literal(match: re.Match) -> str:
        value = params[match.group(1)]
        if value is None:
            return "NULL"
        if isinstance(value, int):
            return str(value)
        return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"

    return re.sub(r"\{(\w+):[^{}]*\}", literal, text)


def status_of(session: Session, org: str = "") -> dict:
    return ok(session, "status", org=org)


# ---------------------------------------------------------------- status by role


def status_roles() -> None:
    cases = [
        ("ta-maintainer", "ta-org-a", SHARED_HISTORY),
        ("ta-owner", "ta-org-a", SHARED_HISTORY),
        ("ta-admin", "", SHARED_HISTORY | ADMIN_ONLY_HISTORY),
        ("ta-admin", "ta-org-a", SHARED_HISTORY | ADMIN_ONLY_HISTORY),
    ]
    cutovers = set()
    for username, org, want in cases:
        body = status_of(Session(username), org)
        check({"history", "refresh", "cutover"} <= set(body), f"{username} org={org or '-'} status keys {sorted(body)}")
        got = set(body["history"] or {})
        check(got == want, f"{username} org={org or '-'} history keys {sorted(got)}, expected {sorted(want)}")
        check(body["cutover"] is not None and "at" in body["cutover"], f"{username} cutover {body['cutover']}")
        cutovers.add(body["cutover"]["at"])
        log(f"{username}, org={org or '-'}: history {sorted(got)}; cutover {body['cutover']['at']}")
    check(len(cutovers) == 1 and None not in cutovers, f"cutover differs by caller or is missing: {cutovers}")


# ---------------------------------------------------------------- the technical account's project


def new_job(owner: Session, name: str, frames: int, chunk_size: int | None = None) -> dict:
    project = owner.request(
        "POST",
        f"/api/projects?org={UI_ORG}",
        {"name": name, "labels": [{"name": "box", "color": "#ff4136"}, {"name": "other", "color": "#1890ff"}]},
    )
    task = owner.request(
        "POST", f"/api/tasks?org={UI_ORG}", {"name": f"{name}-task", "project_id": project["id"], "segment_size": frames}
    )
    upload_images(owner, task["id"], UI_ORG, frames, chunk_size=chunk_size)
    for _ in range(120):
        jobs = owner.request("GET", f"/api/jobs?org={UI_ORG}&task_id={task['id']}")["results"]
        if jobs:
            break
        time.sleep(2)
    else:
        raise SystemExit(f"task {task['id']}: no job within 4 minutes")
    job = jobs[0]
    labels = owner.request("GET", f"/api/labels?project_id={project['id']}")["results"]
    return {
        "project_id": project["id"],
        "task_id": task["id"],
        "job_id": job["id"],
        "stop_frame": job["stop_frame"],
        "labels": [label["name"] for label in labels],
    }


def technical_project() -> None:
    owner = Session("ta-owner-c")
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    made = new_job(owner, f"ta-bot-only-{stamp}", 1)
    project, job = made["project_id"], made["job_id"]
    bot = Session(TECHNICAL_ACCOUNT)
    labels = bot.request("GET", f"/api/labels?job_id={job}&org={UI_ORG}")["results"]
    shapes = [
        {
            "type": "rectangle",
            "frame": 0,
            "label_id": labels[0]["id"],
            "points": [1, 1, 3 + i, 3 + i],
            "occluded": False,
            "z_order": 0,
            "attributes": [],
        }
        for i in range(BOT_BOXES)
    ]
    bot.request(
        "PATCH",
        f"/api/jobs/{job}/annotations?action=create&org={UI_ORG}",
        {"shapes": shapes, "tracks": [], "tags": [], "version": 0},
    )
    rows = wait_rows(
        f"SELECT user_name, scope FROM events WHERE project_id = {int(project)}",
        lambda r: any(x["scope"] == "create:shapes" for x in r),
        "the technical account's saved boxes",
    )
    people = sorted({r["user_name"] for r in rows if r["user_name"] != TECHNICAL_ACCOUNT})
    log(f"project {project}: {TECHNICAL_ACCOUNT} saved {BOT_BOXES} boxes; events by anyone else: {people or 'none'}")
    check(not people, f"project {project} holds events of {people}; it must hold only the technical account's work")

    query = {"org": UI_ORG, "period": "week", "by": "projects", "ids": project}

    def ready(body: dict) -> bool:
        return bool(body["processed"]) and any(r["id"] == project and r["saved_boxes"] > 0 for r in body["rows"])

    body = wait_figures(owner, "details", {**query, "shapes": "all"}, ready, f"details row of project {project}",
                        REFRESH_S * 5 + 120)
    for shapes in ("all", "bounding_boxes"):
        if shapes != "all":
            body = ok(owner, "details", **query, shapes=shapes)
        row = by_key(body["rows"], "id").get(project)
        check(row is not None, f"details by project ({shapes}): no row for project {project}: {body['rows']}")
        want = {"working_time_ms": 0, "sessions": 0, "saved_boxes": BOT_BOXES, "model": BOT_BOXES, "annotators": 0}
        got = {key: row[key] for key in want}
        check(got == want, f"details row of project {project} ({shapes}) {got}, expected {want}")
        log(f"details by project ({shapes}): project {project} {got}")
    people = ok(owner, "details", org=UI_ORG, period="week", by="annotators")
    names = [r["user_name"] for r in people["rows"]]
    check(TECHNICAL_ACCOUNT not in names, f"the technical account is listed by annotator: {names}")
    log(f"details by annotator: {TECHNICAL_ACCOUNT} not listed")


# ---------------------------------------------------------------- gestures in the browser


def prepare_gestures() -> None:
    owner = Session("ta-owner-c")
    worker_id = Session("ta-worker-c").request("GET", "/api/users/self")["id"]
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    made = new_job(owner, f"ta-gestures-{stamp}", FRAMES, chunk_size=1)
    owner.request("PATCH", f"/api/jobs/{made['job_id']}?org={UI_ORG}", {"assignee": worker_id})
    print(json.dumps({"org": UI_ORG, "worker": "ta-worker-c", "worker_id": worker_id, "job": made}))


def job_events(project: int) -> list[dict]:
    return clickhouse(
        "SELECT scope, obj_name, source, user_name, toString(count) AS count, toString(obj_id) AS obj_id, payload,"
        f" toString(timestamp) AS ts FROM events WHERE project_id = {int(project)} ORDER BY timestamp"
    )


def drags(rows: list[dict]) -> list[tuple[dict, dict]]:
    return [(r, payload(r)) for r in rows if r["scope"] == "drag:object" and r["source"] == "client"]


def check_gestures(state_file: str) -> None:
    state = json.loads(Path(state_file).read_text())
    job, did = state["job"], state["did"]
    project = job["project_id"]
    rejected = [p for p in did["event_posts"] if p["status"] != 201]
    check(did["event_posts"] and not rejected, f"POST /api/events not answered 201: {rejected or 'none sent'}")
    log(f"{len(did['event_posts'])} POST /api/events, all 201 (a group drag:object carries count)")

    # every record the browser made, the closing input summary last
    wait_rows(
        f"SELECT count() AS n FROM events WHERE project_id = {int(project)}"
        " AND obj_name = 'team_analytics:input_summary'",
        lambda r: int(r[0]["n"]) > 0,
        "the closing input summary",
        timeout_s=180,
    )
    rows = job_events(project)

    # redo: one undo and one redo of the drawn box, no second creation
    undo = [r for r in rows if r["scope"] == "action:undo"]
    redo = [r for r in rows if r["scope"] == "action:redo"]
    draws = [r for r in rows if r["scope"] == "draw:object"]
    check(len(undo) == 1 and len(redo) == 1, f"undo {len(undo)}, redo {len(redo)} records, expected one each")
    check(len(draws) == did["drawn"], f"{len(draws)} draw:object records, {did['drawn']} drawn")
    log(f"redo: action:undo {payload(undo[0])}, action:redo {payload(redo[0])}; {len(draws)} draw:object")

    # group drags: one group record per gesture; CVAT's own drag of the grabbed box marked; a later drag plain
    seen = drags(rows)
    moves = [(r, p) for r, p in seen if p.get("group") == "move"]
    grabbed = [(r, p) for r, p in seen if p.get("group") == "grabbed"]
    plain = [(r, p) for r, p in seen if "group" not in p]
    log("drag:object records: " + "; ".join(
        f"{p.get('group', 'plain')} count {r['count']} obj_id {r.get('obj_id')} "
        f"{ {k: p[k] for k in sorted(p) if k not in ('client_id', 'is_active')} }"
        for r, p in seen
    ))
    check(len(moves) == 2, f"{len(moves)} group records, expected 2 (the grabbed box's drag, the selection box)")
    for r, p in moves:
        check(
            int(r["count"]) == 2 and p.get("rectangle_count") == 2 and p.get("shape_type") == "rectangle"
            and p.get("object_type") == "shape" and p.get("input_method") == "mouse" and "frame" in p
            and "object_ref" not in p and r.get("obj_id") is None,
            f"group record count {r['count']} obj_id {r.get('obj_id')} payload {p}",
        )
    check(len(grabbed) == 1, f"{len(grabbed)} drags marked grabbed, expected 1")
    g, gp = grabbed[0]
    check("object_ref" in gp and g.get("obj_id") is not None, f"grabbed drag obj_id {g.get('obj_id')} payload {gp}")
    check(len(plain) == 1 and "object_ref" in plain[0][1], f"plain drags {[p for _, p in plain]}, expected 1")
    check(plain[0][0]["ts"] > max(r["ts"] for r, _ in moves), "the plain drag is not the last drag")

    # held frame key: one NEXT_FRAME per frame shown, none for the press at the last frame or the slider
    hold = did["hold"]
    summaries = [r for r in rows if r["obj_name"] == "team_analytics:input_summary"]
    hotkeys: dict[str, int] = {}
    for r in summaries:
        for name, n in (payload(r).get("hotkeys") or {}).items():
            hotkeys[name] = hotkeys.get(name, 0) + n
    frames = [(int(r["count"]), payload(r)) for r in rows if r["scope"] == "change:frame"]
    stepped = sum(n for n, p in frames if p.get("step") == 1)
    log(
        f"held F: {hold['keydowns']} key-down events ({hold['keydowns'] - 1} repeats) over {hold['held_ms']} ms with "
        f"{hold['latency_ms']} ms latency; frames shown {hold['frames']} ({hold['moves']} changes, "
        f"{hold['back_jumps']} back); at the last frame F moved {did['last_frame']['moved']}; the slider "
        f"{did['slider']['from']} -> {did['slider']['to']}"
    )
    log(f"summaries x{len(summaries)}: hotkeys {hotkeys}; change:frame (count, from, to, step): "
        + str([(n, p.get("from"), p.get("to"), p.get("step")) for n, p in frames]))
    check(hold["keydowns"] > hold["moves"] > 0,
          f"the frame was not slow: {hold['keydowns']} key-downs moved {hold['moves']} frames")
    check(hotkeys.get("NEXT_FRAME") == hold["moves"],
          f"NEXT_FRAME {hotkeys.get('NEXT_FRAME')} for {hold['moves']} frames shown by the held key")
    if hold["back_jumps"] == 0:
        check(stepped == hold["moves"], f"CVAT's change:frame shows {stepped} single steps, the page {hold['moves']}")
    check(not did["last_frame"]["moved"] and did["slider"]["to"] < did["slider"]["from"],
          f"last frame {did['last_frame']}, slider {did['slider']}")
    check(hotkeys == did["hotkeys"], f"hotkeys in the summaries {hotkeys}, made {did['hotkeys']}")

    # the figures: one creation for draw, undo, redo; one alignment per object moved, plus the plain drag
    owner = Session("ta-owner-c")
    query = {"org": UI_ORG, "period": "week", "project": project, "shapes": "all"}
    alignments = sum(int(r["count"]) for r, _ in moves) + len(plain)

    def ready(body: dict) -> bool:
        if not body["processed"]:
            return False
        ops = by_key(body["operations"]["rows"], "operation")
        return ops["alignment"]["objects"] >= alignments and body["input"]["hotkey_actions"] >= sum(hotkeys.values())

    wait_figures(owner, "overview", query, ready, f"figures of project {project}", REFRESH_S * 5 + 120)
    time.sleep(REFRESH_S + 15)  # one more scheduled refresh, so that nothing is still on its way
    body = ok(owner, "overview", **query)
    ops = by_key(body["operations"]["rows"], "operation")
    methods = by_key(body["creation_methods"]["rows"], "method")
    got = {
        "creation": ops["creation"]["objects"],
        "drawn": methods["drawn"]["objects"],
        "deletion": ops["deletion"]["objects"],
        "alignment": ops["alignment"]["objects"],
        "hotkey_actions": body["input"]["hotkey_actions"],
    }
    want = {
        "creation": did["drawn"],
        "drawn": did["drawn"],
        "deletion": 0,
        "alignment": alignments,
        "hotkey_actions": sum(did["hotkeys"].values()),
    }
    check(got == want, f"figures of project {project} {got}, expected {want}")
    log(f"figures of project {project}: {got} (draw, undo, redo is one creation; a group of 2 is 2 alignments)")


# ---------------------------------------------------------------- a period not fully processed


def lease_holder() -> str | None:
    rows = clickhouse(control_sql("lock_holder.sql", now=None))
    return rows[0]["token"] if rows else None


def hold_lease(token: str, holder: str) -> float:
    """Claims the refresh lease as another replica would, retrying while a replica holds it; when it is held."""
    for _ in range(60):
        clickhouse(control_sql("lock_claim.sql", token=token, holder=holder, ttl_s=LEASE_S, now=None))
        if lease_holder() == token:
            return time.monotonic()
        clickhouse(control_sql("lock_release.sql", token=token, holder=holder, now=None))
        time.sleep(5)
    raise SystemExit("the refresh lease stayed taken for five minutes")


def withheld(endpoint: str, body: dict) -> list[str]:
    """The fields of an answer for a period not fully processed that carry a figure (should be none)."""
    wrong = [k for k, v in body.items() if k not in ENVELOPES[endpoint] and v is not None]
    if endpoint == "overview":
        wrong += [f"operations.{k}" for k, v in (body.get("operations") or {}).items()
                  if k not in LEGACY_FLAGS and v is not None]
    return wrong


def bucket_of(day: date, buckets: list[dict]) -> int:
    starts = [date.fromisoformat(b["start"][:10]) for b in buckets]
    inside = [i for i, start in enumerate(starts) if start <= day and (i + 1 == len(starts) or day < starts[i + 1])]
    return inside[0] if inside else -1


def unprocessed() -> None:
    admin, maintainer = Session("ta-admin"), Session("ta-maintainer")
    callers = [(maintainer, "ta-org-a"), (admin, "")]
    wait_figures(admin, "status", {}, lambda b: (b.get("history") or {}).get("complete"), "history complete", 900)
    first = date.fromisoformat(clickhouse("SELECT toString(toDate(min(timestamp))) AS d FROM events")[0]["d"])
    probe_day = first - timedelta(days=PROBE_DAYS_BEFORE)
    today = datetime.now(UTC).date()
    check((today - probe_day).days < 330, f"the first event day {first} lies too far back for a probe in the year")
    token = f"ta-stack-probe-{uuid.uuid4().hex[:12]}"
    held_at = hold_lease(token, "run.sh check-fixes unprocessed")
    log(f"holding the refresh lease ({LEASE_S} s); marker event on {probe_day}, {PROBE_DAYS_BEFORE} days before "
        f"the first recorded day {first}")
    try:
        clickhouse(
            "INSERT INTO events FORMAT JSONEachRow",
            json.dumps({"scope": "debug:info", "obj_name": PROBE, "source": "client", "count": 1, "duration": 0,
                        "timestamp": f"{probe_day} 12:00:00.000", "payload": "{}"}) + "\n",
        )
        for session, org in callers:
            who = f"{session.username}, org={org or '-'}"
            st = status_of(session, org)["history"]
            check(st["complete"] is False and st["periods"]["year"] is False and st["periods"]["week"] is True,
                  f"{who} status while the probe days wait: {st}")
            for endpoint, extra in (("overview", {}), ("list", {"by": "annotators"}),
                                    ("details", {"by": "annotators"}), ("details", {"by": "projects"})):
                body = ok(session, endpoint, org=org, period="year", **extra)
                check(body["processed"] is False, f"{who} {endpoint} {extra} year: processed {body['processed']}")
                wrong = withheld(endpoint, body)
                check(not wrong, f"{who} {endpoint} {extra} year carries figures in {wrong}")
                kept = sorted(k for k, v in body.items() if v is not None)
                log(f"{who}: {endpoint} {extra or ''} for the year: processed false, non-null only {kept}")
            week = ok(session, "overview", org=org, period="week")
            check(week["processed"] is True and week["by_annotator"] is not None, f"{who} week overview {week}")
            for step in ("week", "month"):
                trends = ok(session, "trends", org=org, step=step)
                i = bucket_of(probe_day, trends["buckets"])
                if i < 0:
                    log(f"{who}: trends by {step}: no bucket holds {probe_day}")
                    continue
                check(trends["buckets"][i]["processed"] is False, f"{who} trends {step} bucket {trends['buckets'][i]}")
                points = [line["points"][i] for line in trends["lines"]]
                wrong = [k for p in points for k, v in p.items() if k not in TREND_POINT_FLAGS and v is not None]
                check(not wrong, f"{who} trends {step}: the unprocessed bucket carries {wrong}")
                log(f"{who}: trends by {step}: bucket {trends['buckets'][i]['start'][:10]} not processed, values null")
            check(time.monotonic() - held_at < LEASE_S - 15, "the reads outlasted the probe's lease")
    finally:
        clickhouse(control_sql("lock_release.sql", token=token, holder="run.sh check-fixes unprocessed", now=None))
        log(f"released the lease after {time.monotonic() - held_at:.0f} s")
    try:
        wait_figures(admin, "status", {}, lambda b: (b.get("history") or {}).get("complete"),
                     "the probe days processed", 600)
        for session, org in callers:
            body = ok(session, "overview", org=org, period="year")
            check(body["processed"] is True and body["by_annotator"] is not None, f"year after processing {body}")
            log(f"{session.username}, org={org or '-'}: year processed, {len(body['by_annotator']['rows'])} rows")
    finally:
        clickhouse(f"ALTER TABLE events DELETE WHERE obj_name = '{PROBE}' SETTINGS mutations_sync = 2")
        left = clickhouse(f"SELECT count() AS n FROM events WHERE obj_name = '{PROBE}'")[0]["n"]
        check(int(left) == 0, f"{left} marker events left")
        log("marker event deleted; the probe days stay recorded as processed, before the first event")


# ---------------------------------------------------------------- sessions at the one-day limit


def sessions_at_limit() -> None:
    """A refresh reads back one day before the hours it computes and cuts a session there (refresh/sessions.sql),
    so every cut session spans more than a day less the session gap. Counted over the instance-wide set (one
    session per person, across organizations), in each hour's newest version."""
    row = clickhouse(
        "SELECT count() AS sessions,"
        f" countIf(dateDiff('millisecond', start_at, end_at) >= {DAY_MS - SESSION_GAP_MS}) AS at_limit,"
        " toString(max(dateDiff('millisecond', start_at, end_at))) AS longest_ms,"
        " toString(min(start_at)) AS first_start, toString(max(end_at)) AS last_end"
        f" FROM {TOTALS}.session_intervals"
        " WHERE instance_wide = 1"
        f" AND (hour, version) IN (SELECT hour, max(version) FROM {TOTALS}.hour_versions GROUP BY hour)"
    )[0]
    log(
        f"sessions stored (instance-wide set): {row['sessions']}; spanning a day less the session gap or more "
        f"(every session cut at the one-day read-back is among them): {row['at_limit']}; longest "
        f"{int(row['longest_ms'] or 0) / 3_600_000:.2f} h; from {row['first_start']} to {row['last_end']}"
    )


# ---------------------------------------------------------------- the cutover after a restart


def cutover_restart() -> None:
    admin, maintainer = Session("ta-admin"), Session("ta-maintainer")
    first = clickhouse(
        f"SELECT toString(toStartOfHour(toDateTime(min(timestamp), 'Etc/UTC'))) AS at, count() AS n FROM events"
        f" WHERE {TAGGED}"
    )[0]
    check(int(first["n"]) > 0, "the stack holds no shape-tagged work")
    expected = datetime.strptime(first["at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    before = status_of(admin)["cutover"]["at"]
    log(f"tagged operation events: {first['n']}, the first in hour {expected.isoformat()}; status before: {before}")
    try:
        kubectl("scale", "deploy/team-analytics", "--replicas=0")
        kubectl("wait", "--for=delete", "pod", "-l", "app.kubernetes.io/name=team-analytics", "--timeout=5m")
        clickhouse(f"TRUNCATE TABLE {TOTALS}.cutover")
        clickhouse(f"DROP TABLE IF EXISTS {TOTALS}.history_today")
        stored = clickhouse(f"SELECT count() AS n FROM {TOTALS}.cutover")[0]["n"]
        gone = clickhouse(f"EXISTS TABLE {TOTALS}.history_today")
        log(f"service stopped; cutover rows {stored}; history_today exists: {gone}")
        kubectl("scale", "deploy/team-analytics", "--replicas=1")
        started = time.monotonic()
        first_answers = {}
        while len(first_answers) < 2:
            check(time.monotonic() - started < 600, "the restarted service did not answer status within 10 minutes")
            for session, org in ((admin, ""), (maintainer, "ta-org-a")):
                if session.username in first_answers:
                    continue
                status, body = service(session, "status", org=org)
                if status == 200:
                    first_answers[session.username] = (round(time.monotonic() - started), body["cutover"])
            time.sleep(0.5)
    finally:
        kubectl("scale", "deploy/team-analytics", "--replicas=1")
    for username, (after_s, cutover) in first_answers.items():
        at = cutover and cutover.get("at")
        check(at is not None and datetime.fromisoformat(at) == expected,
              f"{username}'s first status after the restart: cutover {cutover}, expected {expected.isoformat()}")
        log(f"{username}: first status {after_s} s after the restart carries cutover {at}")
    exists = clickhouse(f"EXISTS TABLE {TOTALS}.history_today")
    check(exists and int(next(iter(exists[0].values()))) == 1, f"history_today after the restart: {exists}")
    kubectl("rollout", "status", "deploy/team-analytics", "--timeout=10m")
    restarts = kubectl("get", "pods", "-l", "app.kubernetes.io/name=team-analytics", "-o",
                       "jsonpath={range .items[*]}{.metadata.name} {.status.containerStatuses[0].restartCount}{'\\n'}{end}",
                       capture=True).strip()
    log(f"history_today created again at start; pod restarts during the start-up search: {restarts}")


def main() -> None:
    args = sys.argv[1:]
    steps = {
        "status-roles": status_roles,
        "technical-project": technical_project,
        "prepare-gestures": prepare_gestures,
        "unprocessed": unprocessed,
        "sessions-at-limit": sessions_at_limit,
        "cutover-restart": cutover_restart,
    }
    if len(args) == 1 and args[0] in steps:
        steps[args[0]]()
    elif len(args) == 2 and args[0] == "check-gestures":
        check_gestures(args[1])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
