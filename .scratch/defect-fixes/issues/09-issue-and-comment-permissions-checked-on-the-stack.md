# 09: Issue and comment permissions checked on the stack

**What to build:** The issue and comment patch is seen working with real accounts on Kubernetes. Until now it was checked only by the policy test; the live matrix was written for Compose and never run against the corrected delivery. See "Stack and removals" in the spec (`../spec.md`).

**Blocked by:** 08 (The stack runs on the fork server image and the in-tree chart).

**Status:** resolved

- [x] The stack seeds an organization with an owner, a maintainer, a supervisor, workers, a member with no global role, a non-member and a member of another organization, and an issue with comments on a job none of the workers is assigned to.
- [x] Through the real API, an unassigned worker and an unassigned supervisor create, view, update and delete issues and comments of their organization, and list all of them.
- [x] The member with no global role gets what stock CVAT gives: it cannot act on issues it is not staff of, and its list holds only its own.
- [x] The non-member and the member of another organization are refused, and nothing crosses organizations.
- [x] The run judges the matrix itself, pass or fail; it is not left for reading.
- [x] The existing seed and check scripts are reused where they fit.
- [x] The matrix is kept in a dated evidence file.

## Comments

**2026-11-14, part one (no stack).** The machine's user is busy, so no stack was started; every
criterion above needs the live run and stays unticked. Added: `check_issues` in
`verify/team-analytics-stack/run.sh` (one call in `up`, after `check_final`) with the
subcommand `check-issues`, `check-issue-policies [patched|stock]`, `issue_matrix.py`,
`issue_accounts.json`; evidence skeleton `docs/evidence/2026-11-14-stack-issue-matrix.md`.

- The account with no global role: v2.82.0 gives every new account the `user` group (post-save
  signal), so `ta-admin` removes it through `PATCH /api/users/<id>` `{"groups": []}`, the admin
  API; the account reads `groups == []` back. Reasons and the fallback are in the evidence.
- Checked without a server: `bash -n`, byte-compilation, ruff; the matrix's 124 expectations
  against the policy engine, patched column against the import (124 of 124) and stock column
  against `cvat-v2.82.0-widened` (124 of 124), 32 of them differing between the columns. That
  run caught one wrong expectation (the no-role account's list with no organization named
  holds I2), corrected before the live run.
- Reuse: `seed_users.py` and `stack_api.py` are reused; the rows and techniques of
  `verify/opa_issues_check.py` are carried over; the Compose seed and check scripts themselves
  do not fit (`docker exec`, `/tmp` state, `requests`, superuser-owned issues) and are not
  called. Whether that meets "reused where they fit" is for the reviewer; the evidence says
  what was and was not taken.

Outstanding, part two, on a stack the orchestrator starts (`run.sh up`, or `run.sh check-issues`
on a running seeded stack); what each step must show:

1. `seed_users.py` prints the nine accounts of `issue_accounts.json` and `ta-org-i`, `ta-org-j`.
2. Global roles print as in `issue_accounts.json`: `ta-norole-i` `groups=[]`, `ta-worker-i2`
   `groups=['worker']`, the rest `['user']`; both organizations' memberships match the file.
   (Criterion 1.)
3. Layout prints J1 and JJ assigned to nobody, J2 to `ta-norole-i`, and I1, I2, IJ with their
   first comments and a second comment each by the owner. (Criterion 1.)
4. Every row prints `ok` with its HTTP status, and the run ends `issue matrix passed: 124 rows`
   with exit status 0: the unassigned worker, the global-`worker` worker and the supervisor do
   all eight actions on I1 and list I1, I2 (criterion 2); `ta-norole-i` is refused all eight on
   I1, views I2 and C2 only, and lists only I2 (criterion 3); `ta-worker-j`, `ta-outsider-i`
   and the org-i members acting on IJ are refused, and no list shows the other organization's
   objects (criterion 4). A `FAIL` or `INCONSISTENT` row exits non-zero (criterion 5).
5. Every refused row's status is reviewed: a refusal counts on any 4xx other than 401, so any
   code other than 403 is explained before criteria 3 and 4 are ticked, and the codes seen are
   then pinned in the matrix.
