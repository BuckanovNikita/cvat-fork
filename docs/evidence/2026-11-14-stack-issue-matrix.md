# Issue and comment matrix on the stack, 2026-11-14

Ticket 09 of the defect fixes (plan row 1.3b, the matrix; the bundle half of that row is
ticket 08's). `verify/team-analytics-stack/run.sh` gains `check_issues`, called from `up` after
the final run, and the subcommands `check-issues` and `check-issue-policies [patched|stock]`.

This file holds part one: what was checked without a running stack. No `up`, `cycle`, `seed`
or `check-issues` ran; no namespace was created, nothing was installed, built or pulled. The
live matrix (part two) is listed at the end and has not run.

## What was added

- `issue_accounts.json`: the matrix's own accounts and organizations, loaded by the stack's
  existing `seed_users.py` (the launcher passes this file as `TA_ACCOUNTS`). `ta-org-i` holds
  `ta-owner-i`, `ta-maintainer-i`, `ta-supervisor-i`, `ta-worker-i` (global role `user`),
  `ta-worker-i2` (global role `worker`, the floor itself) and `ta-norole-i` (organization role
  worker, no global role). `ta-outsider-i` is a member of nothing. `ta-org-j` holds
  `ta-owner-j` and `ta-worker-j`. A separate file and organizations, so that `accounts.json`,
  `stack_api.py seed` (which compares each organization's memberships exactly) and the final
  run's access cases are untouched.
- `issue_matrix.py`: one table of expectations (`ACTION_ROWS`, `LIST_ROWS`), each row with a
  patched and a stock column, read by both the live run and the policy-engine run.
  - `live FILE` sets the global roles, lays out the objects, runs every row through the API,
    judges it and writes the rows to `FILE` (`issue-matrix.json` in the stack's state
    directory). It exits non-zero when any row differs, after printing all of them.
  - `opa-cases` builds the OPA input the server would send for each row, on a synthetic copy
    of the layout; `opa-judge MODE` judges OPA's answers against the column of `MODE`.
- `run.sh check-issue-policies` runs those inputs through the local `openpolicyagent/opa:1.12.2`
  (`--network none --cpus=1`, read-only mount of a temporary directory) against the import's
  four policy files, or with `stock` against those of `cvat-v2.82.0-widened`, as
  `verify/policy_test.sh` does.

## The account with no global role

In v2.82.0 no account comes to exist without a global role by itself: the `post_save` signal
in `cvat/apps/iam/signals.py` adds the default group (`IAM_DEFAULT_ROLE`, `user`) to every
newly created non-superuser account, and the LDAP path also falls back to the default group.
The privilege the policies see is the account's highest-priority group among the IAM roles
(`cvat/apps/iam/middleware.py`), `None` when it has none. Such an account is made by an
administrator removing its groups. The supported means for that are the Django admin form
(`groups` in the user's "Permissions" fieldset) and the REST API: `UserSerializer` has
`groups` as a writable field and its `update` passes it on to the model serializer's (it only
splits off the profile fields); a superuser gets that serializer for any user (others get it
only for themselves); and the `groups` field maps to the `update:permissions` scope, which
`users.rego` allows only an administrator. Saving the account again does not bring the group
back: the signal adds it only on creation.
No management command sets an account's groups: CVAT's own (listed from the image) are
`deleteuser`, data and cache maintenance and Redis jobs, and Django's built-in ones create a
superuser or change a password.

Chosen: `ta-admin` sends `PATCH /api/users/<id>` with `{"groups": []}`, and the account reads
itself back through `/api/users/self` with `groups == []`. The same call gives `ta-worker-i2`
its `worker` group. It is an API call an administrator makes, needs no database access and
reads back through the API. Because `seed_users.py` sets every non-admin account's groups to
`user` each time it runs, `check_issues` sets the roles again after loading the accounts. If
the live run refuses the call, the fallback is `user.groups.clear()` in `manage.py shell`, the
mechanism the seed already uses; it would be recorded as such.

Source read for this: `cvat/apps/iam/{signals,middleware,permissions,admin}.py`,
`cvat/apps/engine/{permissions,serializers,views,models}.py` and `cvat/apps/engine/rules/users.rego`
from the local image `cvat/server:v2.82.0` (copied out of a created, never started container,
removed afterwards). The Python is not in the import.

What `issue_matrix.py live` assumes about the API, read in the same source: a created issue
or comment is answered with the read serializer (`IssueWriteSerializer` and
`CommentWriteSerializer` override `to_representation`), so the answer carries `id`; opening an
issue creates its first comment, owned by the issue's owner; the read serializers carry `job`,
`position`, `resolved` and `owner.username` (issues) and `issue`, `message` (comments); `resolved`
and a comment's `message` are writable on `PATCH` (only `frame`, `job`, the issue's `message`
and the comment's `issue` are write-once); a job carries `start_frame`; the list filters
`job_id` (issues), `issue_id` (comments) and `name` (tasks) exist.

## Layout

| Key | What | Organization |
| --- | --- | --- |
| J1 | job of task `ta-issue-matrix`, assigned to nobody | ta-org-i |
| J2 | second job of the same task, assigned to `ta-norole-i` | ta-org-i |
| JJ | job of task `ta-issue-matrix`, assigned to nobody | ta-org-j |
| I1, I2, IJ | an issue opened by the organization's owner on J1, J2, JJ | as the job |
| C1, C2, CJ | the first comment of each, which opening the issue creates | as the job |
| (reply) | a second comment on each, by the owner | as the job |

The tasks have no project and are owned by the organization's owner. The layout is found or
created on each run (the task by name, the fixed issue by owner and position, its first
comment by id, the reply by its text); leftovers of an interrupted run are deleted and I1, I2, IJ are reset
(unresolved, original comment text), so the matrix repeats on the same stack.

## The matrix

Actions: CI create an issue on the target's job, VI view, UI update (`resolved: true`), DI
delete a throwaway issue the owner opens on that job for the row, CC create a comment on the
target, VC view, UC update the target's fixed comment, DC delete a throwaway comment the owner
adds. The organization named goes as `?org=`; for view, update and delete the server takes the
organization from the object.

| Account | Organization named | Target | Allowed, patched | Allowed, stock |
| --- | --- | --- | --- | --- |
| `ta-worker-i` | ta-org-i | I1 | CI VI UI DI CC VC UC DC | none |
| `ta-worker-i2` | ta-org-i | I1 | CI VI UI DI CC VC UC DC | none |
| `ta-supervisor-i` | ta-org-i | I1 | CI VI UI DI CC VC UC DC | none |
| `ta-maintainer-i` | ta-org-i | I1 | CI VI UI DI CC VC UC DC | CI VI UI DI CC VC UC DC |
| `ta-norole-i` | ta-org-i | I1 | none | none |
| `ta-norole-i` | ta-org-i | I2 | VI VC | VI VC |
| `ta-worker-j` | ta-org-j | I1 | none | none |
| `ta-worker-j` | ta-org-i | I1 | none | none |
| `ta-worker-i` | ta-org-i | IJ | none | none |
| `ta-maintainer-i` | ta-org-i | IJ | none | none |
| `ta-outsider-i` | ta-org-i | I1 | none | none |
| `ta-outsider-i` | none | I1 | none | none |

Lists (`GET /api/issues`, `GET /api/comments`, every page). The comments listed are the fixed
comments of the issues listed. When an organization is named, nothing of the layout from
another organization may appear.

| Account | Organization named | Fixed issues listed, patched | Stock |
| --- | --- | --- | --- |
| `ta-worker-i` | ta-org-i | {I1, I2} | none |
| `ta-worker-i2` | ta-org-i | {I1, I2} | none |
| `ta-supervisor-i` | ta-org-i | {I1, I2} | none |
| `ta-maintainer-i` | ta-org-i | {I1, I2} | {I1, I2} |
| `ta-norole-i` | ta-org-i | {I2} | {I2} |
| `ta-norole-i` | none | {I2} | {I2} |
| `ta-worker-j` | ta-org-j | {IJ} | none |
| `ta-worker-j` | ta-org-i | refused | refused |
| `ta-worker-j` | none | none | none |
| `ta-worker-i` | ta-org-j | refused | refused |
| `ta-worker-i` | none | none | none |
| `ta-outsider-i` | ta-org-i | refused | refused |
| `ta-outsider-i` | ta-org-j | refused | refused |
| `ta-outsider-i` | none | none | none |

How the live run judges a row: allowed is a 2xx answer whose effect the owner reads back
(the new issue or comment exists, `resolved` is true, the edited text is there, the throwaway
is gone, the view returns the object); refused is a 4xx answer other than 401 after which the
owner reads nothing changed. Anything else (a 5xx, a 401, a refusal with an effect, a success
without one) matches neither expectation and fails the row. The status of every row is
printed and kept, so the refusal codes are on record; they are not pinned, because they
cannot be known without the server.

## Checks with supplied boundaries

All without a server: the inputs are what `opa-cases` builds, following the stock server's
input construction as read above.

- `bash -n verify/team-analytics-stack/run.sh`: passes.
- `issue_matrix.py` byte-compiles (`py_compile`, output outside the tree); `ruff check` and
  `ruff format` with the repository's configuration: no findings, formatted.
- `run.sh check-issue-policies patched`: every expectation of the patched column matches the
  import's policies, 124 of 124 (96 action decisions, 28 list decisions).
- `run.sh check-issue-policies stock`: every expectation of the stock column matches the
  policies of `cvat-v2.82.0-widened`, 124 of 124.
- 32 of the 124 decisions differ between the two columns: the 24 actions of the three
  unassigned members at or above the floor, and the lists of those three and of `ta-worker-j`
  in its own organization. The rows of `ta-norole-i` are the same in both, as the floor
  requires. A matrix passing on the patched server therefore could not pass on stock.
- A wrong expectation caught here: the first draft expected `ta-norole-i`'s list with no
  organization named to be empty. OPA gave the staff filter without an organization filter
  (`add_organization_filter` adds none in the personal workspace when no organization is
  named), so stock lists what the caller is staff of in all its organizations: I2 and C2. The
  expectation was corrected to that, in both columns.
- A quirk of the engine found while building the run: with OPA 1.12.2, `with input as c.input`
  inside a comprehension, `c` taken from `data.cases`, gave `false` for inputs that give `true`
  when evaluated alone; binding `i := c.input` first gives the right answer. The query binds
  first, and every decision above came from that query.

## Reuse of the Compose-era scripts

Reused: `seed_users.py` (the stack's account loader, unchanged, fed the matrix's own file),
`stack_api.py`'s `Session` and `upload_images`, and from `verify/opa_issues_check.py` its
matrix. Its seven rows (list the job's issues, read, edit the owner's issue, list the issue's
comments, add a comment, edit the owner's comment, delete an issue the owner opened) are all
in the new matrix (the two lists over the whole organization rather than one job or issue), as
are its techniques: a fresh throwaway issue per delete check, the shared
issue reset to unresolved after each row, and a list counted only when the issue is actually
in it.

Not reused, because they do not fit the stack: `verify/opa_issues_seed.py` runs `docker exec`
into a named Compose container, posts as a superuser `admin` with fixed passwords, writes its
state to `/tmp` and makes its image with `verify/mkimg.py`; `verify/opa_issues_check.py` reads
that state, uses `requests` (not in the standard library; the stack's scripts use none), and
prints a table to read rather than a verdict. Its layout also differs: the issues there are
opened by a superuser, whom the patch does not concern. Both stay in the tree until the
Compose removal (plan row 1.4) decides on them.

## Not verified here

- Anything on a running CVAT: that the admin call removes the groups, that the server builds
  the inputs as `opa-cases` does (the input shapes come from reading the stock image's
  `permissions.py`, not from a captured request), the refusal codes, and the live outcome of
  every row.
- The live code path of `issue_matrix.py live` has not run at all; only its syntax and lint
  are checked.

## Part two, not run

On a stack started by the orchestrator (`run.sh up`, which ends with `check_issues`, or
`run.sh check-issues` on a running, seeded stack):

1. `check_issues` loads `issue_accounts.json`: `seed_users.py` prints the nine accounts and two
   organizations.
2. Global roles: each account prints `groups=` as in `issue_accounts.json`; `ta-norole-i`
   prints `groups=[]`, `ta-worker-i2` `groups=['worker']`. Both organizations' memberships
   print and match.
3. Layout: J1, J2, JJ print with their assignees (J2: `ta-norole-i`), then I1, I2, IJ with
   their first comments and a reply each.
4. The 96 action rows and 28 list rows print as `ok`, each with its status; the last line is
   `issue matrix passed: 124 rows`, and `run.sh` returns 0. Any `FAIL` or `INCONSISTENT` row
   fails the run.
5. Every refused row's status is reviewed. A refusal counts on any 4xx other than 401, so a
   400 or 404 that comes from something other than the policy would pass as a refusal: any
   code other than 403 is explained before the criteria on the no-role account and on other
   organizations are ticked, and the codes seen are then pinned in the matrix.
6. A second `run.sh check-issues` on the same stack passes the same way and reuses the same
   job, issue and comment ids (repeatability).
7. The output is captured before `down`, which deletes the state directory holding
   `issue-matrix.json`. The printed matrix and the refusal codes are copied into this file
   under a "Live outcome" heading, with the image tag and chart revision of the stack.
