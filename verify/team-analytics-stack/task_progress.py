"""Seed of the task-progress check on the test stack (run.sh check-task-progress).

    task_progress.py seed     two new tasks in ta-admin's personal workspace: one job in every
                              job stage and state, and a single annotation/new job; every job is
                              read back. Prints JSON for task_progress_browser.cjs.

The stages and states are taken from the running server's API schema and must be exactly the
ones the check expects, so a stage or state added upstream fails the seed instead of going
unseeded. The tasks are created by ta-admin in its personal workspace: no organization's
figures are touched, and the owner sees every job of the task. Each run creates new tasks.
Environment: TA_BASE_URL, TA_SEED_PASSWORD. Standard library only.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run with python3 -I, which leaves it out

from stack_api import BASE_URL, Session, check, tiny_png

ACCOUNT = "ta-admin"
ORG = ""  # the personal workspace: ?org= with no slug
# Upstream's JobStage and JobState (cvat-core/src/enums.ts; StageChoice and StateChoice in the
# server), in the order the task card lists them.
STAGES = ["annotation", "validation", "acceptance"]
STATES = ["new", "in progress", "completed", "rejected"]
# The two names the server's schema gives those enums (ENUM_NAME_OVERRIDES in its settings).
SCHEMA_ENUMS = {"JobStage": STAGES, "OperationStatus": STATES}


def log(message: str) -> None:
    print(f"  {message}", file=sys.stderr, flush=True)


def schema_enums(session: Session) -> dict[str, list[str]]:
    req = urllib.request.Request(f"{BASE_URL}/api/schema/", headers={"Accept": "application/vnd.oai.openapi+json"})
    try:
        with session.opener.open(req, timeout=180) as resp:
            schema = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"GET /api/schema/ -> {e.code} {e.read().decode()[:300]}") from None
    components = schema["components"]["schemas"]
    return {name: components.get(name, {}).get("enum") for name in SCHEMA_ENUMS}


def upload(session: Session, task_id: int, count: int) -> None:
    """count distinct 8x8 PNGs as the task's data, the multipart form the UI sends."""
    boundary = uuid.uuid4().hex
    fields = {"image_quality": "70", "sorting_method": "lexicographical"}
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()
    ]
    for i in range(count):
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="client_files[{i}]"; filename="frame{i:02d}.png"\r\n'
            "Content-Type: image/png\r\n\r\n".encode()
            + tiny_png(20 + 230 * i // max(1, count - 1))
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(f"{BASE_URL}/api/tasks/{task_id}/data?org={ORG}", data=b"".join(parts), method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Origin", BASE_URL)
    req.add_header("X-CSRFTOKEN", session._csrf())
    try:
        with session.opener.open(req, timeout=120):
            pass
    except urllib.error.HTTPError as e:
        raise SystemExit(f"task {task_id} data -> {e.code} {e.read().decode()[:300]}") from None


def jobs_of(session: Session, task_id: int) -> list[dict]:
    page = session.request("GET", f"/api/jobs?org={ORG}&task_id={task_id}&page_size=100")
    return sorted(page["results"], key=lambda job: job["id"])


def make_task(session: Session, name: str, segment_size: int, images: int) -> tuple[int, list[dict]]:
    task = session.request(
        "POST",
        f"/api/tasks?org={ORG}",
        {"name": name, "labels": [{"name": "object", "attributes": []}], "segment_size": segment_size},
    )
    check(task.get("organization_id") is None, f"task {task['id']} is in organization {task.get('organization_id')}")
    upload(session, task["id"], images)
    expected = -(-images // segment_size)  # one job per segment; the last segment may be short
    for _ in range(120):
        jobs = jobs_of(session, task["id"])
        if len(jobs) == expected:
            return task["id"], jobs
        time.sleep(2)
    raise SystemExit(f"task {task['id']}: {expected} jobs were not created within 4 minutes")


def seed() -> None:
    session = Session(ACCOUNT)

    found = schema_enums(session)
    check(found == SCHEMA_ENUMS, f"the server's job stages and states are {found}, the check covers {SCHEMA_ENUMS}")
    log(f"server schema: stages {found['JobStage']}, states {found['OperationStatus']}")

    run = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    plan = [(stage, state) for stage in STAGES for state in STATES]

    mixed_id, jobs = make_task(session, f"ta-progress {run} mixed stages", 1, len(plan))
    for job, (stage, state) in zip(jobs, plan):
        session.request("PATCH", f"/api/jobs/{job['id']}?org={ORG}", {"stage": stage, "state": state})
    got = [(job["stage"], job["state"]) for job in jobs_of(session, mixed_id)]
    check(got == plan, f"task {mixed_id} jobs read back as {got}, expected {plan}")
    log(f"task {mixed_id}: {len(got)} jobs, one in each stage/state, read back")

    single_id, jobs = make_task(session, f"ta-progress {run} single job", 6, 1)
    got = [(job["stage"], job["state"]) for job in jobs]
    check(got == [("annotation", "new")], f"task {single_id} jobs read back as {got}")
    log(f"task {single_id}: 1 job, annotation/new, read back")

    for task_id, size in ((mixed_id, len(plan)), (single_id, 1)):
        task = session.request("GET", f"/api/tasks/{task_id}?org={ORG}")
        check(task["jobs"]["count"] == size, f"task {task_id} reports {task['jobs']['count']} jobs, expected {size}")

    json.dump(
        {
            "account": ACCOUNT,
            "tasks": [
                {"id": mixed_id, "jobs": [{"stage": s, "state": t} for s, t in plan]},
                {"id": single_id, "jobs": [{"stage": "annotation", "state": "new"}]},
            ],
        },
        sys.stdout,
        indent=2,
    )
    print()


def main() -> None:
    if sys.argv[1:] == ["seed"]:
        seed()
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
