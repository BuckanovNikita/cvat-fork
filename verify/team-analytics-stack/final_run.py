"""Final run of Team Analytics on the test stack (ticket 18), driven by run.sh check-final.

    final_run.py prepare-ui                 a new project, task and job in ta-org-c for the browser
                                            to annotate (prints JSON for ui_actions.cjs)
    final_run.py check-ui-records FILE      after ui_actions.cjs: the records the real UI sent are in
                                            the events table; the detector record goes through the API;
                                            the technical account saves boxes; working time behaves
    final_run.py check-ui-figures FILE      the service's figures for that project
    final_run.py load-volume                synthetic events in ta-org-v: 100 annotators, 40 projects
                                            with long names, ten weeks of history (once per stack)
    final_run.py check-volume SECS          the service's figures for the loaded events
    final_run.py check-access               every account and organization against every endpoint
    final_run.py page-context FILE          JSON for final_browser.cjs page (organizations, this run's
                                            project and what the browser did there)

FILE is the JSON that prepare-ui printed, extended by ui_actions.cjs with what the browser did.
Environment: TA_BASE_URL, TA_SEED_PASSWORD, TA_KUBE_CONTEXT, TA_NAMESPACE, TA_RELEASE. Standard
library only; ClickHouse is read with clickhouse-client in its pod.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run with python3 -I, which leaves it out

from stack_api import Session, check, get_json, upload_images

API = "/team-analytics-api/v1/"
UI_ORG = "ta-org-c"
VOLUME_ORG = "ta-org-v"
TECHNICAL_ACCOUNT = "ta-bot"  # run.sh sets TEAM_ANALYTICS_TECHNICAL_ACCOUNTS to it
UI_IMAGES = 4
BOT_BOXES = 3
DETECTOR = {"rectangles": 2, "objects": 3}


def log(message: str) -> None:
    print(f"  {message}", flush=True)


# ---------------------------------------------------------------- ClickHouse


def clickhouse(query: str, data: str | None = None) -> list[dict]:
    """Runs a query with clickhouse-client in the stack's ClickHouse pod; JSONEachRow rows."""
    release = os.environ.get("TA_RELEASE", "cvat")
    # clickhouse-client writes into its working directory; / is not writable in the pod
    client = (
        'cd /tmp && clickhouse-client --user "$CLICKHOUSE_USER" --password "$CLICKHOUSE_PASSWORD" '
        '--database "$CLICKHOUSE_DB" --format JSONEachRow --query "$0"'
    )
    command = [
        "kubectl",
        "--context",
        os.environ["TA_KUBE_CONTEXT"],
        "-n",
        os.environ["TA_NAMESPACE"],
        "exec",
        "-i",
        f"{release}-clickhouse-shard0-0",
        "-c",
        "clickhouse",
        "--",
        "sh",
        "-c",
        client,
        query,
    ]
    out = subprocess.run(command, input=data, capture_output=True, text=True, check=False)
    if out.returncode:
        raise SystemExit(f"clickhouse query failed: {out.stderr.strip()[:500]}")
    return [json.loads(line) for line in out.stdout.splitlines() if line.strip()]


def wait_rows(query: str, ready, what: str, timeout_s: int = 120) -> list[dict]:
    started = time.monotonic()
    while True:
        rows = clickhouse(query)
        if ready(rows):
            return rows
        if time.monotonic() - started > timeout_s:
            raise SystemExit(f"{what}: not in the events table after {timeout_s} s; last rows {rows[:5]}")
        time.sleep(3)


# ---------------------------------------------------------------- service


def service(session: Session, path: str, **query) -> tuple[int, object]:
    return session.call(API + path + "?" + urllib.parse.urlencode({"tz": "UTC", **query}))


def ok(session: Session, path: str, **query) -> dict:
    status, body = service(session, path, **query)
    check(status == 200, f"{session.username} {path} {query}: {status} {body}")
    return body


def org_id(session: Session, slug: str) -> int:
    return session.request("GET", f"/api/organizations?slug={slug}")["results"][0]["id"]


def wait_figures(session: Session, path: str, query: dict, ready, what: str, timeout_s: int) -> dict:
    """Polls the service until `ready(body)`; the scheduled refresh brings new events within minutes."""
    started = time.monotonic()
    while True:
        status, body = service(session, path, **query)
        if status == 200 and ready(body):
            log(f"{what}: ready after {time.monotonic() - started:.0f} s")
            return body
        if time.monotonic() - started > timeout_s:
            raise SystemExit(f"{what}: not ready after {timeout_s} s: {status} {json.dumps(body)[:800]}")
        time.sleep(5)


