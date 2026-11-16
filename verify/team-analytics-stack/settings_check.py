"""The Team Analytics settings on the stack (/api/team-analytics/settings, settings/users, project-names), driven by
run.sh check-settings, part of up. Each part judges itself and prints `[settings] PASS` or `FAIL`; every part runs,
the list is put back as the seed set it, and the command exits non-zero when a part failed.

    settings_check.py check SECS GONE   SECS: how long to wait for the probe's work to reach the figures; GONE: a
                                        throwaway user run.sh has just created, which the deleted-account part
                                        deletes

Parts:
  refusals        an owner, a maintainer and a worker get 403 on GET and PUT settings, GET settings/users and GET
                  project-names, with and without their organization; signed out is 401; the refused PUTs send a
                  changed list (the seeded one plus ta-outsider), and the list read back is still the seeded one
  writes          no-store on every settings answer; a PUT with the session cookie and its CSRF token saves, one
                  without the token and one with a read-only access token are refused (both sending a changed
                  list, the list unchanged); status, settings, settings/users and project-names with .json
                  are 404 for the administrator, the plain paths 200; HEAD on status and settings answers 200
                  with no body; the server's log, read whole and not empty, never names the removed variable
  bad-bodies      PUT settings refuses (400 bad_request) a non-list, a missing list, a negative id, zero, a
                  duplicate, an id of no user that is not on the list, and a body sent as text/plain or as
                  application/x-www-form-urlencoded (not 415); neither the list nor the answer generation changes
  generation      every save advances the answer generation by exactly one, a save of the same list too (it
                  answers 200 and keeps the list)
  user-search     with an organization selected, the search finds a user of another organization and a user of
                  none, answers at most 20 users ordered by username, and refuses a search over 150 characters
  project-names   names projects of two organizations in one answer and leaves out an unknown id; refuses a bad id
                  and more than 500 ids
  deleted-user    a listed user deleted by the administrator stays listed (deleted, its last name), a save that
                  keeps its id is accepted, one without it removes it, and adding it again is refused
  retroactive     ta-worker-s's job work this week in ta-org-s (made once per stack: 10 minutes and PROBE_BOXES
                  boxes saved through the API, beside ta-worker-s2's 5 minutes) leaves the people figures when the
                  account joins the list: no longer an annotator, its working time and sessions gone, its saved
                  boxes counted as Model for its project, the list's count up by one; removed again, every figure is
                  as before

The generation is read from Django's cache in the server pod (stack_ops.generation); while it is measured the
analytics worker is at zero, so no refresh run moves it meanwhile (a run advances it when it ends, after its last
step has let the refresh lock go, so holding that lock would not be enough), and it is brought back after.

Environment: TA_BASE_URL, TA_SEED_PASSWORD, TA_KUBE_CONTEXT, TA_NAMESPACE, TA_RELEASE. Standard library only.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run with python3 -I, which leaves it out

from stack_api import (  # noqa: E402
    API,
    BASE_URL,
    SETTINGS,
    USER_SEARCH,
    Session,
    admin_session,
    create_jobs,
    figures,
    find_user,
    owner_of,
    reader,
    refusal,
    send,
    send_full,
    send_work,
    technical_accounts,
)
from stack_ops import RELEASE, WORKER, WORKER_SELECTOR, generation, kubectl, scale  # noqa: E402

PROJECT_NAMES = API + "project-names"
SERVER_SELECTOR = f"app.kubernetes.io/instance={RELEASE},tier=backend,component=server"
PROBE_ORG = "ta-org-s"
PROBE = "ta-worker-s"  # joins the list and leaves it again
PROBE_PEER = "ta-worker-s2"  # stays an annotator, so the figures do not drop to nothing
PROBE_WORK = {PROBE: 10, PROBE_PEER: 5}  # minutes; below ta-solo's 20, so check-tracer's leading instance rows hold
PROBE_BOXES = 4
PROBE_PROJECT = "ta-settings-probe"
UNKNOWN_ID = 2_000_000_000  # no user and no project has it
SEARCH_LIMIT = 20
SEARCH_MAX = 150
# the sentence of cvat/apps/team_analytics/technical_accounts.py clean_account_ids
NEGATIVE_DETAIL = "every technical account must be a user id: a positive integer"
TOKEN_NAME = "ta-stack-settings-read-only"


class Failed(Exception):
    pass


def log(message: str) -> None:
    print(f"  {message}", flush=True)


def need(condition: bool, message: str) -> None:
    if not condition:
        raise Failed(message)


def with_org(path: str, org: str) -> str:
    return path + ("&" if "?" in path else "?") + urllib.parse.urlencode({"org": org})


def ids_of(listing: list[dict]) -> list[int]:
    return sorted(row["user_id"] for row in listing)


def put(session: Session, ids: object) -> tuple[int, object]:
    return session.send("PUT", SETTINGS, {"technical_accounts": ids})


def save(admin: Session, ids: list[int]) -> list[dict]:
    status, body = put(admin, ids)
    need(status == 200 and isinstance(body, dict) and isinstance(body.get("technical_accounts"), list),
         f"PUT settings {ids}: {status} {str(body)[:300]}, expected 200 with the list")
    need(ids_of(body["technical_accounts"]) == sorted(ids),
         f"PUT settings {ids} answered the list {ids_of(body['technical_accounts'])}")
    return body["technical_accounts"]


def raw_request(session: Session, method: str, path: str, data: bytes | None = None,
                content_type: str | None = None) -> tuple[int, str, dict]:
    """One request of the session as it is sent, body bytes and Content-Type included (send_full always sends JSON):
    (status, body text, response headers with lower-case names). A write carries the session's Origin and CSRF
    token, so its answer is the view's and not CSRF's."""
    request = urllib.request.Request(BASE_URL + path, data=data, method=method)
    if content_type:
        request.add_header("Content-Type", content_type)
    if method not in ("GET", "HEAD"):
        request.add_header("Origin", BASE_URL)
        request.add_header("X-CSRFTOKEN", session._csrf())
    try:
        with session.opener.open(request, timeout=60) as response:
            status, text, got = response.status, response.read().decode(), response.headers
    except urllib.error.HTTPError as error:
        status, text, got = error.code, error.read().decode(), error.headers or {}
    return status, text, {name.lower(): value for name, value in got.items()}


def body_refusal(status: int, text: str) -> str | None:
    """refusal() of a raw answer's text."""
    try:
        return refusal(status, json.loads(text) if text.strip() else None)
    except ValueError:
        return f"unexpected {text[:200]}"


