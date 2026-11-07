"""Seeds the throwaway stack with the organization the issue rules are about.

Layout it builds:
  organization  acme
  admin         superuser, owns the task and both issues
  worker1       org member, role worker, ASSIGNED to the job - the browser tab
  worker2       org member, role worker, touches nothing - the API-only case
  task/job      one 64x64 frame, inside the organization
  issue #1      opened by admin, carrying admin's first comment
  issue #2      opened by admin, sacrificial: the delete check destroys it

Users and memberships go in through the ORM rather than the API because the
invitation flow needs a mail backend, and that is not what is under test here.
"""

import json
import os
import subprocess
import sys
import time

import requests

BASE = os.environ.get("OPA_ISSUES_BASE", "http://localhost:8281/api")
SERVER = os.environ.get("OPA_ISSUES_SERVER", "opa_cvat_server")
ADMIN = ("admin", "verify-pass-123")
WORKERS = [("worker1", "worker-pass-123"), ("worker2", "worker-pass-123")]
ORG = "acme"
STATE = os.environ.get("OPA_ISSUES_STATE", "/tmp/opa-issues-state.json")

ORM_SETUP = """
from django.contrib.auth.models import User
from django.utils import timezone
from cvat.apps.organizations.models import Membership, Organization

org = Organization.objects.get(slug={org!r})
for username, password in {workers!r}:
    user, created = User.objects.get_or_create(
        username=username, defaults={{"email": username + "@example.com"}}
    )
    user.set_password(password)
    user.is_active = True
    user.save()
    Membership.objects.update_or_create(
        user=user,
        organization=org,
        defaults={{"is_active": True, "joined_date": timezone.now(), "role": Membership.WORKER}},
    )
print("members:", list(org.members.values_list("user__username", "role", "is_active")))
"""


def session(username: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"username": username, "password": password}, timeout=30)
    r.raise_for_status()
    s.headers["Authorization"] = f"Token {r.json()['key']}"
    return s


def wait_for_request(s: requests.Session, rq_id: str) -> None:
    deadline = time.time() + 300
    while time.time() < deadline:
        status = s.get(f"{BASE}/requests/{rq_id}", timeout=30).json()
        if status["status"] == "finished":
            return
        if status["status"] == "failed":
            sys.exit(f"task data failed: {status.get('message')}")
        time.sleep(2)
    sys.exit("task data never finished")


admin = session(*ADMIN)

orgs = admin.get(f"{BASE}/organizations", params={"slug": ORG}, timeout=30).json()["results"]
if orgs:
    org_id = orgs[0]["id"]
else:
    r = admin.post(f"{BASE}/organizations", json={"slug": ORG, "name": "Acme"}, timeout=30)
    r.raise_for_status()
    org_id = r.json()["id"]

orm = subprocess.run(
    ["docker", "exec", "-i", SERVER, "python", "manage.py", "shell"],
    input=ORM_SETUP.format(org=ORG, workers=WORKERS),
    capture_output=True,
    text=True,
    check=True,
)
print(orm.stdout.strip())

admin.headers["X-Organization"] = ORG

r = admin.post(
    f"{BASE}/tasks",
    json={"name": "issue access", "labels": [{"name": "object", "attributes": []}]},
    timeout=60,
)
r.raise_for_status()
task_id = r.json()["id"]

image = "/tmp/opa-issues-frame.png"
subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "mkimg.py"), "/tmp/opa-issues-img"], check=True)
os.replace("/tmp/opa-issues-img/img_0.png", image)

with open(image, "rb") as fh:
    r = admin.post(
        f"{BASE}/tasks/{task_id}/data",
        files={"client_files[0]": ("frame.png", fh, "image/png")},
        data={"image_quality": "70", "sorting_method": "lexicographical"},
        timeout=120,
    )
r.raise_for_status()
wait_for_request(admin, r.json()["rq_id"])

job = admin.get(f"{BASE}/jobs", params={"task_id": task_id}, timeout=30).json()["results"][0]
job_id = job["id"]

users = {
    u["username"]: u["id"] for u in admin.get(f"{BASE}/users", params={"page_size": 100}, timeout=30).json()["results"]
}
r = admin.patch(f"{BASE}/jobs/{job_id}", json={"assignee": users["worker1"]}, timeout=30)
r.raise_for_status()

issues = []
for message in ("opened by admin - the one both tabs must read and edit", "sacrificial - worker1 deletes this"):
    r = admin.post(
        f"{BASE}/issues",
        json={"frame": 0, "job": job_id, "position": [10.0, 10.0, 40.0, 40.0], "message": message},
        timeout=30,
    )
    r.raise_for_status()
    issues.append(r.json()["id"])

comments = admin.get(f"{BASE}/comments", params={"issue_id": issues[0]}, timeout=30).json()["results"]

state = {
    "base": BASE,
    "org": ORG,
    "org_id": org_id,
    "task_id": task_id,
    "job_id": job_id,
    "issue_id": issues[0],
    "sacrificial_issue_id": issues[1],
    "admin_comment_id": comments[0]["id"],
    "users": {name: users[name] for name in ("admin", "worker1", "worker2")},
}
with open(STATE, "w") as fh:
    json.dump(state, fh, indent=2)
print(json.dumps(state, indent=2))