def by_key(rows: list[dict], key: str) -> dict:
    return {row[key]: row for row in rows}


# ---------------------------------------------------------------- real UI (ta-org-c)


def prepare_ui() -> None:
    """Two projects created for this run: one the browser annotates with the service up, one it
    annotates with the service stopped. Each run makes its own, so figures are read per project."""
    owner = Session("ta-owner-c")
    worker_id = Session("ta-worker-c").request("GET", "/api/users/self")["id"]
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    made = {}
    for role in ("ui", "down"):
        project = owner.request(
            "POST",
            f"/api/projects?org={UI_ORG}",
            {
                "name": f"ta-{role}-{stamp}",
                "labels": [{"name": "box", "color": "#ff4136"}, {"name": "other", "color": "#1890ff"}],
            },
        )
        task = owner.request(
            "POST",
            f"/api/tasks?org={UI_ORG}",
            {"name": f"ta-{role}-task-{stamp}", "project_id": project["id"], "segment_size": UI_IMAGES},
        )
        upload_images(owner, task["id"], UI_ORG, UI_IMAGES)
        for _ in range(120):
            jobs = owner.request("GET", f"/api/jobs?org={UI_ORG}&task_id={task['id']}")["results"]
            if jobs:
                break
            time.sleep(2)
        else:
            raise SystemExit(f"task {task['id']}: no job within 4 minutes")
        job = jobs[0]
        owner.request("PATCH", f"/api/jobs/{job['id']}?org={UI_ORG}", {"assignee": worker_id})
        made[role] = {
            "project_id": project["id"],
            "task_id": task["id"],
            "job_id": job["id"],
            "labels": [
                label["name"] for label in owner.request("GET", f"/api/labels?project_id={project['id']}")["results"]
            ],
        }
    print(json.dumps({"org": UI_ORG, "worker": "ta-worker-c", "worker_id": worker_id, **made}))


def events_of(project_id: int) -> list[dict]:
    return clickhouse(
        "SELECT scope, obj_name, source, user_name, toString(count) AS count, job_id, payload,"
        " toString(timestamp) AS ts FROM events WHERE project_id = " + str(int(project_id)) + " ORDER BY timestamp"
    )


def payload(row: dict) -> dict:
    try:
        return json.loads(row["payload"] or "{}")
    except ValueError:
        return {}