def user_id(session: Session, username: str) -> int:
    found = find_user(session, username)
    need(found is not None, f"no user {username} (run.sh seed)")
    return found


def restore_worker(failure: BaseException | None) -> None:
    """The analytics worker back at one replica. When that fails as well, the failure that led here is printed
    first, then the restore's, and both stop the check, so the restore never hides the original failure."""
    try:
        scale(WORKER, 1, WORKER_SELECTOR)
    except BaseException as restore:
        if failure is not None:
            print(f"[settings] FAIL: {failure}", flush=True)
        print(f"[settings] FAIL: scaling the analytics worker back to 1 failed: {restore}", flush=True)
        raise SystemExit(f"[settings] FAIL: {failure or 'no failure before'}; then scaling the analytics worker back "
                         f"to 1 failed: {restore} (kubectl scale {WORKER} --replicas=1)") from None


class WorkerStopped:
    """The analytics worker at zero while the generation is measured. A refresh run advances the generation once
    when it ends, after its last step has released the refresh lock (core/run.py), so holding that lock does not
    keep a run that started earlier from advancing it; with no worker no run ends. The settings are answered by
    the API process, not by the worker. Back up, it waits until status is answered again."""

    def __enter__(self) -> WorkerStopped:
        try:
            scale(WORKER, 0, WORKER_SELECTOR)
        except BaseException as failure:
            # __exit__ does not run when __enter__ fails: the worker is brought back here
            restore_worker(failure)
            raise
        log("analytics worker at 0 while the generation is measured")
        return self

    def __exit__(self, kind: object, failure: BaseException | None, trace: object) -> None:
        restore_worker(failure)
        started = time.monotonic()
        while True:
            status, body = reader("").call(API + "status?tz=UTC")
            if status == 200 and isinstance(body, dict) and body.get("refresh") is not None:
                break
            if time.monotonic() - started > 300:
                raise Failed(f"status not answered within 300 s after the worker came back: {status} {body}")
            time.sleep(2)
        log(f"analytics worker at 1; status answered after {time.monotonic() - started:.0f} s")


# ---------------------------------------------------------------- parts


def changed_list(admin: Session, base: list[int]) -> list[int]:
    """The seeded list plus ta-outsider (a real user, never technical): what a refused PUT sends, so that a save
    accepted by mistake would show in the list read back."""
    extra = user_id(admin, "ta-outsider")
    need(extra not in base, f"ta-outsider is already on the seeded list {base}")
    return [*base, extra]