6. A second `run.sh check-issues` passes the same way with the same ids.
7. The output is captured before `down` (which deletes the state directory with
   `issue-matrix.json`); the printed matrix, the refusal codes, the image tag and chart
   revision go into the evidence file under "Live outcome" (criterion 7). Criterion 6 is
   ticked then on the evidence's reuse section if the reviewer accepts it.

2026-11-14: Merged into `feat/team-analytics-page` as `7f304201`, after tickets 10 (`3aa2b78b`) and 11 (`f273549f`). Conflicts in `verify/team-analytics-stack/run.sh` (usage lines, functions, the end of `up`) and `README.md` (the subcommand list and the description of `up`) kept both sides; in `up`, `check_issues` comes right after `check_final` and ticket 11's `check_access_cases` stays last. On the merged tree `bash -n` on `run.sh` and `py_compile` on `issue_matrix.py` passed, and `run.sh check-issue-policies patched` and `run.sh check-issue-policies stock` each reported 124 of 124 expectations matching and exited 0; no other launcher command was run. The ticket stays open: part two, the live run above, is outstanding. Evidence: `docs/evidence/2026-11-14-stack-issue-matrix.md`.

**2026-11-15, part two (live).** `run.sh check-issues` was run twice on the stack that ticket 08
brought up, with the server on `cvat/server:v2.82.0-fork-policies` (`4b38c649ae96`). Both runs
passed all 124 rows, exit 0, with the same ids and the same statuses. Outcome:
`docs/evidence/2026-11-14-stack-issue-matrix.md`, "Live outcome, 2026-11-15".

- Steps 1 to 3: the nine accounts and both organizations were seeded. `ta-admin`'s
  `PATCH /api/users/<id>` answered 200 for each. For `ta-norole-i` it returned `groups=[]`, and
  the account read itself back with no group. J1 and JJ are unassigned and J2 is assigned to
  `ta-norole-i`. Each fixed issue has a first comment and a reply. Criterion 1 is ticked.
- Step 4: the worker, the `worker`-role worker and the supervisor did all eight actions on I1
  and listed everything in `ta-org-i`. The no-role account was refused on I1, could only view
  I2 and its comment, and listed only I2. The non-member and the other organization's member
  got 403, and no list crossed organizations. The run judged each row itself. Criteria 2 to 5
  are ticked.
- Step 5: all 70 refusals were 403, so there was nothing to explain. The code is now pinned
  (`REFUSAL_STATUS`). `check-issue-policies` still matches 124 of 124 on both sides.
- Step 6: the second run passed with the pinned code and the same ids.
- Step 7: both runs' output and `issue-matrix.json` were copied before anything could delete the
  state directory, and the matrix with its statuses is in the evidence. Criterion 7 is ticked.
- Criterion 6 stays unticked: whether this counts as reuse is a judgement, not something a run
  shows. The run reuses `seed_users.py` and `stack_api.py`. The Compose seed and check scripts
  are not called; their rows and techniques were carried over instead. That leaves those two
  scripts with no caller when the Compose files are removed (plan row 1.4). The orchestrator or
  reviewer decides.
- 2026-11-15: Merged into `feat/team-analytics-page` as `3cd590eb`, with no conflict. On the merged tree `py_compile` on `issue_matrix.py` passed; no launcher command was run by the merger. Criterion 6 is ticked by the orchestrator's decision, not by a run: it is met. The stack's own `seed_users.py` and `stack_api.py` are reused. The Compose-era `verify/opa_issues_seed.py` and `verify/opa_issues_check.py` do not fit a Kubernetes stack (they rely on `docker exec`, a superuser and state in a temporary directory); their rows and techniques were carried over, and they go with the Compose removal in ticket 12. The ticket is resolved. Evidence: `docs/evidence/2026-11-14-stack-issue-matrix.md`.

2026-11-15: What the removed Compose launcher did and the stack does not, raised by the independent review of the delivery change (finding 5): `verify/opa_issues.sh` ran the matrix against a live stock server and then a patched one. The stack runs only the fork server image, so the stock column is now shown only by the policy engine (`run.sh check-issue-policies stock`, inputs built by `issue_matrix.py` as the server would send them), not by a real stock server. That live run is dropped; no second stack was built for it. Both sides of `check-issue-policies` now run in every `up` (in `preflight`) and are named in the upgrade procedure where the policies are merged; the fork specification records the dropped run. Branch `fix/delivery-review`, evidence `docs/evidence/2026-11-15-compose-removed.md`.