def check_ui_records(state_file: str) -> None:
    state = json.loads(Path(state_file).read_text())
    ui, did = state["ui"], state["did"]
    project, job = ui["project_id"], ui["job_id"]
    worker = Session("ta-worker-c")

    # every POST /api/events the real UI made was accepted
    rejected = [r for r in did["event_posts"] if r["status"] != 201]
    check(did["event_posts"] and not rejected, f"event POSTs not accepted: {rejected or 'none sent'}")
    log(f"real UI: {len(did['event_posts'])} POST /api/events, all 201")

    def client(scope: str, name: str | None = None):
        return lambda rows: [
            r
            for r in rows
            if r["scope"] == scope and r["source"] == "client" and (name is None or r["obj_name"] == name)
        ]

    def ready(rows: list[dict]) -> bool:
        return bool(client("debug:info", "team_analytics:input_summary")(rows))

    rows = wait_rows(
        "SELECT scope, obj_name, source FROM events WHERE project_id = " + str(int(project)),
        lambda found: ready([{**r, "scope": r["scope"]} for r in found]),
        "the input summary of the real UI",
    )
    rows = events_of(project)

    def tagged(row: dict) -> dict:
        p = payload(row)
        return {
            k: p.get(k)
            for k in ("shape_type", "rectangle_count", "object_type", "input_method", "object_ref", "frame")
            if k in p
        }

    draws = client("draw:object")(rows)
    check(len(draws) == did["drawn"], f"draw:object rows {len(draws)}, the browser drew {did['drawn']}")
    check(
        all(
            tagged(r).get("shape_type") == "rectangle"
            and tagged(r).get("object_type") == "shape"
            and tagged(r).get("rectangle_count") == 1
            for r in draws
        ),
        f"draw payloads {[tagged(r) for r in draws]}",
    )
    methods = sorted(tagged(r).get("input_method") for r in draws)
    check(methods == sorted(did["draw_methods"]), f"draw input methods {methods}, expected {did['draw_methods']}")
    log(f"draw:object x{len(draws)}: {[tagged(r) for r in draws]}")

    drags = client("drag:object")(rows)
    check(len(drags) == did["dragged"], f"drag:object rows {len(drags)}, the browser dragged {did['dragged']}")
    check(
        all(
            isinstance(tagged(r).get("object_ref"), int)
            and isinstance(tagged(r).get("frame"), int)
            and tagged(r).get("input_method") == "mouse"
            for r in drags
        ),
        f"drag payloads {[tagged(r) for r in drags]}",
    )
    log(f"drag:object x{len(drags)}: {[tagged(r) for r in drags]}")

    for scope, key in (
        ("paste:object", "pasted"),
        ("propagate:object", "propagated_events"),
        ("delete:object", "deleted"),
    ):
        found = client(scope)(rows)
        check(len(found) == did[key], f"{scope} rows {len(found)}, expected {did[key]}")
        check(
            all(tagged(r).get("shape_type") == "rectangle" and "input_method" in tagged(r) for r in found),
            f"{scope} payloads {[tagged(r) for r in found]}",
        )
        log(f"{scope} x{len(found)}: {[(r['count'], tagged(r)) for r in found]}")
    propagated = sum(int(r["count"]) for r in client("propagate:object")(rows))
    check(propagated == did["propagated"], f"propagate:object count {propagated}, expected {did['propagated']}")

    changes = client("debug:info", "team_analytics:class_change")(rows)
    check(
        len(changes) == len(did["class_changes"]),
        f"class change records {len(changes)}, expected {did['class_changes']}",
    )
    got = sorted((int(r["count"]), tagged(r).get("input_method")) for r in changes)
    want = sorted((c["count"], c["input_method"]) for c in did["class_changes"])
    check(got == want, f"class change records {got}, expected {want}")
    log(f"team_analytics:class_change: {[(r['count'], tagged(r)) for r in changes]}")

    summaries = client("debug:info", "team_analytics:input_summary")(rows)
    hotkeys: dict[str, int] = defaultdict(int)
    mouse: dict[str, int] = defaultdict(int)
    for r in summaries:
        for name, n in (payload(r).get("hotkeys") or {}).items():
            hotkeys[name] += n
        for name, n in (payload(r).get("mouse") or {}).items():
            mouse[name] += n
    for action, n in did["hotkeys"].items():
        check(hotkeys.get(action) == n, f"hotkey {action}: summary {hotkeys.get(action)}, pressed {n}")
    check(mouse.get("canvas", 0) > 0, f"no canvas clicks in the summaries: {dict(mouse)}")
    log(f"team_analytics:input_summary x{len(summaries)}: hotkeys {dict(hotkeys)}, mouse {dict(mouse)}")

    # detector use: no model function is deployed (nuclio is off), so the record the UI module
    # produces is sent through the real API with the class change record's own shape
    template = changes[0]
    now = datetime.now(UTC)
    body = payload(template)
    for key in ("shape_type", "object_type", "input_method"):
        body.pop(key, None)
    body["rectangle_count"] = DETECTOR["rectangles"]
    event = {
        "scope": "debug:info",
        "obj_name": "team_analytics:model_creation",
        "count": DETECTOR["objects"],
        "timestamp": now.isoformat(),
        "payload": json.dumps(body),
        "project_id": project,
        "task_id": ui["task_id"],
        "job_id": job,
    }
    worker.request("POST", f"/api/events?org={UI_ORG}", {"events": [event], "timestamp": now.isoformat()})
    found = wait_rows(
        "SELECT user_name, toString(count) AS count, payload FROM events WHERE project_id = "
        + str(int(project))
        + " AND obj_name = 'team_analytics:model_creation'",
        bool,
        "the detector record",
    )
    check(
        found[0]["user_name"] == "ta-worker-c"
        and int(found[0]["count"]) == DETECTOR["objects"]
        and payload(found[0]).get("rectangle_count") == DETECTOR["rectangles"],
        f"detector record {found}",
    )
    log(
        f"team_analytics:model_creation (sent through the API, see evidence): {found[0]['count']} objects, "
        f"payload {payload(found[0])}"
    )

    # the technical account uploads boxes the way a script would
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
    wait_rows(
        "SELECT count() AS n FROM events WHERE project_id = "
        + str(int(project))
        + " AND scope = 'create:shapes' AND user_name = 'ta-bot'",
        lambda r: int(r[0]["n"]) > 0,
        "the technical account's saved boxes",
    )
    log(f"{TECHNICAL_ACCOUNT}: saved {BOT_BOXES} boxes through the API")

    # event logging and working time as before: CVAT still turns the client events into working time
    rows = events_of(project)
    working = [r for r in rows if r["scope"] == "send:working_time" and r["user_name"] == "ta-worker-c"]
    total = sum(payload(r).get("working_time", 0) for r in working)
    check(working and total > 0, f"no working time recorded for the real UI session: {working}")
    stock = sorted({r["scope"] for r in rows if r["source"] == "client"})
    for scope in (
        "load:job",
        "draw:object",
        "drag:object",
        "paste:object",
        "propagate:object",
        "delete:object",
        "copy:object",
        "change:frame",
        "save:job",
    ):
        check(scope in stock, f"stock client event {scope} missing: {stock}")
    with_client_id = [r for r in rows if r["source"] == "client" and "client_id" in payload(r)]
    check(
        len(with_client_id) == len([r for r in rows if r["source"] == "client"]),
        "a client event lost its client_id (the logger's browser id)",
    )
    saved = [r for r in rows if r["scope"] == "create:shapes" and r["user_name"] == "ta-worker-c"]
    check(saved, "the job save wrote no create:shapes event")
    log(
        f"working time: {len(working)} send:working_time rows, {total} ms; client scopes {stock}; "
        f"create:shapes by ta-worker-c {sum(int(r['count']) for r in saved)}"
    )


