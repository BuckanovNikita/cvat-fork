# Team Analytics inside the CVAT backend, in a full-source fork

Status: ready-for-agent

Vocabulary follows [`GLOSSARY.md`](../../GLOSSARY.md). The two structural decisions are
[ADR 0005](../../docs/adr/0005-a-full-source-fork-joined-to-upstream-history.md) (the
repository is a full-source fork, joined to upstream by one merge) and
[ADR 0006](../../docs/adr/0006-team-analytics-inside-the-backend-with-reads-on-a-worker.md)
(the feature lives in the backend and its queries run on a worker of their own). Both were
decided by the owner on 2026-11-15. Earlier decisions and what became of them are in
[`decisions-ledger.md`](decisions-ledger.md); the first draft of this work, dropped on
2026-11-14, is in history up to commit `fb3148e`.

The figures, their rules and the page do not change. What changes is where the code runs,
who checks access, and how the repository relates to upstream.

## Problem Statement

- The owner asked at the start for "possibly a dedicated backend endpoint" and got a separate
  service, because the backend was not in the repository. The service carries what a backend
  endpoint gets for free: its own access check built on three calls to CVAT, a cache of
  CVAT's answers that keeps a removed member in for a minute, an HTTP server, a lease kept in
  ClickHouse, an image, manifests, a proxy route and an Ingress.
- The repository is a filtered copy of upstream. An upgrade means a mirror, a filter, a
  subtree pull and a separate source for whatever the filter left out. Upstream's backend
  tests and policy tests cannot run on it.
- Merged into the backend naively, the analytical queries would run inside CVAT's API
  server, which the Helm chart runs as one process per pod. The owner's standing rule is
  that a failure of the feature must not break core functions.

## Solution

The repository becomes upstream's tree with the fork's changes on top, and an upgrade is a
merge of a release tag.

Team Analytics becomes a backend app. The page asks CVAT's own API; CVAT's permission system
decides who may read, on every request. The API server never queries ClickHouse for the
feature: it answers from a cache, and on a miss hands the read to a dedicated analytics
worker and tells the client to retry if the answer is not ready within a few seconds. The
same worker refreshes the stored totals. If the worker, ClickHouse or the totals are
unavailable, the Team Analytics page shows its error panel and the rest of CVAT is
unaffected.

## User Stories

Numbered for reference from tickets.

Access

1. As an owner or maintainer, I see my organization's figures and no other organization's.
2. As an administrator, I see the organization I selected, or the whole instance when none is
   selected.
3. As a supervisor, worker or outsider, I am refused, in an organization and outside one.
4. As a member who was removed, I am refused on my next request, not a minute later.
5. As an owner or maintainer with no organization selected, I am told to select one.
6. As anyone signed out, I am told to sign in.

Figures

7. As a reader of the page, every figure is what it was before the move, for the same events:
   the calculation tests that passed on the service pass on the backend.
8. As a reader, a period that is not fully processed still carries no figures, also when I
   call the API directly.
9. As a reader, the first answer after a fresh start already knows the cutover.

Not slowing CVAT down

10. As an annotator, opening and saving a job, the task list and signing in are as fast while
    others load Team Analytics as when nobody does.
11. As an annotator, CVAT works when the analytics worker is stopped, when ClickHouse is
    stopped and when the totals database is missing.
12. As an operator who runs CVAT without analytics, the feature is absent: no endpoints, no
    worker, no scheduled job.
13. As a reader of the page, I get figures, not an error panel, when a dozen people open the
    page at once.
14. As a reader, a view I have already loaded comes back at once until the totals change.

Operating it

15. As an operator, I deploy two images, the UI and the fork server image; the analytics
    worker is a Deployment of the chart.
16. As an operator, a worker that dies in the middle of a refresh holds refreshes up for two
    minutes at most.
17. As a maintainer of the fork, I upgrade by merging a release tag, and the fork's changes to
    upstream files are a short list I can read with `git diff`.
18. As a maintainer of the fork, one command runs the checks, on the fork's files only.

## Implementation Decisions

Repository

- One merge commit joins the overlay's `main` to upstream's `v2.82.0`. Its tree is upstream's
  tree with the fork's own files added. The fork's 80 changed files of the old import (61 new,
  19 edited) are then replayed at upstream's paths, byte for byte, as three commits.
- Upstream's `README.md` is left alone; the fork's is `README.fork.md`. The fork's entries are
  appended to upstream's `.gitignore`. Upstream's `.github/` is removed.
- The work stays on v2.82.0 throughout, so that equality of trees proves the conversion.
- Nothing is pushed, and `main` is not moved, without the owner's word.

The app

- `cvat/apps/team_analytics/`, installed only when analytics is enabled (its queue is defined
  everywhere, so that switching analytics off removes the stored refresh schedule). No Django models, no
  migrations, no signal handlers.
- **Core.** Today's calculation code (periods, rows, the withholding rule, the SQL runner, the
  cutover, history, refresh, the prioritised step, the five endpoints and their sections) and
  the SQL files move in unchanged and stay free of Django, so the calculation tests run on
  them as before.
