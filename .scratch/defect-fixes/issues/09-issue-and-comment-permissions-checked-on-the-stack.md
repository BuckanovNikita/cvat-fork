# 09: Issue and comment permissions checked on the stack

**What to build:** The issue and comment patch is seen working with real accounts on Kubernetes. Until now it was checked only by the policy test; the live matrix was written for Compose and never run against the corrected delivery. See "Stack and removals" in the spec (`../spec.md`).

**Blocked by:** 08 (The stack runs on the fork server image and the in-tree chart).

**Status:** ready-for-agent

- [ ] The stack seeds an organization with an owner, a maintainer, a supervisor, workers, a member with no global role, a non-member and a member of another organization, and an issue with comments on a job none of the workers is assigned to.
- [ ] Through the real API, an unassigned worker and an unassigned supervisor create, view, update and delete issues and comments of their organization, and list all of them.
- [ ] The member with no global role gets what stock CVAT gives: it cannot act on issues it is not staff of, and its list holds only its own.
- [ ] The non-member and the member of another organization are refused, and nothing crosses organizations.
- [ ] The run judges the matrix itself, pass or fail; it is not left for reading.
- [ ] The existing seed and check scripts are reused where they fit.
- [ ] The matrix is kept in a dated evidence file.

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