def check_ui_figures(state_file: str, timeout_s: int) -> None:
    state = json.loads(Path(state_file).read_text())
    ui, did = state["ui"], state["did"]
    project = ui["project_id"]
    owner = Session("ta-owner-c")
    rows = events_of(project)
    working_ms = sum(
        payload(r).get("working_time", 0)
        for r in rows
        if r["scope"] == "send:working_time" and r["user_name"] == "ta-worker-c"
    )
    hotkeys = sum(
        sum((payload(r).get("hotkeys") or {}).values()) for r in rows if r["obj_name"] == "team_analytics:input_summary"
    )
    saved_by_worker = did["boxes_in_job_after_save"]
    query = {"org": UI_ORG, "period": "week", "project": project, "shapes": "all"}

    def ready(body: dict) -> bool:
        # a period that is not fully processed carries no figures (rows and counts are null)
        if not body["processed"]:
            return False
        ops = by_key(body["operations"]["rows"], "operation")
        return (
            body["creation_methods"]["model"]["objects"] == BOT_BOXES + DETECTOR["objects"]
            and ops["deletion"]["objects"] == did["deleted_objects"]
            and body["saved_boxes"]["boxes"] == saved_by_worker + BOT_BOXES
            and sum(r["working_time_ms"] for r in body["by_annotator"]["rows"]) == working_ms
        )

    body = wait_figures(owner, "overview", query, ready, f"figures of project {project}", timeout_s)
    ops = by_key(body["operations"]["rows"], "operation")
    methods = by_key(body["creation_methods"]["rows"], "method")
    expected_methods = {"drawn": did["drawn"], "pasted": did["pasted_objects"], "propagated": did["propagated"]}
    check(
        {m: methods[m]["objects"] for m in expected_methods} == expected_methods,
        f"creation methods {methods}, expected {expected_methods}",
    )
    check(ops["creation"]["objects"] == sum(expected_methods.values()), f"creation {ops['creation']}")
    check(
        ops["alignment"]["objects"] == did["alignments"], f"alignment {ops['alignment']}, expected {did['alignments']}"
    )
    check(
        ops["class_change"]["objects"] == sum(c["count"] for c in did["class_changes"]),
        f"class change {ops['class_change']}",
    )
    check(ops["deletion"]["objects"] == did["deleted_objects"], f"deletion {ops['deletion']}")
    shares = sum(r["share"] or 0 for r in body["operations"]["rows"])
    check(abs(shares - 1) < 1e-6, f"shares add up to {shares}")
    log(
        f"operations: { {k: v['objects'] for k, v in ops.items()} }, methods {expected_methods}, "
        f"model {body['creation_methods']['model']}"
    )

    check(
        body["sessions"]["sessions"] == 1 and body["sessions"]["by_annotator"][0]["user_name"] == "ta-worker-c",
        f"sessions {body['sessions']}",
    )
    check(body["headline"] == {"annotators": 1, "projects": 1}, f"headline {body['headline']}")
    # the by-project list keeps every project of the scope (its own filter does not apply to it)
    # (each row also carries its operation parts)
    check(
        any(r["project_id"] == project and r["working_time_ms"] == working_ms for r in body["by_project"]["rows"]),
        f"by project {body['by_project']}",
    )
    check(body["saved_boxes"]["by_annotator"][0]["boxes"] == saved_by_worker, f"saved boxes {body['saved_boxes']}")
    check(body["input"]["hotkey_actions"] == hotkeys, f"hotkey actions {body['input']}, summaries {hotkeys}")
    top = {r["action"]: r["actions"] for r in body["input"]["top_hotkeys"]}
    check(
        len(top) == min(7, len(did["hotkeys"])) and body["input"]["rest"]["count"] == len(did["hotkeys"]) - len(top),
        f"top hotkeys {top}, rest {body['input']['rest']}",
    )
    listed = ok(owner, "list", org=UI_ORG, period="week", project=project, by="hotkeys")
    every = {r["action"]: r["actions"] for r in listed["rows"]}
    check(every == did["hotkeys"], f"hotkeys in the full list {every}, pressed {did['hotkeys']}")
    inputs = {r["operation"]: (r.get("hotkey_objects"), r.get("mouse_objects")) for r in body["operations"]["rows"]}
    log(
        f"sessions {body['sessions']['sessions']} ({body['sessions']['total_ms']} ms), working time {working_ms} ms, "
        f"saved boxes {body['saved_boxes']['boxes']} (ta-worker-c {saved_by_worker}), hotkeys {top}, "
        f"started by hotkey/mouse {inputs}"
    )

    boxes = ok(owner, "overview", **{**query, "shapes": "bounding_boxes"})
    check(
        boxes["creation_methods"]["model"]["objects"] == BOT_BOXES + DETECTOR["rectangles"],
        f"Model under bounding boxes {boxes['creation_methods']['model']}",
    )
    log(f"bounding boxes: model {boxes['creation_methods']['model']['objects']}")

    trends = ok(owner, "trends", org=UI_ORG, project=project, step="week")
    last = trends["lines"][0]["points"][-1]
    check(last["working_time_ms"] == working_ms, f"trends current week {last}, working time {working_ms}")
    log(f"trends: current week {last['working_time_ms']} ms, boxes {last['boxes']}")