def refusals(admin: Session, base: list[int]) -> str:
    changed = changed_list(admin, base)
    requests = [
        ("GET", SETTINGS, None),
        ("PUT", SETTINGS, {"technical_accounts": changed}),
        ("GET", USER_SEARCH + "?search=ta-", None),
        ("GET", PROJECT_NAMES + "?ids=1", None),
    ]
    seen = 0
    for username, org in (("ta-owner", "ta-org-a"), ("ta-maintainer", "ta-org-a"), ("ta-worker", "ta-org-a")):
        session = Session(username)
        for method, path, body in requests:
            for scoped in (path, with_org(path, org)):
                status, answer = session.send(method, scoped, body)
                need((status, refusal(status, answer)) == (403, "forbidden"),
                     f"{username} {method} {scoped}: {status} {str(answer)[:200]}, expected 403 forbidden")
                seen += 1
        log(f"{username}: 403 forbidden on {len(requests) * 2} requests (with and without {org})")
    anonymous = urllib.request.build_opener()
    for method, path, body in requests:
        status, answer = send(anonymous, method, path, body)
        need((status, refusal(status, answer)) == (401, "not_authenticated"),
             f"signed out {method} {path}: {status} {str(answer)[:200]}, expected 401 not_authenticated")
    log(f"signed out: 401 on {len(requests)} requests")
    after = ids_of(technical_accounts(admin))
    need(after == sorted(base), f"the list after the refused saves is {after}, expected {sorted(base)}")
    return f"{seen} requests of three accounts refused 403, {len(requests)} signed out 401, the list unchanged {after}"


def bad_bodies(admin: Session, base: list[int]) -> str:
    known = base[0] if base else user_id(admin, "ta-outsider")
    bodies = {
        "a number": {"technical_accounts": 12},
        "a string": {"technical_accounts": "ta-bot"},
        "no list": {},
        "a negative id": {"technical_accounts": [*base, -5]},
        "zero": {"technical_accounts": [*base, 0]},
        "a duplicate": {"technical_accounts": [*base, known] if base else [known, known]},
        "an id of no user, not on the list": {"technical_accounts": [*base, UNKNOWN_ID]},
    }
    with WorkerStopped():
        before = generation()
        for what, body in bodies.items():
            status, answer = admin.send("PUT", SETTINGS, body)
            need(status == 400 and refusal(status, answer) == "bad_request",
                 f"PUT settings with {what} {body}: {status} {str(answer)[:200]}, expected 400 bad_request")
            log(f"{what}: 400 {answer.get('detail') if isinstance(answer, dict) else answer}")
            if what == "a negative id":
                need(answer.get("detail") == NEGATIVE_DETAIL,
                     f"a negative id: detail {answer.get('detail')!r}, expected {NEGATIVE_DETAIL!r}")
        # a body that is not JSON: the view's own 400, not DRF's 415; each would save a changed list if accepted
        changed = changed_list(admin, base)
        not_json = {
            "text/plain": json.dumps({"technical_accounts": changed}).encode(),
            "application/x-www-form-urlencoded": urllib.parse.urlencode(
                [("technical_accounts", i) for i in changed]).encode(),
        }
        for content_type, data in not_json.items():
            status, text, _ = raw_request(admin, "PUT", SETTINGS, data, content_type)
            need(status == 400 and body_refusal(status, text) == "bad_request",
                 f"PUT settings as {content_type}: {status} {text[:200]}, expected 400 bad_request (not 415)")
            log(f"{content_type}: 400 {text[:120]}")
        after = generation()
    listed = ids_of(technical_accounts(admin))
    need(listed == sorted(base), f"the list after the refused saves is {listed}, expected {sorted(base)}")
    need(after == before, f"the answer generation moved from {before} to {after} over refused saves")
    return (f"{len(bodies)} bad bodies and {len(not_json)} bodies that are not JSON refused 400 bad_request; the list "
            f"{listed} and the generation {before} unchanged")


