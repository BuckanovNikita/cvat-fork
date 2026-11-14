"""The issue and comment permission matrix (ticket 09), driven by run.sh check-issues.

    issue_matrix.py live FILE         on a running, seeded stack: set the global roles of
                                      issue_accounts.json through the admin API and read them back,
                                      find or create the jobs, issues and comments, run every row
                                      through the real API, judge it and write the results to FILE
    issue_matrix.py opa-cases         print the OPA inputs the server would build for every row,
                                      for a synthetic copy of the same layout
    issue_matrix.py opa-judge MODE    judge OPA's answers (stdin) against the expectations of MODE,
                                      patched or stock

One table (ACTION_ROWS, LIST_ROWS) holds the expectations; the live run and the policy-engine run
both read it. Each row has the patched expectation, which the live run checks, and the stock one,
which only the policy-engine run against the stock tag checks: a row the patch widens flips there,
and a row for the account with no global role must not.

The accounts and the two organizations are loaded by seed_users.py (run.sh feeds it
issue_accounts.json); this file sets the global roles, because seed_users.py gives every account
the `user` role. Environment for live: TA_BASE_URL, TA_SEED_PASSWORD. Standard library only.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # run with python3 -I, which leaves it out

ACCOUNTS = json.loads((HERE / "issue_accounts.json").read_text())

ORG_I, ORG_J = "ta-org-i", "ta-org-j"
ADMIN = "ta-admin"  # from accounts.json, loaded by run.sh seed
TASK_NAME = "ta-issue-matrix"

# The layout: job -> (organization, assignee). J1 and JJ are assigned to nobody; J2 to the
# account with no global role, so that it is staff of exactly one issue.
JOBS = {"J1": (ORG_I, None), "J2": (ORG_I, "ta-norole-i"), "JJ": (ORG_J, None)}
# Fixed issues, each opened by its organization's owner on its job, with the first comment that
# opening an issue creates (C1, C2, CJ, the comments the rows act on) and a second comment by
# the owner (REPLY).
ISSUES = {"I1": "J1", "I2": "J2", "IJ": "JJ"}
FIXED_POSITION = [10.0, 10.0, 40.0, 40.0]
THROWAWAY_POSITION = [1.0, 1.0, 9.0, 9.0]
ACTOR_POSITION = [2.0, 2.0, 8.0, 8.0]
REPLY = "second fixed comment, by the owner"


def comment_of(issue: str) -> str:
    return "C" + issue[1:]


ACTIONS = [
    "create issue",
    "view issue",
    "update issue",
    "delete issue",
    "create comment",
    "view comment",
    "update comment",
    "delete comment",
]
ALL = frozenset(ACTIONS)
NONE: frozenset[str] = frozenset()
VIEWS = frozenset({"view issue", "view comment"})
REFUSED = "refused"
SHOWN = {True: "ALLOW", False: "DENY "}
# Every refusal of the matrix, actions and lists, answered 403 on the stack (2026-11-15,
# docs/evidence/2026-11-14-stack-issue-matrix.md); any other code fails its row.
REFUSAL_STATUS = 403

# (actor, organization the request names or None, target issue, allowed patched, allowed stock).
# "create issue" targets the issue's job, the comment actions the issue's fixed comment, the
# deletes a throwaway issue or comment the owner opens on the same job or issue for the row.
ACTION_ROWS = [
    # unassigned members at or above the floor: everything, which stock refuses
    ("ta-worker-i", ORG_I, "I1", ALL, NONE),
    ("ta-worker-i2", ORG_I, "I1", ALL, NONE),  # global role worker, the floor itself
    ("ta-supervisor-i", ORG_I, "I1", ALL, NONE),
    ("ta-maintainer-i", ORG_I, "I1", ALL, ALL),
    # no global role: stock's result, not staff of I1, staff of I2 through its job
    ("ta-norole-i", ORG_I, "I1", NONE, NONE),
    ("ta-norole-i", ORG_I, "I2", VIEWS, VIEWS),
    # another organization's member, in its own organization and naming this one
    ("ta-worker-j", ORG_J, "I1", NONE, NONE),
    ("ta-worker-j", ORG_I, "I1", NONE, NONE),
    # this organization's members on the other organization's issue
    ("ta-worker-i", ORG_I, "IJ", NONE, NONE),
    ("ta-maintainer-i", ORG_I, "IJ", NONE, NONE),
    # a member of no organization, naming this one and in its personal workspace
    ("ta-outsider-i", ORG_I, "I1", NONE, NONE),
    ("ta-outsider-i", None, "I1", NONE, NONE),
]

# (actor, organization named or None, fixed issues listed patched, stock). Comments listed are
# the fixed comments of the listed issues. The fixed issues are judged; when an organization is
# named, no listed issue or comment of the layout may belong to another one.
LIST_ROWS = [
    ("ta-worker-i", ORG_I, {"I1", "I2"}, set()),
    ("ta-worker-i2", ORG_I, {"I1", "I2"}, set()),
    ("ta-supervisor-i", ORG_I, {"I1", "I2"}, set()),
    ("ta-maintainer-i", ORG_I, {"I1", "I2"}, {"I1", "I2"}),
    ("ta-norole-i", ORG_I, {"I2"}, {"I2"}),
    # no organization named: stock lists what the caller is staff of in every organization
    ("ta-norole-i", None, {"I2"}, {"I2"}),
    ("ta-worker-j", ORG_J, {"IJ"}, set()),
    ("ta-worker-j", ORG_I, REFUSED, REFUSED),
    ("ta-worker-j", None, set(), set()),
    ("ta-worker-i", ORG_J, REFUSED, REFUSED),
    ("ta-worker-i", None, set(), set()),
    ("ta-outsider-i", ORG_I, REFUSED, REFUSED),
    ("ta-outsider-i", ORG_J, REFUSED, REFUSED),
    ("ta-outsider-i", None, set(), set()),
]


def owner_of(org: str) -> str:
    return next(u for u, r in ACCOUNTS["organizations"][org]["members"].items() if r == "owner")


def role_in(user: str, org: str | None) -> str | None:
    return None if org is None else ACCOUNTS["organizations"][org]["members"].get(user)


def org_of_issue(issue: str) -> str:
    return JOBS[ISSUES[issue]][0]


def list_expectation(expected: object, kind: str) -> object:
    if expected == REFUSED:
        return REFUSED
    return set(expected) if kind == "issues" else {comment_of(i) for i in expected}


# ---------------------------------------------------------------- the policy engine, no server


def synthetic_ids() -> tuple[dict[str, int], dict[str, int]]:
    users = {name: 100 + n for n, name in enumerate(ACCOUNTS["users"])}
    orgs = {ORG_I: 1, ORG_J: 2}
    return users, orgs


def opa_cases() -> dict:
    """The inputs the stock server builds (cvat/apps/iam/permissions.py and the Issue and Comment
    permissions of cvat/apps/engine/permissions.py in cvat/server:v2.82.0): for view, update and
    delete the organization is the object's and the role the caller's active membership in it;
    for create and list it is the organization the request names."""
    uid, oid = synthetic_ids()
    priority = ["admin", "user", "worker"]

    def privilege(user: str) -> str | None:
        groups = sorted(ACCOUNTS["users"][user]["groups"], key=priority.index)
        return groups[0] if groups else None

    def auth(user: str, org: str | None, named: str | None) -> dict:
        return {
            "user": {"id": uid[user], "privilege": privilege(user)},
            "organization": None
            if org is None
            else {"id": oid[org], "owner": {"id": uid[owner_of(org)]}, "user": {"role": role_in(user, org)}},
            "organization_specified": named is not None,
        }

    def job_common(job: str) -> dict:
        org, assignee = JOBS[job]
        return {
            "project": None,
            "task": {"owner": {"id": uid[owner_of(org)]}, "assignee": {"id": None}},
            "job": {"assignee": {"id": uid.get(assignee)}},
            "organization": {"id": oid[org]},
        }

    def issue_common(issue: str) -> dict:
        org = org_of_issue(issue)
        return {
            **job_common(ISSUES[issue]),
            "issue": {"owner": {"id": uid[owner_of(org)]}, "assignee": {"id": None}},
        }

    cases = []
    for n, (actor, named, issue, _, _) in enumerate(ACTION_ROWS):
        org = org_of_issue(issue)
        owner = {"id": uid[owner_of(org)]}
        for action in ACTIONS:
            verb, kind = action.split()
            pkg = "issues" if kind == "issue" else "comments"
            if verb == "create" and kind == "issue":
                scope, who = "create@job", auth(actor, named, named)
                resource = {**job_common(ISSUES[issue]), "owner": {"id": uid[actor]}, "assignee": {"id": None}}
            elif verb == "create":
                scope, who = "create@issue", auth(actor, named, named)
                resource = {**issue_common(issue), "owner": {"id": uid[actor]}}
            elif kind == "issue":
                scope, who = verb, auth(actor, org, named)
                resource = {**job_common(ISSUES[issue]), "id": 1000 + n, "owner": owner, "assignee": {"id": None}}
            else:
                scope, who = verb, auth(actor, org, named)
                resource = {**issue_common(issue), "id": 2000 + n, "owner": owner}
            cases.append(
                {"id": f"a{n}:{action}", "pkg": pkg, "input": {"scope": scope, "auth": who, "resource": resource}}
            )
    for n, (actor, named, _, _) in enumerate(LIST_ROWS):
        for pkg in ("issues", "comments"):
            cases.append(
                {
                    "id": f"l{n}:{pkg}",
                    "pkg": pkg,
                    "input": {"scope": "list", "auth": auth(actor, named, named), "resource": None},
                }
            )
    return {"cases": cases}


# The query opa eval runs over data.cases (run.sh check-issue-policies). The input is bound to a
# local first: with OPA 1.12.2, `with input as c.input` inside a comprehension gave false where
# the same input bound as `i := c.input` gave true.
OPA_QUERY = (
    "array.concat("
    + ", ".join(
        f'[{{"id": c.id, "allow": a, "filter": f}} | some c in data.cases; c.pkg == "{pkg}"; i := c.input; '
        f"a := data.{pkg}.allow with input as i; f := [x | x := data.{pkg}.filter with input as i]]"
        for pkg in ("issues", "comments")
    )
    + ")"
)


def fixed_fields() -> dict[str, dict[str, object]]:
    """The row fields a list filter can name, for the fixed issues and comments of the layout."""
    uid, oid = synthetic_ids()
    out: dict[str, dict[str, object]] = {}
    for issue, job in ISSUES.items():
        org, assignee = JOBS[job]
        fields = {
            "owner": uid[owner_of(org)],
            "assignee": None,
            "job__assignee": uid.get(assignee),
            "job__segment__task__owner": uid[owner_of(org)],
            "job__segment__task__assignee": None,
            "job__segment__task__project__owner": None,
            "job__segment__task__project__assignee": None,
            "job__segment__task__organization": oid[org],
        }
        out[issue] = fields
        out[comment_of(issue)] = {"owner": uid[owner_of(org)], **{f"issue__{k}": v for k, v in fields.items()}}
    return out


def q_matches(expr: object, row: dict[str, object]) -> bool:
    """Evaluates a filter as cvat/apps/iam/permissions.py turns it into a Django Q object."""
    if expr == "org_filter_proof":
        return True
    if isinstance(expr, dict):
        for field, value in expr.items():
            if field not in row:
                raise SystemExit(f"the filter names a field the layout does not model: {field}")
            if row[field] != value:
                return False
        return True
    if isinstance(expr, list) and expr and expr[0] == "~":
        return not q_matches(expr[1], row)
    if isinstance(expr, list) and expr and expr[0] in ("&", "|"):
        results = [q_matches(e, row) for e in expr[1:]]
        return all(results) if expr[0] == "&" else any(results)
    raise SystemExit(f"unknown filter expression: {expr!r}")


def opa_judge(mode: str) -> None:
    column = {"patched": 3, "stock": 4}[mode]
    answers = {r["id"]: r for r in json.load(sys.stdin)["result"][0]["expressions"][0]["value"]}
    fields = fixed_fields()
    failures = 0

    def report(ok: bool, text: str) -> None:
        nonlocal failures
        failures += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {text}")

    print(f"issue matrix against the {mode} policies:")
    for n, row in enumerate(ACTION_ROWS):
        actor, named, issue = row[:3]
        allowed = row[column]
        for action in ACTIONS:
            got = answers[f"a{n}:{action}"]["allow"]
            want = action in allowed
            report(got == want, f"{actor:16} org={named or '-':9} {action:15} {issue}: allow={got}, expected {want}")
    for n, row in enumerate(LIST_ROWS):
        actor, named = row[:2]
        for kind in ("issues", "comments"):
            answer = answers[f"l{n}:{kind}"]
            want = list_expectation(row[column - 1], kind)
            if not answer["allow"]:
                got: object = REFUSED
            elif not answer["filter"]:
                got = "allowed without a filter"
            else:
                names = [k for k in fields if (k[0] == "I") == (kind == "issues")]
                got = {k for k in names if q_matches(answer["filter"][0], fields[k])}
            report(got == want, f"{actor:16} org={named or '-':9} list {kind:9}: {fmt(got)}, expected {fmt(want)}")
    if failures:
        raise SystemExit(f"{failures} expectations differ from the {mode} policies")
    print(f"every expectation matches the {mode} policies")


def fmt(value: object) -> str:
    return "{" + ", ".join(sorted(value)) + "}" if isinstance(value, set) else str(value)


# ---------------------------------------------------------------- the real API


def send(session, method: str, path: str, body: object = None) -> tuple[int, object]:
    """A request as the account of session that returns (status, JSON body) instead of failing."""
    from stack_api import BASE_URL

    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE_URL + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if method != "GET":
        req.add_header("Origin", BASE_URL)
        req.add_header("X-CSRFTOKEN", session._csrf())
    try:
        with session.opener.open(req, timeout=60) as resp:
            status, text = resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read().decode()
    try:
        return status, json.loads(text) if text.strip() else None
    except ValueError:
        return status, text[:200]


def with_org(path: str, org: str | None, **params: object) -> str:
    query = {**({"org": org} if org else {}), **{k: v for k, v in params.items() if v is not None}}
    return path + ("?" + urllib.parse.urlencode(query) if query else "")


def outcome(status: int, effect_seen: bool, nothing_changed: bool) -> object:
    """True (allowed) for a success whose effect the owner reads back, False (refused) for a
    REFUSAL_STATUS after which the owner reads nothing changed, anything else (another 4xx, a
    server error, a lost session, a refusal with an effect) "inconsistent", which matches no
    expectation."""
    if status < 300 and effect_seen:
        return True
    if status == REFUSAL_STATUS and nothing_changed:
        return False
    return "inconsistent"


class Live:
    def __init__(self) -> None:
        from stack_api import Session

        self.sessions = {name: Session(name) for name in [ADMIN, *ACCOUNTS["users"]]}
        self.ids: dict[str, int] = {}  # layout key (J1, I1, C1, ...) -> id on the stack
        self.user_ids: dict[str, int] = {}
        self.org_jobs: dict[str, set[int]] = {}
        self.frames: dict[str, int] = {}

    def must(self, user: str, method: str, path: str, body: object = None, want: tuple = (200, 201, 204)):
        status, out = send(self.sessions[user], method, path, body)
        if status not in want:
            raise SystemExit(f"{user}: {method} {path} -> {status} {str(out)[:300]}")
        return out

    def pages(self, user: str, path: str) -> tuple[int, list]:
        """Every page of a list; (status, rows), rows empty when refused."""
        rows: list = []
        page = 1
        while True:
            sep = "&" if "?" in path else "?"
            status, body = send(self.sessions[user], "GET", f"{path}{sep}page_size=100&page={page}")
            if status != 200:
                return status, []
            rows += body["results"]
            if not body.get("next"):
                return status, rows
            page += 1

    # ---------------------------------------------------------- global roles

    def set_roles(self) -> None:
        print("global roles, set by ta-admin through PATCH /api/users/<id>:")
        for user, spec in ACCOUNTS["users"].items():
            me = self.must(user, "GET", "/api/users/self")
            self.user_ids[user] = me["id"]
            status, answer = send(self.sessions[ADMIN], "PATCH", f"/api/users/{me['id']}", {"groups": spec["groups"]})
            if status != 200:
                raise SystemExit(f"{user}: PATCH groups -> {status} {str(answer)[:300]}")
            groups = self.must(user, "GET", "/api/users/self")["groups"]
            if sorted(groups) != sorted(spec["groups"]) or sorted(answer["groups"]) != sorted(spec["groups"]):
                raise SystemExit(
                    f"{user}: groups answered {answer['groups']}, read back {groups}, want {spec['groups']}"
                )
            print(f"  {user}: before {me['groups']}, PATCH -> {status} groups={answer['groups']}, read back {groups}")
        for org, spec in ACCOUNTS["organizations"].items():
            members = self.pages(owner_of(org), with_org("/api/memberships", org))[1]
            found = {m["user"]["username"]: (m["role"], m["is_active"]) for m in members}
            expected = {u: (r, True) for u, r in spec["members"].items()}
            if found != expected:
                raise SystemExit(f"{org}: memberships {found}, expected {expected}")
            print(f"  {org}: {found}")

    # ---------------------------------------------------------- layout

    def task_jobs(self, org: str, count: int) -> list[dict]:
        from stack_api import upload_images

        owner = owner_of(org)
        found = self.must(owner, "GET", with_org("/api/tasks", org, name=TASK_NAME))["results"]
        if found:
            task_id = found[0]["id"]
        else:
            task = self.must(
                owner,
                "POST",
                with_org("/api/tasks", org),
                {"name": TASK_NAME, "labels": [{"name": "box"}], "segment_size": 1},
            )
            task_id = task["id"]
            upload_images(self.sessions[owner], task_id, org, count)
        for _ in range(120):
            jobs = self.must(owner, "GET", with_org("/api/jobs", org, task_id=task_id, page_size=100))["results"]
            if len(jobs) == count:
                return sorted(jobs, key=lambda job: job["id"])
            time.sleep(2)
        raise SystemExit(f"{org}: the jobs of task {TASK_NAME} were not there within 4 minutes")

    def layout(self) -> None:
        print("layout:")
        by_org: dict[str, list[str]] = {}
        for job, (org, _) in JOBS.items():
            by_org.setdefault(org, []).append(job)
        for org, keys in by_org.items():
            for key, job in zip(keys, self.task_jobs(org, len(keys))):
                self.ids[key] = job["id"]
                self.frames[key] = job["start_frame"]
            self.org_jobs[org] = {self.ids[k] for k in keys}
        for job, (org, assignee) in JOBS.items():
            assignee_id = self.user_ids[assignee] if assignee else None
            self.must(owner_of(org), "PATCH", with_org(f"/api/jobs/{self.ids[job]}", org), {"assignee": assignee_id})
            print(f"  {job}: job {self.ids[job]} in {org}, assigned to {assignee or 'nobody'}")
        for issue, job in ISSUES.items():
            org = org_of_issue(issue)
            owner = owner_of(org)
            mine = [
                i
                for i in self.pages(owner, with_org("/api/issues", org, job_id=self.ids[job]))[1]
                if i["owner"]["username"] == owner and i["position"] == FIXED_POSITION
            ]
            if mine:
                self.ids[issue] = min(i["id"] for i in mine)
            else:
                self.ids[issue] = self.new_issue(owner, org, job, FIXED_POSITION, f"fixed issue {issue}")
            # leftovers of an interrupted run: every other issue of the job, every later comment
            for i in self.pages(owner, with_org("/api/issues", org, job_id=self.ids[job]))[1]:
                if i["id"] != self.ids[issue]:
                    self.must(owner, "DELETE", with_org(f"/api/issues/{i['id']}", org))
            comments = sorted(
                self.pages(owner, with_org("/api/comments", org, issue_id=self.ids[issue]))[1], key=lambda c: c["id"]
            )
            self.ids[comment_of(issue)] = comments[0]["id"]
            # a second fixed comment, so that every fixed issue carries comments, not one
            if len(comments) < 2 or comments[1]["message"] != REPLY:
                for c in comments[1:]:
                    self.must(owner, "DELETE", with_org(f"/api/comments/{c['id']}", org))
                self.must(owner, "POST", with_org("/api/comments", org), {"issue": self.ids[issue], "message": REPLY})
            else:
                for c in comments[2:]:
                    self.must(owner, "DELETE", with_org(f"/api/comments/{c['id']}", org))
            self.reset(issue)
            print(
                f"  {issue}: issue {self.ids[issue]} on {job} by {owner}, comment {self.ids[comment_of(issue)]} and a reply"
            )

    def new_issue(self, user: str, org: str | None, job: str, position: list, message: str) -> int:
        body = {"frame": self.frames[job], "job": self.ids[job], "position": position, "message": message}
        return self.must(user, "POST", with_org("/api/issues", org), body)["id"]

    def reset(self, issue: str) -> None:
        org = org_of_issue(issue)
        owner = owner_of(org)
        self.must(owner, "PATCH", with_org(f"/api/issues/{self.ids[issue]}", org), {"resolved": False})
        self.must(
            owner,
            "PATCH",
            with_org(f"/api/comments/{self.ids[comment_of(issue)]}", org),
            {"message": f"fixed issue {issue}"},
        )

    # ---------------------------------------------------------- one action

    def act(self, actor: str, named: str | None, issue: str, action: str) -> tuple[object, int, str]:
        """Runs one action; (outcome, status, what the owner read back), see outcome()."""
        org = org_of_issue(issue)
        owner = owner_of(org)
        job = ISSUES[issue]
        issue_id, comment_id = self.ids[issue], self.ids[comment_of(issue)]
        mark = f"by {actor} as {named or '-'}"
        s = self.sessions[actor]

        def owner_get(path: str) -> tuple[int, object]:
            return send(self.sessions[owner], "GET", with_org(path, org))

        def owner_issues() -> list[dict]:
            return self.pages(owner, with_org("/api/issues", org, job_id=self.ids[job]))[1]

        def owner_comments() -> list[dict]:
            return self.pages(owner, with_org("/api/comments", org, issue_id=issue_id))[1]

        if action == "create issue":
            body = {"frame": self.frames[job], "job": self.ids[job], "position": ACTOR_POSITION, "message": mark}
            status, out = send(s, "POST", with_org("/api/issues", named), body)
            made = [i for i in owner_issues() if i["position"] == ACTOR_POSITION]
            for i in made:
                self.must(owner, "DELETE", with_org(f"/api/issues/{i['id']}", org))
            return outcome(status, len(made) == 1, len(made) == 0), status, f"{len(made)} new issue(s) on the job"
        if action == "view issue":
            status, out = send(s, "GET", with_org(f"/api/issues/{issue_id}", named))
            return outcome(status, status == 200 and out.get("id") == issue_id, status >= 300), status, ""
        if action == "update issue":
            status, _ = send(s, "PATCH", with_org(f"/api/issues/{issue_id}", named), {"resolved": True})
            resolved = owner_get(f"/api/issues/{issue_id}")[1]["resolved"]
            self.reset(issue)
            return outcome(status, resolved is True, resolved is False), status, f"resolved={resolved}"
        if action == "delete issue":
            victim = self.new_issue(owner, org, job, THROWAWAY_POSITION, f"throwaway for {mark}")
            status, _ = send(s, "DELETE", with_org(f"/api/issues/{victim}", named))
            left = owner_get(f"/api/issues/{victim}")[0]
            if left == 200:
                self.must(owner, "DELETE", with_org(f"/api/issues/{victim}", org))
            return outcome(status, left == 404, left == 200), status, f"owner reads it: {left}"
        if action == "create comment":
            status, _ = send(s, "POST", with_org("/api/comments", named), {"issue": issue_id, "message": mark})
            made = [c for c in owner_comments() if c["message"] == mark]
            for c in made:
                self.must(owner, "DELETE", with_org(f"/api/comments/{c['id']}", org))
            return outcome(status, len(made) == 1, len(made) == 0), status, f"{len(made)} new comment(s)"
        if action == "view comment":
            status, out = send(s, "GET", with_org(f"/api/comments/{comment_id}", named))
            return outcome(status, status == 200 and out.get("id") == comment_id, status >= 300), status, ""
        if action == "update comment":
            status, _ = send(s, "PATCH", with_org(f"/api/comments/{comment_id}", named), {"message": f"edited {mark}"})
            edited = owner_get(f"/api/comments/{comment_id}")[1]["message"] == f"edited {mark}"
            self.reset(issue)
            return outcome(status, edited, not edited), status, f"edited={edited}"
        if action == "delete comment":
            victim = self.must(
                owner, "POST", with_org("/api/comments", org), {"issue": issue_id, "message": "throwaway"}
            )
            status, _ = send(s, "DELETE", with_org(f"/api/comments/{victim['id']}", named))
            left = owner_get(f"/api/comments/{victim['id']}")[0]
            if left == 200:
                self.must(owner, "DELETE", with_org(f"/api/comments/{victim['id']}", org))
            return outcome(status, left == 404, left == 200), status, f"owner reads it: {left}"
        raise AssertionError(action)

    def listing(self, actor: str, named: str | None, kind: str) -> tuple[object, int, str]:
        """(fixed objects listed or REFUSED, status, note); fails when a listed object is not of
        the named organization."""
        status, rows = self.pages(actor, with_org(f"/api/{kind}", named))
        if status != 200:
            return (REFUSED if status == REFUSAL_STATUS else f"error {status}"), status, ""
        listed = {r["id"] for r in rows}
        keys = list(ISSUES) if kind == "issues" else [comment_of(i) for i in ISSUES]
        got = {k for k in keys if self.ids[k] in listed}
        # anything of the layout that belongs to an organization other than the named one; with
        # none named, the list spans the caller's organizations and only the fixed ones are judged
        named_jobs = self.org_jobs.get(named, set())
        known_jobs = set().union(*self.org_jobs.values())
        if not named:
            foreign = []
        elif kind == "issues":
            foreign = [r["id"] for r in rows if r["job"] in known_jobs - named_jobs]
        else:
            other = {self.ids[i] for i in ISSUES if org_of_issue(i) != named}
            foreign = [r["id"] for r in rows if r["issue"] in other]
        note = f"{len(rows)} listed" + (f", outside the named organization: {foreign}" if foreign else "")
        return (got if not foreign else f"{fmt(got)} and foreign {foreign}"), status, note

    # ---------------------------------------------------------- the matrix

    def run(self, out_file: str) -> None:
        self.set_roles()
        self.layout()
        results = []
        failures = 0
        print("matrix (expected / seen, HTTP status, owner's read-back):")
        for actor, named, issue, allowed, _ in ACTION_ROWS:
            for action in ACTIONS:
                want = action in allowed
                got, status, note = self.act(actor, named, issue, action)
                ok = got == want
                failures += not ok
                results.append(
                    {
                        "actor": actor,
                        "org": named,
                        "target": issue,
                        "action": action,
                        "expected": want,
                        "allowed": got,
                        "status": status,
                        "read_back": note,
                        "pass": ok,
                    }
                )
                print(
                    f"  {'ok  ' if ok else 'FAIL'} {actor:16} org={named or '-':9} {action:15} {issue}: "
                    f"{SHOWN[want]} / {SHOWN.get(got, 'INCONSISTENT')} {status} {note}"
                )
        for actor, named, expected, _ in LIST_ROWS:
            for kind in ("issues", "comments"):
                want = list_expectation(expected, kind)
                got, status, note = self.listing(actor, named, kind)
                ok = got == want
                failures += not ok
                results.append(
                    {
                        "actor": actor,
                        "org": named,
                        "action": f"list {kind}",
                        "expected": fmt(want),
                        "listed": fmt(got),
                        "status": status,
                        "note": note,
                        "pass": ok,
                    }
                )
                print(
                    f"  {'ok  ' if ok else 'FAIL'} {actor:16} org={named or '-':9} list {kind:9}: "
                    f"{fmt(want)} / {fmt(got)} {status} {note}"
                )
        Path(out_file).write_text(json.dumps({"ids": self.ids, "results": results}, indent=2) + "\n")
        if failures:
            raise SystemExit(f"issue matrix: {failures} of {len(results)} rows differ from the expectations")
        print(f"issue matrix passed: {len(results)} rows")


def main() -> None:
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "live":
        Live().run(args[1])
    elif args == ["opa-cases"]:
        json.dump(opa_cases(), sys.stdout)
    elif len(args) == 2 and args[0] == "opa-judge" and args[1] in ("patched", "stock"):
        opa_judge(args[1])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