# ---------------------------------------------------------------- volume (ta-org-v)

ANNOTATORS = 100
PROJECTS = 40
WEEKS = 10
GAP_S = 30
VOLUME_USER_BASE = 910_000
LONG_USER = "-with-an-exceptionally-long-display-name-for-the-overflow-checks"
LONG_PROJECT = " with a deliberately long name that has to wrap or be cut without overflowing its card"
VOLUME_MARK = "ta-volume-annotator-"


def volume_user(i: int) -> tuple[int, str]:
    return VOLUME_USER_BASE + i, f"{VOLUME_MARK}{i:03d}{LONG_USER}"


def draws_of(i: int, w: int) -> int:
    return 1 + (i + w) % 5


def plan(anchor: date) -> list[dict]:
    """One work session per annotator and week: day = anchor - 1 - 7 w, k draws GAP_S apart."""
    out = []
    for w in range(WEEKS):
        day = anchor - timedelta(days=1 + 7 * w)
        for i in range(1, ANNOTATORS + 1):
            k = draws_of(i, w)
            start = datetime(day.year, day.month, day.day, 8, tzinfo=UTC) + timedelta(minutes=i)
            out.append(
                {
                    "day": day,
                    "i": i,
                    "w": w,
                    "k": k,
                    "start": start,
                    "polygons": 1 if i % 10 == 0 else 0,
                    "hotkeys": {"NEXT_FRAME": 1 + i % 7, "SWITCH_DRAW_MODE_STANDARD_CONTROLS": k},
                    "mouse": {"canvas": 2 * k, "controls_sidebar": 1},
                }
            )
    return out


