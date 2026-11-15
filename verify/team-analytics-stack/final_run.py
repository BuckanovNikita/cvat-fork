"""Final run of Team Analytics on the test stack (ticket 18), driven by run.sh check-final.

    final_run.py prepare-ui                 a new project, task and job in ta-org-c for the browser
                                            to annotate (prints JSON for ui_actions.cjs)
    final_run.py check-ui-records FILE      after ui_actions.cjs: the records the real UI sent are in
                                            the events table, the detector record among them (one, for
                                            the run that created objects); the technical account saves
                                            boxes; working time behaves
    final_run.py check-ui-figures FILE      the analytics figures for that project, Model equal to the
                                            detector run's objects and the technical account's boxes
    final_run.py volume-accounts            JSON of the volume's annotators for seed_users.py
    final_run.py load-volume [N]            synthetic work in ta-org-v: 100 annotators, 40 projects with
                                            long names, ten weeks of history; the current week through
                                            the events API, each annotator signed in (only the first N
                                            with N, and nothing else); loads what is missing only
    final_run.py check-volume SECS          the analytics figures for the loaded events
    final_run.py check-access               every account and organization against every endpoint
    final_run.py page-context FILE          JSON for final_browser.cjs page (organizations, this run's
                                            project and what the browser did there)

FILE is the JSON that prepare-ui printed, extended by ui_actions.cjs with what the browser did.
Environment: TA_BASE_URL, TA_SEED_PASSWORD, TA_KUBE_CONTEXT, TA_NAMESPACE, TA_RELEASE, and TA_VOLUME_ORG
for a volume organization other than ta-org-v. Standard
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

from stack_api import API, Session, check, get_json, refusal, upload_images

UI_ORG = "ta-org-c"
# The volume organization; another one serves a stack that already holds a volume load.
VOLUME_ORG = os.environ.get("TA_VOLUME_ORG") or "ta-org-v"
TECHNICAL_ACCOUNT = "ta-bot"  # run.sh sets TEAM_ANALYTICS_TECHNICAL_ACCOUNTS to it
UI_IMAGES = 4
BOT_BOXES = 3


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


# ---------------------------------------------------------------- Team Analytics API


def service(session: Session, path: str, **query) -> tuple[int, object]:
    return session.call(API + path + "?" + urllib.parse.urlencode({"tz": "UTC", **query}))


def ok(session: Session, path: str, **query) -> dict:
    status, body = service(session, path, **query)
    check(status == 200, f"{session.username} {path} {query}: {status} {body}")
    return body


def org_id(session: Session, slug: str) -> int:
    return session.request("GET", f"/api/organizations?slug={slug}")["results"][0]["id"]


def wait_figures(session: Session, path: str, query: dict, ready, what: str, timeout_s: int) -> dict:
    """Polls the analytics API until `ready(body)`; the scheduled refresh brings new events within minutes."""
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
    """Two projects created for this run: one the browser annotates with the analytics worker up, one it
    annotates with the analytics worker stopped. Each run makes its own, so figures are read per project."""
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
        labels = owner.request("GET", f"/api/labels?project_id={project['id']}")["results"]
        made[role] = {
            "project_id": project["id"],
            "task_id": task["id"],
            "job_id": job["id"],
            "labels": [label["name"] for label in labels],
            "label_ids": {label["name"]: label["id"] for label in labels},  # for the supplied detector answer
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


def check_detector_record(did: dict, project: int, job: int) -> None:
    """The real UI ran the detector twice (ticket 25). Only the model list and the model's answers were
    supplied, in the browser (final_browser.cjs superviseDetector): first nothing, then three objects."""
    detector = did["detector"]
    supplied = [(r["method"], r["path"]) for r in detector["supplied"]]
    # the one other /api/lambda/ request goes to the real server: the tasks page, reached when the
    # browser leaves the job, lists running automatic-annotation requests (getInferenceStatusAsync)
    passed = detector["passed"]
    check(
        supplied
        == [("HEAD", "/api/lambda/functions"), ("GET", "/api/lambda/functions")]
        + [("POST", f"/api/lambda/functions/{detector['model']}")] * 2
        and all(r == {"method": "GET", "path": "/api/lambda/requests"} for r in passed),
        f"detector requests: supplied {supplied}, passed to the server {passed}",
    )
    calls = detector["calls"]
    check(
        [c["answered"] for c in calls] == [0, 3]
        and all((c["request"] or {}).get("job") == job and (c["request"] or {}).get("frame") == 0 for c in calls),
        f"detector calls {calls}",
    )
    created = detector["created"]
    check(created == {"objects": 3, "rectangles": 2}, f"detector objects saved in the job: {created}")
    log(
        f"detector: supplied {[' '.join(r) for r in supplied]}; passed to the server "
        f"{[r['method'] + ' ' + r['path'] for r in passed]}; "
        f"canvas shapes per run {[(r['answered'], r['shapes_before'], r['shapes_after']) for r in detector['runs']]}; "
        f"saved in the job with source auto {created}"
    )

    # one record left the browser, for the run that created objects; none for the empty answer
    unread = [p for p in did["event_posts"] if p["model_records"] is None]
    check(not unread, f"{len(unread)} event POST bodies could not be read")
    sent = [record for p in did["event_posts"] for record in p["model_records"]]
    check(
        len(sent) == 1
        and sent[0]["count"] == created["objects"]
        and sent[0]["payload"].get("rectangle_count") == created["rectangles"]
        and sent[0]["job_id"] == job,
        f"detector records in the UI's event POSTs {sent}, objects created {created}",
    )
    query = (
        "SELECT user_name, toString(count) AS count, payload, job_id FROM events WHERE project_id = "
        + str(int(project))
        + " AND obj_name = 'team_analytics:model_creation'"
    )
    wait_rows(query, bool, "the detector record")
    time.sleep(10)  # a second record, had one been sent, would be in the table by now
    found = clickhouse(query)
    check(
        len(found) == 1
        and found[0]["user_name"] == "ta-worker-c"
        and int(found[0]["job_id"]) == job
        and int(found[0]["count"]) == created["objects"]
        and payload(found[0]).get("rectangle_count") == created["rectangles"],
        f"detector records in the events table {found}, objects created {created}",
    )
    log(
        f"team_analytics:model_creation from the real UI: 1 record (sent 1), count {found[0]['count']}, "
        f"rectangle_count {payload(found[0]).get('rectangle_count')}; none for the empty answer"
    )


def check_ui_records(state_file: str) -> None:
    state = json.loads(Path(state_file).read_text())
    ui, did = state["ui"], state["did"]
    project, job = ui["project_id"], ui["job_id"]

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

    check_detector_record(did, project, job)

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
    detector = did["detector"]["created"]  # what the real UI's detector run created, read from the job
    query = {"org": UI_ORG, "period": "week", "project": project, "shapes": "all"}

    def ready(body: dict) -> bool:
        # a period that is not fully processed carries no figures (rows and counts are null)
        if not body["processed"]:
            return False
        ops = by_key(body["operations"]["rows"], "operation")
        return (
            body["creation_methods"]["model"]["objects"] == BOT_BOXES + detector["objects"]
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
        boxes["creation_methods"]["model"]["objects"] == BOT_BOXES + detector["rectangles"],
        f"Model under bounding boxes {boxes['creation_methods']['model']}",
    )
    log(f"bounding boxes: model {boxes['creation_methods']['model']['objects']}")

    # Model has counts and no time: the overview's Model carries objects and a share only, and
    # ta-worker-c's Model in the details is the detector run alone (the technical account is no person)
    for shapes, want in (("all", detector["objects"]), ("bounding_boxes", detector["rectangles"])):
        overview = body if shapes == "all" else boxes
        model = overview["creation_methods"]["model"]
        check(set(model) == {"objects", "share"}, f"Model ({shapes}) carries {sorted(model)}")
        details = ok(owner, "details", org=UI_ORG, period="week", project=project, by="annotators", shapes=shapes)
        worker = [r for r in details["rows"] if r["user_name"] == "ta-worker-c"]
        check(
            len(worker) == 1 and worker[0]["model"] == want,
            f"details ({shapes}) of ta-worker-c {worker}, detector made {want}",
        )
        check(
            not any("model" in key and key != "model" for key in worker[0]),
            f"details ({shapes}) model keys {sorted(worker[0])}",
        )
        log(
            f"Model ({shapes}): overview {model}, ta-worker-c in the details {worker[0]['model']} = the detector's {want}"
        )

    trends = ok(owner, "trends", org=UI_ORG, project=project, step="week")
    last = trends["lines"][0]["points"][-1]
    check(last["working_time_ms"] == working_ms, f"trends current week {last}, working time {working_ms}")
    log(f"trends: current week {last['working_time_ms']} ms, boxes {last['boxes']}")


# ---------------------------------------------------------------- volume (ta-org-v)

ANNOTATORS = 100
PROJECTS = 40
WEEKS = 10
GAP_S = 30
LONG_USER = "-with-an-exceptionally-long-display-name-for-the-overflow-checks"
LONG_PROJECT = " with a deliberately long name that has to wrap or be cut without overflowing its card"
VOLUME_MARK = "ta-volume-annotator-"
VOLUME_OWNER = "ta-owner-v"
VOLUME_LABEL = "box"
# How long the records of the load may take to reach the events table through Vector.
ARRIVAL_TIMEOUT_S = 600


def volume_user(i: int) -> str:
    return f"{VOLUME_MARK}{i:03d}{LONG_USER}"


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
                    "last": start + timedelta(seconds=GAP_S * k),
                    "polygons": 1 if i % 10 == 0 else 0,
                    "hotkeys": {"NEXT_FRAME": 1 + i % 7, "SWITCH_DRAW_MODE_STANDARD_CONTROLS": k},
                    "mouse": {"canvas": 2 * k, "controls_sidebar": 1},
                }
            )
    return out


def volume_accounts() -> None:
    """JSON for seed_users.py (run.sh load-volume): the annotators, each a worker of the volume organization.
    Stops first, before any account is made, when the organization holds a load from before ticket 26."""
    volume_sessions_loaded()
    known = json.loads((Path(__file__).resolve().parent / "accounts.json").read_text())["organizations"]
    name = known.get(VOLUME_ORG, {}).get("name", f"Team Analytics volume ({VOLUME_ORG})")
    users = [volume_user(i) for i in range(1, ANNOTATORS + 1)]
    members = {VOLUME_OWNER: "owner", **{user: "worker" for user in users}}
    print(
        json.dumps(
            {
                "users": {user: {"admin": False} for user in users},
                "organizations": {VOLUME_ORG: {"name": name, "members": members}},
            }
        )
    )


def client_events(s: dict, job: dict, anchor: date) -> list[dict]:
    """The client records of one session, as the UI sends them to POST /api/events (timestamps as datetimes).
    The session's load:job carries the anchor of the load, so that a later run finds the plan again."""

    def event(scope, when, count=None, obj_name=None, duration=0, body=None):
        return {
            "scope": scope,
            "obj_name": obj_name,
            "count": count,
            "duration": duration,
            "timestamp": when,
            "payload": json.dumps({"client_id": 4242, "is_active": True, **(body or {})}),
            "project_id": job["project_id"],
            "task_id": job["task_id"],
            "job_id": job["job_id"],
        }

    out = [event("load:job", s["start"], body={"volume_anchor": anchor.isoformat()})]
    for j in range(1, s["k"] + 1):
        polygon = j == s["k"] and s["polygons"]
        out.append(
            event(
                "draw:object",
                s["start"] + timedelta(seconds=GAP_S * j),
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
    out.append(
        event(
            "debug:info",
            s["last"],
            obj_name="team_analytics:input_summary",
            body={"hotkeys": s["hotkeys"], "mouse": s["mouse"]},
        )
    )
    return out


def direct_rows(s: dict, job: dict, anchor: date, org: int) -> list[dict]:
    """An older week's session as rows of the events table: its client records, and the working time and
    saved boxes that CVAT would have recorded for it (the API cannot date those back)."""
    check(s["w"] > 0, f"the current week's session of annotator {s['i']} must go through the API")
    who = {
        "user_id": job["user_id"],
        "user_name": volume_user(s["i"]),
        "user_email": f"{volume_user(s['i'])}@example.com",
        "org_id": org,
        "org_slug": VOLUME_ORG,
    }

    def stamp(when: datetime) -> str:
        return when.strftime("%Y-%m-%d %H:%M:%S.000")

    rows = [{**e, "source": "client", "timestamp": stamp(e["timestamp"]), **who} for e in client_events(s, job, anchor)]
    ids = {key: job[key] for key in ("project_id", "task_id", "job_id")}
    work = GAP_S * 1000 * s["k"]
    boxes = s["k"] - s["polygons"]
    rows.append(
        {
            "scope": "send:working_time",
            "obj_name": None,
            "source": "server",
            "count": 1,
            "duration": work,
            "timestamp": stamp(s["last"]),
            "payload": json.dumps({"working_time": work}, separators=(",", ":")),
            **ids,
            **who,
        }
    )
    rows.append(
        {
            "scope": "create:shapes",
            "obj_name": "rectangle",
            "source": "server",
            "count": boxes,
            "duration": 0,
            "timestamp": stamp(s["last"] + timedelta(seconds=1)),
            "payload": json.dumps({"shapes": [{"id": n} for n in range(boxes)]}, separators=(",", ":")),
            **ids,
            **who,
        }
    )
    return rows


def volume_projects(owner: Session) -> list[int]:
    found = owner.request("GET", f"/api/projects?org={VOLUME_ORG}&page_size=100")["results"]
    by_name = {p["name"]: p["id"] for p in found}
    ids = []
    for n in range(PROJECTS):
        name = f"Volume project {n:02d}{LONG_PROJECT}"
        if name not in by_name:
            by_name[name] = owner.request(
                "POST", f"/api/projects?org={VOLUME_ORG}", {"name": name, "labels": [{"name": VOLUME_LABEL}]}
            )["id"]
        ids.append(by_name[name])
    return ids


def volume_members(owner: Session) -> dict[str, int]:
    """User ids of the volume organization's members, by username."""
    out, page = {}, 1
    while True:
        body = owner.request("GET", f"/api/memberships?org={VOLUME_ORG}&page_size=100&page={page}")
        out.update({m["user"]["username"]: m["user"]["id"] for m in body["results"]})
        if not body.get("next"):
            return out
        page += 1


def volume_jobs(owner: Session, projects: list[int]) -> dict[int, dict]:
    """One task per project with a single-frame job for each annotator of the project, assigned to them."""
    members = volume_members(owner)
    missing = [volume_user(i) for i in range(1, ANNOTATORS + 1) if volume_user(i) not in members]
    check(not missing, f"{len(missing)} annotators are not members of {VOLUME_ORG} (run.sh load-volume seeds them)")
    tasks = {t["name"]: t["id"] for t in owner.request("GET", f"/api/tasks?org={VOLUME_ORG}&page_size=100")["results"]}
    out = {}
    for n, project in enumerate(projects):
        mine = [i for i in range(1, ANNOTATORS + 1) if i % PROJECTS == n]
        labels = owner.request("GET", f"/api/labels?project_id={project}&org={VOLUME_ORG}")["results"]
        if not labels:  # a project from a load before ticket 26 has no label to save boxes with
            owner.request("PATCH", f"/api/projects/{project}?org={VOLUME_ORG}", {"labels": [{"name": VOLUME_LABEL}]})
            labels = owner.request("GET", f"/api/labels?project_id={project}&org={VOLUME_ORG}")["results"]
        name = f"Volume task {n:02d}"
        if name not in tasks:
            task = owner.request(
                "POST", f"/api/tasks?org={VOLUME_ORG}", {"name": name, "project_id": project, "segment_size": 1}
            )
            upload_images(owner, task["id"], VOLUME_ORG, len(mine))
            tasks[name] = task["id"]
        for _ in range(120):
            jobs = owner.request("GET", f"/api/jobs?org={VOLUME_ORG}&task_id={tasks[name]}&page_size=100")["results"]
            if len(jobs) == len(mine):
                break
            time.sleep(2)
        else:
            raise SystemExit(f"{name}: {len(mine)} jobs not created within 4 minutes")
        for i, job in zip(mine, sorted(jobs, key=lambda j: j["start_frame"])):
            user_id = members[volume_user(i)]
            if (job.get("assignee") or {}).get("id") != user_id:
                owner.request("PATCH", f"/api/jobs/{job['id']}?org={VOLUME_ORG}", {"assignee": user_id})
            out[i] = {
                "project_id": project,
                "task_id": tasks[name],
                "job_id": job["id"],
                "frame": job["start_frame"],
                "label_id": labels[0]["id"],
                "user_id": user_id,
            }
    return out


def volume_sessions_loaded() -> dict[tuple[str, date], str]:
    """The sessions of the volume organization in the events table: (user name, day) -> anchor of their load.
    Stops on a load from before ticket 26 (no anchor), which a load through the API must not be added to."""
    rows = clickhouse(
        "SELECT user_name, toString(toDate(timestamp)) AS day, JSONExtractString(payload, 'volume_anchor') AS anchor "
        f"FROM events WHERE org_slug = '{VOLUME_ORG}' AND scope = 'load:job' AND startsWith(user_name, '{VOLUME_MARK}')"
    )
    legacy = [r for r in rows if not r["anchor"]]
    check(
        not legacy,
        f"{VOLUME_ORG} holds {len(legacy)} volume sessions of a direct load from before ticket 26; load into "
        "another organization (TA_VOLUME_ORG) or remove them first",
    )
    return {(r["user_name"], date.fromisoformat(r["day"])): r["anchor"] for r in rows}


def volume_anchor() -> date | None:
    anchors = set(volume_sessions_loaded().values())
    check(len(anchors) <= 1, f"{VOLUME_ORG} holds volume loads with several anchors: {sorted(anchors)}")
    return date.fromisoformat(anchors.pop()) if anchors else None


def send_session(s: dict, job: dict, anchor: date, post: bool, save: bool) -> dict:
    """The annotator signs in and does the session's part through the API: posts its client records (CVAT
    derives the working time from them) and saves its boxes in its job (CVAT records the saved boxes)."""
    took = {}
    started = time.monotonic()
    user = Session(volume_user(s["i"]))
    took["login_s"] = time.monotonic() - started
    if post:
        events = [{**e, "timestamp": e["timestamp"].isoformat()} for e in client_events(s, job, anchor)]
        started = time.monotonic()
        user.request(
            "POST",
            f"/api/events?org={VOLUME_ORG}",
            {"events": events, "timestamp": datetime.now(UTC).isoformat()},
        )
        took["post_s"] = time.monotonic() - started
        took["post_bytes"] = len(json.dumps({"events": events}))
    boxes = s["k"] - s["polygons"]
    if save and boxes:
        shapes = [
            {
                "type": "rectangle",
                "frame": job["frame"],
                "label_id": job["label_id"],
                "points": [1, 1, 3 + n % 4, 3 + n // 4],
                "occluded": False,
                "z_order": 0,
                "attributes": [],
            }
            for n in range(boxes)
        ]
        started = time.monotonic()
        user.request(
            "PATCH",
            f"/api/jobs/{job['job_id']}/annotations?action=create&org={VOLUME_ORG}",
            {"shapes": shapes, "tracks": [], "tags": [], "version": 0},
        )
        took["save_s"] = time.monotonic() - started
    return took


def volume_counts(anchor: date) -> dict:
    """What the events table holds of the volume, split into the current week (from anchor - 7) and before."""
    since = (anchor - timedelta(days=7)).isoformat()
    rows = clickhouse(
        "SELECT scope, timestamp >= toDateTime64('" + since + "', 3, 'Etc/UTC') AS current, count() AS n, "
        "sum(ifNull(count, 0)) AS objects, countIf(JSONHas(payload, 'request')) AS by_server "
        f"FROM events WHERE org_slug = '{VOLUME_ORG}' AND startsWith(user_name, '{VOLUME_MARK}') "
        "AND scope IN ('load:job', 'draw:object', 'debug:info', 'send:working_time', 'create:shapes') "
        "GROUP BY scope, current ORDER BY scope, current"
    )
    return {(r["scope"], int(r["current"])): {k: int(r[k]) for k in ("n", "objects", "by_server")} for r in rows}


def expected_counts(anchor: date) -> dict:
    out: dict = defaultdict(lambda: {"n": 0, "objects": 0, "by_server": 0})
    for s in plan(anchor):
        current = int(s["w"] == 0)
        boxes = s["k"] - s["polygons"]
        for scope, n, objects in (
            ("load:job", 1, 0),
            ("draw:object", s["k"], s["k"]),
            ("debug:info", 1, 0),
            ("send:working_time", 1, 1),
            ("create:shapes", 1 if not current or boxes else 0, boxes),
        ):
            out[(scope, current)]["n"] += n
            out[(scope, current)]["objects"] += objects
            if current and scope in ("send:working_time", "create:shapes"):
                out[(scope, current)]["by_server"] += n  # only CVAT itself writes these for the current week
    return {k: v for k, v in out.items() if v["n"]}


def check_current_week(anchor: date, jobs: dict[int, dict]) -> None:
    """The current week's records in the events table, against the generator: the gaps between an
    annotator's records as sent, CVAT's working time per session, and the boxes saved."""
    sessions = {s["i"]: s for s in plan(anchor) if s["w"] == 0}
    since = (anchor - timedelta(days=7)).isoformat()
    rows = clickhouse(
        "SELECT user_name, user_id, scope, source, job_id, toUnixTimestamp64Milli(timestamp) AS ms, count, payload "
        f"FROM events WHERE org_slug = '{VOLUME_ORG}' AND startsWith(user_name, '{VOLUME_MARK}') "
        "AND timestamp >= toDateTime64('" + since + "', 3, 'Etc/UTC') ORDER BY user_name, timestamp"
    )
    by_user: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_user[r["user_name"]].append(r)
    shifts = []
    for i, s in sessions.items():
        mine = by_user.get(volume_user(i), [])
        client = [r for r in mine if r["source"] == "client"]
        planned = [int(e["timestamp"].timestamp() * 1000) for e in client_events(s, jobs[i], anchor)]
        got = [int(r["ms"]) for r in client]
        check(len(got) == len(planned), f"annotator {i}: {len(got)} client records, sent {len(planned)}")
        check(
            [b - a for a, b in zip(got, got[1:])] == [b - a for a, b in zip(planned, planned[1:])],
            f"annotator {i}: gaps {got}, sent {planned}",
        )
        shifts.append(got[0] - planned[0])
        check(
            all(int(r["user_id"]) == jobs[i]["user_id"] and int(r["job_id"]) == jobs[i]["job_id"] for r in mine),
            f"annotator {i}: records not of user {jobs[i]['user_id']} in job {jobs[i]['job_id']}",
        )
        work = [json.loads(r["payload"]) for r in mine if r["scope"] == "send:working_time"]
        check(
            [w.get("working_time") for w in work] == [GAP_S * 1000 * s["k"]] and all("request" in w for w in work),
            f"annotator {i}: CVAT's working time {work}, expected {GAP_S * 1000 * s['k']}",
        )
        saved = sum(int(r["count"]) for r in mine if r["scope"] == "create:shapes")
        check(saved == s["k"] - s["polygons"], f"annotator {i}: saved {saved}, expected {s['k'] - s['polygons']}")
    log(
        f"current week in the events table: {len(sessions)} sessions as sent, gaps unchanged, CVAT's working time "
        f"and saved boxes as planned; record time moved by {min(shifts)}..{max(shifts)} ms (receive minus send time)"
    )


def load_volume(only: int | None = None) -> None:
    """Loads the volume once per organization. The current week goes through the events API, each annotator
    in its own session; the older weeks are inserted directly, since the API moves a record's time by the
    time between the request's own timestamp and its arrival, and CVAT stamps working time and saved boxes when it records them. A later run
    loads only what is not in the events table yet. `only` limits the current week to the first annotators."""
    began = time.monotonic()
    owner = Session(VOLUME_OWNER)
    org = org_id(owner, VOLUME_ORG)
    loaded = volume_sessions_loaded()
    anchor = volume_anchor() or datetime.now(UTC).date()
    sessions = plan(anchor)
    todo = [s for s in sessions if (volume_user(s["i"]), s["day"]) not in loaded]
    log(f"{VOLUME_ORG}: anchor {anchor}; {len(sessions) - len(todo)} of {len(sessions)} sessions already loaded")
    projects = volume_projects(owner)
    jobs = volume_jobs(owner, projects)
    log(f"layout: {len(projects)} projects, {len(jobs)} jobs, one per annotator ({time.monotonic() - began:.0f} s)")

    older = [s for s in todo if s["w"] > 0]
    if older and only is None:
        rows = [row for s in older for row in direct_rows(s, jobs[s["i"]], anchor, org)]
        clickhouse("INSERT INTO events FORMAT JSONEachRow", "".join(json.dumps(r) + "\n" for r in rows))
        log(f"older weeks: {len(rows)} rows of {len(older)} sessions inserted directly")

    current = {s["i"]: s for s in sessions if s["w"] == 0 and (only is None or s["i"] <= only)}
    posted = saved = 0
    took: dict[str, list[float]] = defaultdict(list)
    started = time.monotonic()
    for i, s in current.items():
        post = (volume_user(i), s["day"]) not in loaded
        have = owner.request("GET", f"/api/jobs/{jobs[i]['job_id']}/annotations?org={VOLUME_ORG}")["shapes"]
        save = s["k"] > s["polygons"] and not have
        if not (post or save):
            continue
        for key, value in send_session(s, jobs[i], anchor, post, save).items():
            took[key].append(value)
        posted += post
        saved += save
    sent_s = time.monotonic() - started
    summary = {k: f"{sum(v) / len(v):.3f}/{max(v):.3f}" for k, v in took.items()}
    log(
        f"current week through the API: {posted} annotators posted their session, {saved} saved boxes, in "
        f"{sent_s:.0f} s (mean/max {summary})"
    )

    if only is not None:
        return
    want = expected_counts(anchor)
    started = time.monotonic()
    while True:
        got = volume_counts(anchor)
        if got == want:
            break
        if time.monotonic() - started > ARRIVAL_TIMEOUT_S:
            raise SystemExit(f"volume records after {ARRIVAL_TIMEOUT_S} s: {got}, expected {want}")
        time.sleep(3)
    log(f"all records in the events table {time.monotonic() - started:.0f} s after the last request: {got}")
    check_current_week(anchor, jobs)
    log(f"volume loaded in {time.monotonic() - began:.0f} s")


def week_span(today: date) -> tuple[date, date]:
    return today - timedelta(days=6), today


def check_volume(timeout_s: int) -> None:
    owner = Session("ta-owner-v")
    projects = volume_projects(owner)
    anchor = volume_anchor()
    check(anchor is not None, "no volume events loaded")
    check_current_week(anchor, volume_jobs(owner, projects))
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
    members = volume_members(owner)
    ids = [members[volume_user(1)], members[volume_user(2)]]
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
            error = refusal(status, body)
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
                "model": BOT_BOXES + state["did"]["detector"]["created"]["objects"],
                "volume_projects": volume_projects(owner),
                "volume_users": [volume_members(owner)[volume_user(i)] for i in (1, 2)],
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
    elif args == ["volume-accounts"]:
        volume_accounts()
    elif args == ["load-volume"]:
        load_volume()
    elif len(args) == 2 and args[0] == "load-volume":
        load_volume(int(args[1]))
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