def writes(admin: Session, base: list[int]) -> str:
    """How the settings answer and what a write needs: `Cache-Control: no-store` on every settings answer (200,
    400 and 403 alike); a PUT with the session cookie and its X-CSRFToken saves, one without the token is refused
    by CSRF under session authentication; an administrator's read-only access token reads the settings and is
    refused on PUT. The server's log has no warning about TEAM_ANALYTICS_TECHNICAL_ACCOUNTS, which the stack no
    longer sets (the app warns only when it is set)."""
    answers = {
        "GET settings": send_full(admin.opener, "GET", SETTINGS),
        "PUT settings (cookie and X-CSRFToken)": send_full(admin.opener, "PUT", SETTINGS, {"technical_accounts": base},
                                                           admin._csrf()),
        "GET settings/users": send_full(admin.opener, "GET", USER_SEARCH + "?search=ta-"),
        "GET project-names": send_full(admin.opener, "GET", PROJECT_NAMES + "?ids=1"),
        "PUT settings refused (400)": send_full(admin.opener, "PUT", SETTINGS, {"technical_accounts": [-5]},
                                                admin._csrf()),
        "GET settings by a maintainer (403)": send_full(Session("ta-maintainer").opener, "GET", SETTINGS),
    }
    want = {name: (400 if "400" in name else 403 if "403" in name else 200) for name in answers}
    seen = {name: (status, headers.get("cache-control")) for name, (status, _, headers) in answers.items()}
    log(f"(status, Cache-Control): {seen}")
    need(all(seen[n] == (want[n], "no-store") for n in answers),
         f"settings answers (status, Cache-Control) {seen}, expected each status {want} with no-store")
    need(ids_of(answers["PUT settings (cookie and X-CSRFToken)"][1]["technical_accounts"]) == sorted(base),
         "the PUT with the CSRF token answered another list")

    # the session cookie without its CSRF token: Origin sent, X-CSRFToken not; a changed list, so a wrong save shows
    changed = changed_list(admin, base)
    status, answer, _ = send_full(admin.opener, "PUT", SETTINGS, {"technical_accounts": changed},
                                  headers={"Origin": BASE_URL})
    detail = answer.get("detail", "") if isinstance(answer, dict) else str(answer)
    need(status == 403 and "csrf" in str(detail).lower(),
         f"PUT with the session cookie and no X-CSRFToken: {status} {str(answer)[:200]}, expected 403 CSRF Failed")
    log(f"PUT without X-CSRFToken: {status} {detail}")

    # a read-only personal access token of the administrator, sent as Bearer without the cookie
    for token in admin.request("GET", "/api/auth/access_tokens?page_size=100")["results"]:
        if token["name"] == TOKEN_NAME:  # left by an interrupted run
            admin.request("DELETE", f"/api/auth/access_tokens/{token['id']}")
    expiry = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    token = admin.request("POST", "/api/auth/access_tokens", {"name": TOKEN_NAME, "read_only": True,
                                                              "expiry_date": expiry})
    try:
        bare = urllib.request.build_opener()
        bearer = {"Authorization": f"Bearer {token['value']}"}
        read_status, read_body, _ = send_full(bare, "GET", SETTINGS, headers=bearer)
        put_status, put_body, _ = send_full(bare, "PUT", SETTINGS, {"technical_accounts": changed}, headers=bearer)
    finally:
        admin.request("DELETE", f"/api/auth/access_tokens/{token['id']}")
    log(f"read-only token: GET settings {read_status}, PUT settings {put_status} {str(put_body)[:120]}")
    need(read_status == 200, f"GET settings with the administrator's read-only token: {read_status} {str(read_body)[:200]}")
    need(put_status == 403, f"PUT settings with the administrator's read-only token: {put_status} {str(put_body)[:200]}, "
                            "expected 403")
    need(ids_of(technical_accounts(admin)) == sorted(base), "a refused PUT changed the list")

    # no format-suffix routes: each path with .json is 404 for the administrator (once routed, it answered 500),
    # while the plain path answers 200
    plain = {"status": API + "status?tz=UTC", "settings": SETTINGS, "settings/users": USER_SEARCH + "?search=ta-",
             "project-names": PROJECT_NAMES + "?ids=1"}
    suffixed = {"status": API + "status.json?tz=UTC", "settings": SETTINGS + ".json",
                "settings/users": USER_SEARCH + ".json?search=ta-", "project-names": PROJECT_NAMES + ".json?ids=1"}
    routes = {}
    for name in plain:
        status_plain, _ = admin.call(plain[name])
        status_json, text, _ = raw_request(admin, "GET", suffixed[name])
        routes[name] = (status_plain, status_json)
        need(status_plain == 200 and status_json == 404,
             f"{name}: GET {plain[name]} {status_plain}, GET {suffixed[name]} {status_json} {text[:150]}; expected 200 "
             "and 404")
    log(f"(plain path, .json path) by endpoint: {routes}")

    # HEAD answers as GET does: 200 and no body (status may be "not ready yet" for a moment: asked again then)
    heads = {}
    for name in ("status", "settings"):
        status_get, _ = admin.call(plain[name])
        started = time.monotonic()
        while True:
            status_head, text, _ = raw_request(admin, "HEAD", plain[name])
            if status_head != 429 or time.monotonic() - started > 30:
                break
            time.sleep(1)
        heads[name] = (status_get, status_head, len(text))
        need(status_get == 200 and status_head == 200 and text == "",
             f"{name}: GET {status_get}, HEAD {status_head} with {len(text)} bytes of body; expected 200 and 200 with none")
    log(f"(GET, HEAD, HEAD body bytes): {heads}")

    server_log = kubectl("logs", "-l", SERVER_SELECTOR, "-c", "cvat-backend", "--tail=-1", "--max-log-requests=10")
    need(server_log.strip() != "", "the server's log came back empty: the warning cannot be looked for")
    warned = [line for line in server_log.splitlines() if "TEAM_ANALYTICS_TECHNICAL_ACCOUNTS" in line]
    need(not warned, f"the server's log names TEAM_ANALYTICS_TECHNICAL_ACCOUNTS although the stack no longer sets it: "
                     f"{warned[:3]}")
    return ("no-store on 200, 400 and 403 of the settings; PUT with the cookie and X-CSRFToken 200, without the token "
            f"403 CSRF; the read-only token reads (200) and is refused on PUT ({put_status}); .json paths 404 and plain "
            "paths 200; HEAD on status and settings 200 with no body; no warning about the removed variable in the "
            "server's log")