def volume_rows(anchor: date, org: int, projects: list[int]) -> list[dict]:
    rows = []
    for s in plan(anchor):
        uid, name = volume_user(s["i"])
        pid = projects[s["i"] % PROJECTS]
        ids = {
            "project_id": pid,
            "task_id": 8_000_000 + pid,
            "job_id": 8_100_000 + s["i"],
            "user_id": uid,
            "user_name": name,
            "user_email": f"volume{s['i']}@example.com",
            "org_id": org,
            "org_slug": VOLUME_ORG,
        }

        def row(scope, when, source="client", count=None, obj_name=None, duration=0, body=None, ids=ids):
            text = (
                json.dumps({"client_id": 4242, "is_active": True, **(body or {})})
                if source == "client"
                else json.dumps(body or {}, separators=(",", ":"))
            )
            return {
                "scope": scope,
                "obj_name": obj_name,
                "source": source,
                "count": count,
                "duration": duration,
                "timestamp": when.strftime("%Y-%m-%d %H:%M:%S.000"),
                "payload": text,
                **ids,
            }

        rows.append(row("load:job", s["start"]))
        last = s["start"]
        for j in range(1, s["k"] + 1):
            last = s["start"] + timedelta(seconds=GAP_S * j)
            polygon = j == s["k"] and s["polygons"]
            rows.append(
                row(
                    "draw:object",
                    last,
                    count=1,
                    duration=2000,
                    body={
                        "shape_type": "polygon" if polygon else "rectangle",
                        "rectangle_count": 0 if polygon else 1,
                        "object_type": "shape",
                        "input_method": "hotkey" if j % 2 else "mouse",
                    },
                )
            )
        rows.append(
            row(
                "debug:info",
                last,
                obj_name="team_analytics:input_summary",
                body={"hotkeys": s["hotkeys"], "mouse": s["mouse"]},
            )
        )
        rows.append(
            row(
                "send:working_time",
                last,
                source="server",
                count=1,
                duration=GAP_S * 1000 * s["k"],
                body={"working_time": GAP_S * 1000 * s["k"]},
            )
        )
        rows.append(
            row(
                "create:shapes",
                last + timedelta(seconds=1),
                source="server",
                count=s["k"] - s["polygons"],
                obj_name="rectangle",
                body={"shapes": [{"id": n} for n in range(s["k"] - s["polygons"])]},
            )
        )
    return rows


def volume_projects(owner: Session) -> list[int]:
    found = owner.request("GET", f"/api/projects?org={VOLUME_ORG}&page_size=100")["results"]
    by_name = {p["name"]: p["id"] for p in found}
    ids = []
    for n in range(PROJECTS):
        name = f"Volume project {n:02d}{LONG_PROJECT}"
        if name not in by_name:
            by_name[name] = owner.request("POST", f"/api/projects?org={VOLUME_ORG}", {"name": name, "labels": []})["id"]
        ids.append(by_name[name])
    return ids


def volume_anchor() -> date | None:
    rows = clickhouse(
        f"SELECT toString(max(toDate(timestamp))) AS d, count() AS n FROM events "
        f"WHERE startsWith(user_name, '{VOLUME_MARK}')"
    )
    if not rows or int(rows[0]["n"]) == 0:
        return None
    return date.fromisoformat(rows[0]["d"]) + timedelta(days=1)


def load_volume() -> None:
    owner = Session("ta-owner-v")
    projects = volume_projects(owner)
    anchor = volume_anchor()
    if anchor is not None:
        log(f"volume events already loaded (anchor {anchor}); {len(projects)} projects")
        return
    anchor = datetime.now(UTC).date()
    org = org_id(owner, VOLUME_ORG)
    rows = volume_rows(anchor, org, projects)
    data = "".join(json.dumps(r) + "\n" for r in rows)
    clickhouse("INSERT INTO events FORMAT JSONEachRow", data)
    log(
        f"loaded {len(rows)} synthetic events into ta-org-v (org {org}): {ANNOTATORS} annotators, "
        f"{PROJECTS} projects, {WEEKS} weeks back from {anchor}"
    )


def week_span(today: date) -> tuple[date, date]:
    return today - timedelta(days=6), today