- **Endpoints.** `GET /api/team-analytics/{status,overview,trends,list,details}`. Parameters
  and answers are those of the service. Errors: 400 for a bad parameter, 401 signed out, 403
  refused, 403 with the body `{"error": "organization_required"}` for story 5, 404 for an
  unknown organization, 429 with `Retry-After` when the answer is not ready, 503 when the
  read failed. Answers are never cached by the browser.
- **Access.** A policy file and a permission class on upstream's base class. Administrators
  (the admin group, as upstream derives it) are always allowed. In an organization, owners
  and maintainers are allowed. Everyone else is refused. The view turns CVAT's context into
  the core's scope: an administrator without an organization gets instance scope.
- **Reads.** The API process keeps the parameters an endpoint reads and builds a key from the
  endpoint, the scope, the parameters and the hour. The worker stores each answer under that key
  with the generation of the totals it was computed on. A stored answer is returned while its
  generation is the current one. Otherwise the read is queued on the `team_analytics` queue under
  that key (one job per key), unless the queue is already too deep; the request waits up to a
  configured time (default 5 s; 0 means do not wait) for an answer computed since it arrived, and
  answers 429 if none has come. What a parameter means is checked by the worker; a parameter an
  endpoint refuses is a stored 400. The API process imports nothing that connects to ClickHouse.
- **Worker.** A Deployment of the fork server image running `run worker team_analytics`, with
  several processes (default 3). A read job computes the answer through the core and stores
  it. Each statement of a read has a time and a memory limit; the job has a timeout.
- **Refresh.** A periodic job on the same queue, every minute. It takes a Redis lock without
  waiting; with the lock it runs the core's prioritised step again and again while there is
  work, within a time budget, proving before every write that it still holds the lock and
  extending it. At the end of a run that wrote, it advances the generation of the totals. A run ends after a step as
  soon as a read is waiting in the queue: reads come before history. Schema
  set-up and the first cutover search run inside the job when it finds them missing, and a
  read that arrives first triggers them.
- **Settings.** The technical accounts, the refresh interval and window, the look-back, the
  totals database name, the read wait, the queue depth limit and the limits of a statement
  are Django settings with defaults in the app, overridable from the environment. ClickHouse
  access is CVAT's own setting.
- **Upstream files edited:** `cvat/settings/base.py` (the app, the queue and the periodic job,
  all behind the analytics flag) and `cvat/urls.py` (one include), each by appended lines. New
  files in upstream directories: the app, one component file for the entry point, and one chart
  template, whose values have their defaults in the template so that upstream's `values.yaml` is
  not edited.

The page

- `service.ts` keeps its single boundary and calls `core.server.request`. The organization is
  attached by cvat-core. A 404 reads as "not available"; a 429 that outlives the client's
  retries reads as the error panel.

Images and the stack

- The fork server image is the stock release with the fork's `cvat/` tree and the component
  file copied over it. The build refuses when the fork's tree differs from the release in
  the requirements, the entry point or the process configuration.
- The Team Analytics service image, its manifests, the proxy route and the Ingress are
  removed.

## Testing Decisions

- **Calculations** (the service's suite, seam 1): the same tests, entering through the core's
  read function, in the same runner: the fork server image and a throwaway ClickHouse, now
  with a throwaway Redis for the lock. They move to `verify/team-analytics-backend/`.
- **Lock:** the lease tests are rewritten against the lock's interface: held during a step,
  lost before a write, a dead holder overtaken after the expiry.
- **Access:** upstream's generated policy tests for the new rule, and the stack's matrix on
  real accounts for every role and endpoint.
- **Read path:** unit tests of the key, the cache, the queue depth limit and the wait, with
  the cache and the queue supplied; a test that the view, permission and read modules import
  with `clickhouse_connect` unavailable.
- **Page and logging** (seams 2 and 3): unchanged suites; the three files that assert request
  addresses follow the new boundary.
- **On the stack**, before the service is deleted: parity, access, isolation and load, as the
  acceptance ticket lists them.
- The move of the core is a commit that only moves; formatting to upstream's black and isort
  settings is a commit of its own, with the suite rerun.
- Prior art: `cvat/apps/log_viewer` and `cvat/apps/events` for the permission class and
  policy, `cvat/apps/engine/cache.py` for queue-and-wait, `cvat/apps/access_tokens` for app
  settings and a periodic job.

## Out of Scope

- A newer upstream release.
- Running upstream's Django and REST suites. Its REST test for issues
  (`tests/python/rest_api/test_issues.py`) disagrees with the patched policies until an
  upgrade gate takes that on; its Kubernetes mode flushes databases in whatever namespace
  the current kube context names.
- Compose. Upstream's Compose files are left as they are and do not start the analytics
  worker.
- Production. It is air-gapped and was put out of scope by the owner.
- Moving UI wiring into upstream's plugin slots; delivering the last input summary on tab
  close.
- Any change to what is measured or how it is counted.

## Further Notes

Defaults chosen without asking the owner, each to be changed on their word: upstream's
`README.md` is kept and ours renamed; upstream's `.github/` is removed; the endpoints are
left out of the published schema; the wait is 5 s and the worker runs 3 processes; an
administrator without an organization means instance scope.

Limits that stay as they are: figures are self-reported and any account can move the
cutover (issue 19 of `.scratch/team-analytics/`); the app uses the chart's ClickHouse
account, which can write CVAT's events table; stored hours are not recounted when a rule
changes.