def generation_steps(admin: Session, base: list[int]) -> str:
    extra = user_id(admin, "ta-outsider")  # does no job work: no figure moves
    need(extra not in base, f"ta-outsider is already on the seeded list {base}")
    try:
        with WorkerStopped():
            g0 = generation()
            save(admin, [*base, extra])
            g1 = generation()
            same = save(admin, [*base, extra])
            g2 = generation()
            save(admin, base)
            g3 = generation()
    finally:
        if ids_of(technical_accounts(admin)) != sorted(base):
            save(admin, base)
    log(f"generation: {g0} -> add ta-outsider -> {g1} -> the same list again -> {g2} -> removed -> {g3}")
    need(isinstance(g0, int), f"no answer generation in the cache ({g0})")
    need(g1 == g0 + 1, f"adding an account moved the generation {g0} -> {g1}, expected exactly one step")
    need(g3 == g2 + 1, f"removing it moved the generation {g2} -> {g3}, expected exactly one step")
    # a save advances the generation whether or not the list changed (docs/fork-specification.md, views.py)
    need(g2 == g1 + 1, f"saving the same list again moved the generation {g1} -> {g2}, expected exactly one step")
    need(ids_of(same) == sorted([*base, extra]), f"the same list saved again answered {ids_of(same)}")
    return (f"every save advanced the generation by one: adding {g0}->{g1}, the same list again {g1}->{g2} (answered "
            f"200, list unchanged), removing {g2}->{g3}")


def user_search(admin: Session) -> str:
    def search(text: str, org: str = "ta-org-a") -> tuple[int, object]:
        return admin.send("GET", with_org(USER_SEARCH + "?" + urllib.parse.urlencode({"search": text}), org))

    found = {}
    for name, where in (("ta-owner-b", "of ta-org-b"), ("ta-outsider", "of no organization")):
        status, body = search(name)
        need(status == 200 and isinstance(body, dict), f"search {name}: {status} {str(body)[:200]}")
        rows = [u for u in body["users"] if u["username"] == name]
        need(len(rows) == 1 and set(rows[0]) == {"id", "username", "first_name", "last_name"},
             f"search {name} with ta-org-a selected: {body['users']}, expected the user {where}")
        found[name] = rows[0]["id"]
    log(f"with ta-org-a selected: ta-owner-b (ta-org-b) and ta-outsider (no organization) found: {found}")
    sizes = {}
    for text in ("", "ta-", "ta-volume-annotator-"):
        status, body = search(text)
        need(status == 200 and isinstance(body, dict), f"search {text!r}: {status} {str(body)[:200]}")
        names = [u["username"] for u in body["users"]]
        need(len(names) <= SEARCH_LIMIT and names == sorted(names),
             f"search {text!r}: {len(names)} users {names[:25]}, expected at most {SEARCH_LIMIT} by username")
        need(all(text.lower() in n.lower() for n in names) or text == "", f"search {text!r} answered {names}")
        sizes[text] = len(names)
    # more than 20 users of the instance carry ta- (accounts.json alone holds fifteen, and the volume's hundred
    # annotators once check-final has run): the answer is cut at 20
    need(sizes["ta-"] == SEARCH_LIMIT and sizes[""] == SEARCH_LIMIT,
         f"rows for an empty search and for 'ta-': {sizes}, expected {SEARCH_LIMIT} (the instance has more)")
    status, body = search("x" * (SEARCH_MAX + 1))
    need(status == 400 and refusal(status, body) == "bad_request",
         f"a search of {SEARCH_MAX + 1} characters: {status} {str(body)[:200]}, expected 400 bad_request")
    status, body = search("x" * SEARCH_MAX)
    need(status == 200, f"a search of {SEARCH_MAX} characters: {status} {str(body)[:200]}, expected 200")
    log(f"rows by search: {sizes}; {SEARCH_MAX + 1} characters 400, {SEARCH_MAX} characters 200")
    return f"users of another organization and of none found with an organization selected; rows {sizes}; long search refused"