def check_volume(timeout_s: int) -> None:
    owner = Session("ta-owner-v")
    projects = volume_projects(owner)
    anchor = volume_anchor()
    check(anchor is not None, "no volume events loaded")
    today = datetime.now(UTC).date()
    first, last = week_span(today)
    sessions = [s for s in plan(anchor) if first <= s["day"] <= last]
    work = sum(s["k"] * GAP_S * 1000 for s in sessions)
    draws = sum(s["k"] for s in sessions)
    polygons = sum(s["polygons"] for s in sessions)
    hotkeys = sum(sum(s["hotkeys"].values()) for s in sessions)
    canvas = sum(s["mouse"]["canvas"] for s in sessions)
    mouse = sum(s["mouse"]["controls_sidebar"] for s in sessions)
    active = {s["i"] for s in sessions}
    projects_active = {projects[i % PROJECTS] for i in active}

    # history: every older day processed before the trends are read
    wait_figures(
        owner,
        "status",
        {"org": VOLUME_ORG},
        lambda b: (b.get("history") or {}).get("complete"),
        "history processing",
        timeout_s,
    )
    query = {"org": VOLUME_ORG, "period": "week", "shapes": "all"}
    body = wait_figures(
        owner,
        "overview",
        query,
        lambda b: b["processed"] and b["sessions"]["sessions"] == len(sessions),
        "volume figures",
        timeout_s,
    )
    check(
        body["headline"] == {"annotators": len(active), "projects": len(projects_active)},
        f"headline {body['headline']}",
    )
    check(
        len(body["by_annotator"]["rows"]) == 8 and body["by_annotator"]["rest"]["count"] == len(active) - 8,
        f"by annotator rest {body['by_annotator']['rest']}",
    )
    shown = (
        sum(r["working_time_ms"] for r in body["by_annotator"]["rows"])
        + body["by_annotator"]["rest"]["working_time_ms"]
    )
    check(shown == work, f"working time {shown}, expected {work}")
    check(
        len(body["by_project"]["rows"]) == 8 and body["by_project"]["rest"]["count"] == len(projects_active) - 8,
        f"by project rest {body['by_project']['rest']}",
    )
    check(body["sessions"]["total_ms"] == work, f"session time {body['sessions']['total_ms']}, expected {work}")
    ops = by_key(body["operations"]["rows"], "operation")
    check(
        ops["creation"]["objects"] == draws and ops["creation"]["average_ms"] == GAP_S * 1000,
        f"creation {ops['creation']}, expected {draws} at {GAP_S} s",
    )
    check(by_key(body["creation_methods"]["rows"], "method")["drawn"]["objects"] == draws, "drawn")
    check(body["saved_boxes"]["boxes"] == draws - polygons, f"saved boxes {body['saved_boxes']['boxes']}")
    check(
        (body["input"]["hotkey_actions"], body["input"]["mouse_actions"], body["input"]["canvas_clicks"])
        == (hotkeys, mouse, canvas),
        f"input {body['input']}, expected {(hotkeys, mouse, canvas)}",
    )
    log(
        f"week: {len(active)} annotators, {len(projects_active)} projects, {len(sessions)} sessions, {work} ms, "
        f"{draws} drawn, saved {draws - polygons}, hotkeys {hotkeys}, mouse {mouse}, canvas {canvas}"
    )
    boxes = ok(owner, "overview", **{**query, "shapes": "bounding_boxes"})
    check(
        by_key(boxes["operations"]["rows"], "operation")["creation"]["objects"] == draws - polygons,
        "bounding boxes creation",
    )

    # trends: weekly working time per Monday week, the scope and two annotators compared
    trends = ok(owner, "trends", org=VOLUME_ORG, step="week")
    expected = defaultdict(int)
    for s in plan(anchor):
        expected[(s["day"] - timedelta(days=s["day"].weekday())).isoformat()] += s["k"] * GAP_S * 1000
    got = {b["start"]: p["working_time_ms"] for b, p in zip(trends["buckets"], trends["lines"][0]["points"])}
    check(all(b["processed"] for b in trends["buckets"]), f"unprocessed trend buckets {trends['buckets']}")
    check(
        {k: got.get(k, 0) for k in expected if k in got} == {k: v for k, v in expected.items() if k in got}
        and all(v == 0 for k, v in got.items() if k not in expected),
        f"trends {got}, expected {dict(expected)}",
    )
    ids = [VOLUME_USER_BASE + 1, VOLUME_USER_BASE + 2]
    pair = ok(owner, "trends", org=VOLUME_ORG, step="week", compare="annotators", ids=",".join(map(str, ids)))
    for line, i in zip(pair["lines"], (1, 2)):
        want = defaultdict(int)
        for s in plan(anchor):
            if s["i"] == i:
                want[(s["day"] - timedelta(days=s["day"].weekday())).isoformat()] += s["k"] * GAP_S * 1000
        mine = {b["start"]: p["working_time_ms"] for b, p in zip(pair["buckets"], line["points"])}
        check(all(mine[k] == want.get(k, 0) for k in mine), f"annotator {i}: {mine}, expected {dict(want)}")
    log(
        f"trends: {len([v for v in got.values() if v])} weeks with work match the loaded events; two annotators compared"
    )

    # details table and full view hold everyone
    listed = ok(owner, "list", org=VOLUME_ORG, period="week", by="annotators")
    check(len([r for r in listed["rows"] if r["working_time_ms"] > 0]) == len(active), "full list of annotators")
    details = ok(owner, "details", org=VOLUME_ORG, period="week", by="projects")
    check(details["total"] == len(projects_active), f"details total {details['total']}")
    log(f"list: {len(listed['rows'])} annotators; details by project: {details['total']} rows")


# ---------------------------------------------------------------- access

ENDPOINTS = [
    ("overview", {"period": "week"}),
    ("status", {}),
    ("trends", {"step": "week"}),
    ("details", {"period": "week", "by": "annotators"}),
    ("list", {"period": "week", "by": "projects"}),
]


def check_access() -> None:
    # (account, organization slug or "", expected status, expected error)
    cases = [
        ("ta-admin", "", 200, None),
        ("ta-admin", "ta-org-a", 200, None),
        ("ta-admin", VOLUME_ORG, 200, None),
        ("ta-owner", "ta-org-a", 200, None),
        ("ta-maintainer", "ta-org-a", 200, None),
        ("ta-supervisor", "ta-org-a", 403, "forbidden"),
        ("ta-worker", "ta-org-a", 403, "forbidden"),
        ("ta-outsider", "ta-org-a", 403, "forbidden"),
        ("ta-outsider", "", 403, "forbidden"),
        ("ta-maintainer-b", "ta-org-a", 403, "forbidden"),
        ("ta-owner-b", "ta-org-a", 403, "forbidden"),
        ("ta-maintainer-b", "ta-org-b", 200, None),
        ("ta-maintainer", "", 403, "organization_required"),
        ("ta-worker", "", 403, "forbidden"),
        ("ta-bot", UI_ORG, 200, None),
        ("ta-worker-c", UI_ORG, 403, "forbidden"),
    ]
    for username, org, want_status, want_error in cases:
        session = Session(username)
        seen = []
        for path, query in ENDPOINTS:
            status, body = service(session, path, org=org, **query)
            error = body.get("error") if isinstance(body, dict) and status != 200 else None
            check(
                (status, error) == (want_status, want_error),
                f"{username} org={org or '-'} {path}: {status} {error}, expected {want_status} {want_error}",
            )
            seen.append(status)
        log(f"{username}, org={org or '-'}: {want_status} {want_error or ''} on {len(seen)} endpoints")
    status, _ = service(_Anonymous(), "overview", org="ta-org-a")
    check(status == 401, f"anonymous: {status}")
    log("anonymous: 401")
    # the organization the admin names decides the scope: org a's figures only
    a = ok(Session("ta-admin"), "overview", org="ta-org-a", period="week")
    names = {r["user_name"] for r in a["by_annotator"]["rows"]}
    check(names == {"ta-worker", "ta-supervisor"}, f"admin with ta-org-a sees {names}")
    log(f"ta-admin, org=ta-org-a: rows {sorted(names)}")


class _Anonymous:
    """A caller without a CVAT session."""

    username = "anonymous"

    def call(self, path: str) -> tuple[int, object]:
        return get_json(urllib.request.build_opener(), path)


def page_context(state_file: str) -> None:
    state = json.loads(Path(state_file).read_text())
    owner = Session("ta-owner-v")
    print(
        json.dumps(
            {
                "volume_org": VOLUME_ORG,
                "ui_org": UI_ORG,
                "ui": state["ui"],
                "did": state["did"],
                "model": BOT_BOXES + DETECTOR["objects"],
                "volume_projects": volume_projects(owner),
                "volume_users": [volume_user(i)[0] for i in (1, 2)],
            }
        )
    )


def main() -> None:
    args = sys.argv[1:]
    if args == ["prepare-ui"]:
        prepare_ui()
    elif len(args) == 2 and args[0] == "check-ui-records":
        check_ui_records(args[1])
    elif len(args) == 3 and args[0] == "check-ui-figures":
        check_ui_figures(args[1], int(args[2]))
    elif args == ["load-volume"]:
        load_volume()
    elif len(args) == 2 and args[0] == "check-volume":
        check_volume(int(args[1]))
    elif args == ["check-access"]:
        check_access()
    elif len(args) == 2 and args[0] == "page-context":
        page_context(args[1])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