def project_of(org: str, name: str) -> int:
    page = Session(owner_of(org)).request("GET", f"/api/projects?org={org}&name={urllib.parse.quote(name)}")
    need(page["count"] >= 1, f"no project {name} in {org}")
    return page["results"][0]["id"]


def project_names(admin: Session) -> str:
    a, s = project_of("ta-org-a", "ta-tracer"), project_of(PROBE_ORG, PROBE_PROJECT)
    path = with_org(PROJECT_NAMES + f"?ids={a},{s},{UNKNOWN_ID}", "ta-org-a")
    status, body = admin.send("GET", path)
    want = {"names": {str(a): "ta-tracer", str(s): PROBE_PROJECT}}
    need(status == 200 and body == want, f"GET {path}: {status} {body}, expected {want}")
    log(f"project-names with ta-org-a selected: {body}")
    for what, ids in (("a word", "4,x"), ("a negative id", "-4"), ("501 ids", ",".join(str(i) for i in range(1, 502)))):
        status, answer = admin.send("GET", PROJECT_NAMES + "?ids=" + ids)
        need(status == 400 and refusal(status, answer) == "bad_request",
             f"project-names with {what}: {status} {str(answer)[:200]}, expected 400 bad_request")
    status, answer = admin.send("GET", PROJECT_NAMES + "?ids=" + ",".join(str(i) for i in range(1, 501)))
    need(status == 200, f"project-names with 500 ids: {status} {str(answer)[:200]}, expected 200")
    return f"ta-org-a's {a} and {PROBE_ORG}'s {s} named in one answer, {UNKNOWN_ID} left out; bad ids and 501 ids 400"


def deleted_user(admin: Session, base: list[int], gone: str) -> str:
    gone_id = user_id(admin, gone)
    need(gone_id not in base, f"{gone} ({gone_id}) is already on the list {base}")
    try:
        listed = {r["user_id"]: r for r in save(admin, [*base, gone_id])}
        need(listed[gone_id]["user_name"] == gone and listed[gone_id]["deleted"] is False,
             f"{gone} listed as {listed[gone_id]}, expected its name and deleted false")
        status, answer = admin.send("DELETE", f"/api/users/{gone_id}")
        need(status == 204, f"the administrator's DELETE /api/users/{gone_id}: {status} {str(answer)[:200]}")
        need(find_user(admin, gone) is None, f"{gone} is still found by the search after its deletion")
        log(f"{gone} ({gone_id}) added, then deleted by the administrator")
        row = {r["user_id"]: r for r in technical_accounts(admin)}.get(gone_id)
        need(row == {"user_id": gone_id, "user_name": gone, "deleted": True},
             f"GET settings after the deletion lists {row}, expected deleted true with the last name {gone}")
        kept = {r["user_id"]: r for r in save(admin, [*base, gone_id])}.get(gone_id)
        need(kept is not None and kept["deleted"] is True, f"a save keeping the deleted user's id answered {kept}")
        removed = save(admin, base)
        need(gone_id not in ids_of(removed), f"a save without the deleted user still lists it: {removed}")
        status, answer = put(admin, [*base, gone_id])
        need(status == 400 and refusal(status, answer) == "bad_request",
             f"adding the deleted user's id again: {status} {str(answer)[:200]}, expected 400 bad_request")
        need(ids_of(technical_accounts(admin)) == sorted(base), "the refused save changed the list")
        log("listed as deleted with its last name; kept by a save; removed; adding it again 400")
    finally:
        if ids_of(technical_accounts(admin)) != sorted(base):
            save(admin, base)
        if find_user(admin, gone) is not None:
            admin.send("DELETE", f"/api/users/{gone_id}")
    return f"{gone} ({gone_id}) stayed listed after its deletion (deleted, last name), kept, removed, then refused"


def probe_work(timeout_s: int) -> tuple[int, dict]:
    """ta-org-s's probe project (made once per stack) and the overview of its week once the work is in it."""
    owner = Session(owner_of(PROBE_ORG))
    found = owner.request("GET", f"/api/projects?org={PROBE_ORG}&name={PROBE_PROJECT}")
    if found["count"]:
        project = found["results"][0]["id"]
        jobs = owner.request("GET", f"/api/jobs?org={PROBE_ORG}&project_id={project}&page_size=10")["results"]
        need(len(jobs) == len(PROBE_WORK), f"{PROBE_PROJECT} (project {project}) has {len(jobs)} jobs, expected "
                                           f"{len(PROBE_WORK)}: an earlier run stopped half-way; run.sh down and up")
        job = sorted(j["id"] for j in jobs)[0]  # create_jobs assigns the jobs in id order: the first is PROBE's
        log(f"{PROBE_PROJECT} exists in {PROBE_ORG} (project {project}); its working time is already sent")
    else:
        annotators = list(PROBE_WORK)
        jobs = create_jobs(PROBE_ORG, annotators, PROBE_PROJECT)
        project, job = jobs[0]["project_id"], jobs[0]["job_id"]
        for username, ids in zip(annotators, jobs):
            send_work(username, PROBE_ORG, ids, PROBE_WORK[username])
    worker = Session(PROBE)
    if worker.request("GET", f"/api/jobs/{job}/annotations?org={PROBE_ORG}")["shapes"]:
        log(f"{PROBE}'s boxes are saved in job {job}")
    else:
        label = worker.request("GET", f"/api/labels?job_id={job}&org={PROBE_ORG}")["results"][0]["id"]
        shapes = [{"type": "rectangle", "frame": 0, "label_id": label, "points": [1, 1, 3 + i, 3 + i],
                   "occluded": False, "z_order": 0, "attributes": []} for i in range(PROBE_BOXES)]
        worker.request("PATCH", f"/api/jobs/{job}/annotations?action=create&org={PROBE_ORG}",
                       {"shapes": shapes, "tracks": [], "tags": [], "version": 0})
        log(f"{PROBE} saved {PROBE_BOXES} boxes through the API in job {job} of project {project}")
    want = sorted(((u, m * 60_000) for u, m in PROBE_WORK.items()), key=lambda r: -r[1])
    started = time.monotonic()
    while True:
        status, body = overview(project)
        if status == 200 and body.get("processed") and figures(body) == want \
                and (body.get("saved_boxes") or {}).get("boxes") == PROBE_BOXES:
            log(f"the probe's figures after {time.monotonic() - started:.0f} s: {figures(body)}, "
                f"saved boxes {body['saved_boxes']['boxes']}")
            return project, body
        need(time.monotonic() - started < timeout_s,
             f"{PROBE_ORG} week: {status} {figures(body) if status == 200 else body}, saved boxes "
             f"{(body.get('saved_boxes') or {}).get('boxes') if isinstance(body, dict) else None}; expected {want} "
             f"and {PROBE_BOXES} saved boxes (waited {timeout_s} s)")
        time.sleep(5)


def query(endpoint: str, project: int, **extra: str) -> str:
    params = {"tz": "UTC", "org": PROBE_ORG, "period": "week", "shapes": "all", "project": str(project), **extra}
    return API + endpoint + "?" + urllib.parse.urlencode(params)


def overview(project: int) -> tuple[int, dict]:
    return reader(PROBE_ORG).call(query("overview", project))


def annotators_list(project: int) -> tuple[int, dict]:
    return reader(PROBE_ORG).call(query("list", project, by="annotators"))


def people(body: dict) -> dict:
    """The figures the account must leave, and those it must change."""
    by = body["by_annotator"]
    return {
        "annotators": [r["user_name"] for r in by["rows"]],
        "working_time_ms": sum(r["working_time_ms"] for r in by["rows"]) + ((by.get("rest") or {}).get("working_time_ms") or 0),
        "sessions": body["sessions"]["sessions"],
        "session_ms": body["sessions"]["total_ms"],
        "session_rows": [r["user_name"] for r in body["sessions"]["by_annotator"]],
        "headline_annotators": body["headline"]["annotators"],
        "model": body["creation_methods"]["model"]["objects"],
        "technical_accounts": body["creation_methods"]["technical_accounts"],
        "saved_boxes": body["saved_boxes"]["boxes"],
    }


def read_both(project: int, what: str) -> tuple[dict, dict]:
    status, body = overview(project)
    need(status == 200 and body.get("processed"), f"overview {what}: {status} {str(body)[:300]}")
    status, listed = annotators_list(project)
    need(status == 200 and listed.get("processed"), f"list by annotators {what}: {status} {str(listed)[:300]}")
    return body, listed


def retroactive(admin: Session, base: list[int], timeout_s: int) -> str:
    probe_id = user_id(admin, PROBE)
    need(probe_id not in base, f"{PROBE} is on the seeded list {base}")
    project, _ = probe_work(timeout_s)
    before, before_list = read_both(project, "before")
    b = people(before)
    mine = next((r for r in before["sessions"]["by_annotator"] if r["user_name"] == PROBE), None)
    need(PROBE in b["annotators"] and mine is not None and mine["sessions"] >= 1,
         f"{PROBE} is not an annotator with sessions before: {b}")
    listed_before = [r.get("user_name") for r in before_list["rows"]]
    need(PROBE in listed_before, f"{PROBE} not in the list by annotators before: {listed_before}")
    work = next(r["working_time_ms"] for r in before["by_annotator"]["rows"] if r["user_name"] == PROBE)
    log(f"before: {b}; {PROBE}: {work} ms, {mine['sessions']} sessions ({mine['total_ms']} ms)")
    try:
        save(admin, [*base, probe_id])
        after, after_list = read_both(project, f"with {PROBE} on the list")
        a = people(after)
        want = {
            **b,
            "annotators": [n for n in b["annotators"] if n != PROBE],
            "working_time_ms": b["working_time_ms"] - work,
            "sessions": b["sessions"] - mine["sessions"],
            "session_ms": b["session_ms"] - mine["total_ms"],
            "session_rows": [n for n in b["session_rows"] if n != PROBE],
            "headline_annotators": b["headline_annotators"] - 1,
            "model": b["model"] + PROBE_BOXES,  # its saved boxes are Model now (all shapes; they are rectangles)
            "technical_accounts": b["technical_accounts"] + 1,
            # the saved boxes total counts technical accounts too
        }
        listed_after = [r.get("user_name") for r in after_list["rows"]]
        log(f"with {PROBE} on the list: {a}; list by annotators {listed_after}")
        need(a == want, f"with {PROBE} on the list: {a}, expected {want}")
        need(PROBE not in listed_after and PROBE_PEER in listed_after,
             f"list by annotators with {PROBE} on the list: {listed_after}")
    finally:
        save(admin, base)
    # the same reads again: equal to the first, whole answers (a refresh can land in between: read again a few times)
    for attempt in range(4):
        restored, restored_list = read_both(project, f"with {PROBE} removed")
        if (restored, restored_list) == (before, before_list):
            break
        time.sleep(3)
    differs = sorted(k for k in set(before) | set(restored) if before.get(k) != restored.get(k))
    need((restored, restored_list) == (before, before_list),
         f"with {PROBE} removed the answers differ from the first read in {differs} "
         f"(list equal: {restored_list == before_list}): {people(restored)} vs {b}")
    return (f"{PROBE} on the list: not an annotator, -{work} ms working time, -{mine['sessions']} sessions, Model "
            f"+{PROBE_BOXES}, count {b['technical_accounts']}->{b['technical_accounts'] + 1}; removed: the overview "
            f"and the list equal the first read")


def check(timeout_s: int, gone: str) -> None:
    admin = admin_session()
    base = ids_of(technical_accounts(admin))
    log(f"the seeded Technical accounts list: {base}")
    parts = [
        ("refusals", lambda: refusals(admin, base)),
        ("writes", lambda: writes(admin, base)),
        ("bad-bodies", lambda: bad_bodies(admin, base)),
        ("generation", lambda: generation_steps(admin, base)),
        ("user-search", lambda: user_search(admin)),
        ("retroactive", lambda: retroactive(admin, base, timeout_s)),
        ("project-names", lambda: project_names(admin)),
        ("deleted-user", lambda: deleted_user(admin, base, gone)),
    ]
    failed = []
    try:
        for name, run in parts:
            try:
                detail = run()
            except (Failed, SystemExit) as error:
                print(f"[settings] FAIL {name}: {error}", flush=True)
                failed.append(name)
            else:
                print(f"[settings] PASS {name}: {detail}", flush=True)
    finally:
        now = ids_of(technical_accounts(admin))
        if now != base:
            log(f"the list is {now}; putting back the seeded {base}")
            save(admin, base)
    if failed:
        raise SystemExit(f"[settings] FAIL: {', '.join(failed)}")


def main() -> None:
    args = sys.argv[1:]
    if len(args) == 3 and args[0] == "check":
        check(int(args[1]), args[2])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
