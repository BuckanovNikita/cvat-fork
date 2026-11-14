# Fix plan for the confirmed defects and recorded gaps

Rewritten on 2026-11-14 after three rounds of questions to the owner. Nothing
here is implemented. The decisions of section 1 are the owner's; the defaults
of section 2 were not confirmed one by one. The behaviour is specified in
[`spec.md`](spec.md); this file keeps the order of work, the file-level notes
and how each defect is known, until ticket files are cut from section 4.

It covers the list the owner asked to have fixed: the problems confirmed on
2026-11-14 around the issue and comment policies, the gaps the Team Analytics
implementation left behind, and what was never verified. Rows carry the ids of
[`../standard-fork/decisions-ledger.md`](../standard-fork/decisions-ledger.md)
where one exists; policy items are numbered `OPA-n`.

How each statement is known:

- *observed*: produced by a run recorded in `docs/evidence/`.
- *read*: found by reading the code on `feat/team-analytics-page` for this
  plan. Part of that reading was done by read-only helpers whose reports were
  taken as given.
- *recorded*: taken from the ledger or a review write-up, not re-read.

Nothing was run for this plan except: one read of the stock issue policy from
the stock server image, searches of the tree and history for a local path, and
the teardown of the test stack on the owner's instruction.

## 1. Decisions of the owner, 2026-11-14

| # | Decision |
| --- | --- |
| 1 | **The fork conversion is dropped.** Its draft was deleted on the owner's instruction; it is in history up to commit `fb3148e`. The overlay layout stays |
| 2 | **Compose is dead.** No deployment uses the Compose overlay. Its files and launchers are removed and their two live checks (issue permissions, task progress) move to the Kubernetes stack |
| 3 | **A fork server image delivers the policies**: the stock release image with the two patched policy files and nothing else (ADR 0004). No ConfigMap mount |
| 4 | **The import filter is widened**, accepting new identifiers for the mirrored history once. It brings in upstream's root lint configuration, `helm-chart/` and the four stock policy files, and drops `docker-compose.yml` |
| 5 | **The policies are patched in place** inside the import; `opa/` goes away |
| 6 | The Team Analytics service keeps its own image on the stock base |
| 7 | Role floor: the added policy rule requires at least the `worker` global role; below it a member gets exactly the stock behaviour |
| 8 | The API itself withholds figures of a period that is not fully processed |
| 9 | An organization maintainer's status shows whether history is complete, a progress percentage, which periods can be offered, the freshness stamp and the cutover day; administrators keep the full block |
| 10 | The cutover may move to an earlier hour, never a later one |
| 11 | Frame navigation counts frames moved, as the glossary says |
| 12 | A redo is not a creation |
| 13 | A group drag is one alignment per object moved, sharing the time equally; moving the selection box follows the same rule |
| 14 | The split bars by operation and the definitions footer are built |
| 15 | The home-directory path is redacted going forward; history is left alone |
| 16 | The never-applied Ingress is applied beside the stack's proxy and checked with one request per run |
| 17 | Stated limits, not fixed: counts lost on tab close (cvat-core stays untouched); tags, interactor and OpenCV objects are not counted; a session is at most a day long; in 3D jobs only sessions and working time are measured |
| 18 | Not a defect: a table lists every row of its own dimension under a page filter, so its legacy content can differ from a filtered, empty overview. Kept, with the missing test added |
| 19 | The kept test stack was torn down (done with the launcher's `down`; the namespace and its port-forward are gone) |

The glossary carries decisions 10, 12, 13 and 17. Decision 3 is ADR 0004;
decisions 2 and 4 amend ADR 0003.

## 2. Defaults nobody was asked about

Each is what the work will do unless the owner says otherwise.

| # | Default |
| --- | --- |
| a | **The lint gate is a hook pipeline (prek)**, holding ESLint, stylelint, the type check, ruff, the policy test and the node suites. Suites that need ClickHouse or the stack stay separate commands. The owner chose how the configuration arrives, not whether a gate exists |
| b | **Lease length 120 s**, renewed every 40 s, so a killed replica blocks refreshes for at most two minutes instead of thirty |
| c | **A redo still ends an alignment run**, as today, although it is no longer counted as an operation |
| d | **A group move is its own alignment for each object moved.** It ends the runs before it and does not continue into a later drag of one of those objects |
| e | **Detector use is verified with a supplied model answer**: the real UI is driven in the browser, and the model function's reply is supplied at the HTTP boundary. A deployed model function stays unverified and is said so |
| f | **The volume goes through the events API for the current week only.** Older weeks stay direct inserts unless the API accepts old timestamps, which is not known |
| g | The formatting-only change in `components/analytics/clickhouse/init.py` is reverted to the upstream file, since the in-tree chart will ship that directory to the cluster |
| h | The ledger stays as the record of earlier decisions, with a dated note that its last column refers to the dropped plan |

## 3. Order

Each step ends with its checks, then an independent review of the integrated
result where behaviour, interfaces or delivery changed.

```
0.1 hygiene ──┐
0.2 re-import ─┬─ 0.3 lint findings ── C (UI logging), D (page)
               └─ 1.1 policies in place ── 1.2 server image ── 1.3 stack ── 1.4 removals
A (reads), B (refresh): after 0.1, beside everything above
wave 3 (verification): after all of it
```

Constraints the order encodes:

- The re-import is one shot: every further widening changes the identifiers
  again. Its path list is proven in a scratch copy first (0.2).
- UI packages wait for the lint findings commit, so they are not rebased over
  a formatting sweep.
- Compose artefacts and `opa/` are deleted only after the stack carries both
  live checks and the image carries the policies (1.4).
- The lease test gets a supplied clock before the lease is shortened; that
  test already needed loosening on slow hosts.
- The group drag spans the UI and the SQL; the event's shape is fixed in the
  contract first, then both halves are built.
- P9's service half follows S13 in the same package; its page half follows it.
- Nothing was to be pushed before 0.1 and the security review. The owner then
  had `main` landed and pushed on 2026-11-14 as it was; see the comments of
  `spec.md`. The work itself is now ticketed under `issues/`.

## 4. The work

*Test first* names the failing test to write before the fix and its seam
(1 service against ClickHouse, 2 UI logging, 3 page, P policy test). A dash
means tooling, configuration or documentation, which gets a check instead.

### Wave 0: foundations

| # | Item | How known | Work | Check |
| --- | --- | --- | --- | --- |
| 0.1a | R8: a home-directory path in five tracked files (one line in each of four run logs, one line of `INFRA_MIGRATION.md`) | read (whole tree and every commit of `main..HEAD`, binary files included) | Redact the five lines. Keep the launcher's filter for Helm's symbolic-link warning and extend it to every Helm call: with the chart in the tree that warning prints the repository path | the same search over the tree finds nothing |
| 0.1b | V2: the frontend tests skip themselves when jsdom is missing (about 62 page tests in 13 files and the whole keyboard-and-mouse logging file, counted by search); jsdom is only another package's optional dependency | read | Fail, not skip. Declare jsdom in a fork-owned manifest for the harness | with jsdom off the path the suites fail |
| 0.2 | The widened import (decision 4) | — | See below | See below |
| 0.3 | V7: ESLint never ran on about 6,500 lines of UI code; L9: import cycles between `index` and each of `input-summary`, `class-change`, `model-creation` | read | First run of ESLint, stylelint and the type check with upstream's configuration; findings fixed in their own commit. The cycle is removed by moving the record writer out of `index.ts`. The gate of default (a) | all three exit clean; the seam 2 and 3 suites stay green |

**0.2 in detail.**

- Paths added: `eslint.config.mjs`, `.eslintrc.cjs`, `.stylelintrc.json`,
  `.prettierrc`, `.prettierignore`, `.editorconfig`; `helm-chart/`;
  `cvat/apps/engine/rules/issues.rego` and `comments.rego`,
  `cvat/apps/iam/rules/utils.rego`,
  `cvat/apps/organizations/rules/organizations.rego`. Path removed:
  `docker-compose.yml`. Upstream's root holds all of these at v2.82.0
  (*read* from the release's file list).
- Proof before the filter runs, in a scratch copy of those files at the
  recorded upstream commit: the ESLint and stylelint configurations load on
  our UI paths without a file the import lacks; the chart renders the same as
  the cached one (with default (g) applied); the policy test passes against
  the four stock files.
- `mirror-cvat.sh` deletes the existing mirror before cloning. It is changed
  to build the new mirror beside the old one and swap only on success.
- The local tags `v2.82.0` and `cvat-v2.82.0` keep pointing at the old
  filtered commit, which earlier merges cite. The new filtered commit gets its
  own tag, and the documented delta inventory switches to it. Old and new
  identifiers go into a dated baseline evidence file.
- Check after the pull: every path of the old list except `docker-compose.yml`
  is unchanged by it; every new path equals the upstream commit byte for byte.
- It needs a full clone of upstream from the network.

### Wave 1: policies, image, stack

| # | Item | How known | Test first | Work | Check |
| --- | --- | --- | --- | --- | --- |
| 1.1 | OPA-3: the added rule and the added list-filter branch admit any member whatever their global role, including none. The patch replaced the stock member branch of the list filter | read (both policies compared with their stock v2.82.0 files) | P: cases with `privilege: null` in `verify/opa_issues_test.rego`, for a caller who is staff of the issue and one who is not: the patched result equals the stock result for every action and for the list filter. Stock lets issue staff view without a global role, so "refused everything" would be wrong | Apply the patch to the imported stock files with `utils.has_perm(utils.WORKER)` in the added rules, and the stock member branch restored after the patched one. The test reads the in-tree files and helpers | the policy test on the stock tag and on the patched tree |
| 1.2 | OPA-2: nothing delivers the policies on Kubernetes | read | — | A Dockerfile and a build script beside `build-ui.sh`: stock server image plus the two files copied over the stock ones. Nothing else, no Python | the server's own bundle builder, run in the image, yields both patched files (the check of `docs/evidence/2026-11-14-opa-rules-mount-path.md`) |
| 1.3a | The stack uses the fork image and the in-tree chart | — | — | Backend image set to the fork image. The chart comes from `cvat/helm-chart`; the download of the upstream archive goes away. **Its dependency archives are still fetched by Helm and still checked against `chart-deps.sha256`; the lock stays ours** | the render guard and a fresh `up` |
| 1.3b | OPA-8: the patch was never seen on a running stack | recorded | — | The issue and comment matrix of `verify/opa_issues_check.py` runs in the stack with its seed, plus an account with no global role; the served bundle is checked for both files, each by itself | the matrix, kept as dated evidence |
| 1.3c | The task-progress check ran only on Compose | read | — | Its seed and browser check run in the stack | its output |
| 1.3d | The service's Ingress was never applied | recorded | — | Applied beside the proxy under the cluster's nginx class; one request through it per run | 200 from `status` through the Ingress |
| 1.3e | V4: access cases never seen against a real CVAT | recorded | — | Added to the stack's access matrix: a removed member, an administrator by group who is not a superuser, a personal workspace under instance scope, credentials as an `Authorization` header | the matrix |
| 1.4 | Compose artefacts and `opa/` have no user | read (nothing else references the imported Compose file) | — | Delete `docker-compose.override.yml`, the three `verify/docker-compose.*.yml`, `verify/opa_issues.sh`, `verify/run.sh`, `opa/`; their seed and check scripts stay where the stack uses them | a search for their names finds only history and dated evidence |
| 1.5 | Documents that describe the old delivery | read | — | Fork specification (BUILD-1, IAM-1, the stated limits of decision 17), the upgrade procedure (policies are merged, not reapplied; the server image is rebuilt), the Team Analytics spec's stock-backend and chart-download lines, the READMEs, `INFRA_MIGRATION.md` | read against the tree after 1.4 |

### Wave 2: product fixes, four packages with disjoint files

**A, service reads.** Owns `team_analytics/endpoints/`, `team_analytics/status/`,
`team_analytics/overview/`, `sql/read/` and their tests.

| # | Item | How known | Test first | Fix |
| --- | --- | --- | --- | --- |
| S13 | Unprocessed figures are returned with `processed: false` | read | 1: the processed-flag tests in `test_history.py`, `test_details_table.py`, `test_trends.py`, turned to expect no figures | Per endpoint, once the flag is known: overview, list, details, trends per bucket |
| A4 | Status shows instance-wide history dates and day counts to a maintainer | read | 1: in `test_isolation.py`, a maintainer's status has no first event day and no day counts; an administrator's has both | `endpoints/status.py`, `status/history.py` |
| Q8 | A project touched only by a technical account has no row in the details table | read | 1: such a project has a row | The row set of `sql/read/details.sql` gains the saved-box keys when the table is by project |
| P9 | The overview has no operations per row | read | 1: each overview row carries operation parts that add up as in the full view | The overview's annotator and project sections |
| Q10 | Decision 18 | read | 1: `test_cutover.py` pins a table's legacy content with its own filter set | none |

**B, service refresh.** Owns `cutover.py`, `history.py`, `refresh.py`,
`config.py`, `sql/control/`, `sql/refresh/`, `sql/read/cutover.sql` and their
tests.

| # | Item | How known | Test first | Fix |
| --- | --- | --- | --- | --- |
| Q9a | A stored cutover never changes | read | 1: an earlier tagged event that arrives later moves the cutover at the next daily check; a later one does not | The daily check looks again; the read takes the earliest stored hour. The cost of the long-range query is measured on the loaded volume first; if too costly, later moves come from the steps that compute an hour anyway. Removing the stored value does not undo a wrongly early event; that becomes a stated limit (see `spec.md`) |
| Q9b | With no stored cutover every period reads as legacy until a tagged hour reaches the totals | read | 1: a service started on stored tagged events knows the cutover on its first answer; tagged work present only in raw events still yields one | The finder runs in the start-up step and no longer waits for the totals |
| S15 | A refresh window under 24 hours counts today's earlier hours as processed without computing them | read ("processed" is inferred from history reaching yesterday) | 1: with a 1-hour window an event from earlier today is computed or its period reads as not processed | The history step also covers today's hours before the window. Two tests set a 1-hour window as a device for the edge between two refreshes, so short windows must stay possible |
| Q6 | A redo is counted as a creation | read (`sql/refresh/operations.sql`) | 1: draw, undo, redo is one creation; the redo's time is Other. The redo tests in `test_creation_methods.py` change with it | Remove the redo branch from the creation rule; default (c) for alignment runs |
| L10a, SQL half | A group event must become one alignment per object | decision 13 | 1: a group event of three objects and 6 s yields three alignments of 2 s | `sql/refresh/operations.sql`, after the event's shape is fixed with package C |
| V10 | The hanging-renewal test depends on wall-clock time | read | — | A supplied clock for the lease tests |
| S9 | A killed replica blocks refreshes for 30 minutes | recorded; the lease is a constant of 1800 s (*read*) | 1: a killed holder is overtaken within the lease | Default (b), after V10 |

**C, UI logging.** Owns `utils/team-analytics-logging/`, the fork's edits in
upstream UI files, `verify/team-analytics-logging/`.

| # | Item | How known | Test first | Fix |
| --- | --- | --- | --- | --- |
| L2 | Frame navigation counts repeats that moved no frame | read (a repeat while a frame loads asks for the same frame again) | 2: a press or repeat while the frame is loading adds nothing, and neither does one at the last frame | A frame-navigation hotkey counts when the frame changes as a result; the frame-change success signal already exists |
| L10a, UI half | A group drag logs only the grabbed shape; moving the selection box logs nothing | read (the canvas reports the group in one event that is saved without logging, and reports the grabbed shape again) | 2: a group drag of three boxes logs one group event for three objects and no second event for the grabbed one | The group-moved handler in `canvas-wrapper.tsx`; the event's shape in `contract.ts` |

**D, page.** Owns the page directory and `verify/team-analytics-page/`.

| # | Item | How known | Test first | Fix |
| --- | --- | --- | --- | --- |
| P10 | No definitions footer | read | 3: the overview ends with the definitions, in glossary wording | A small component |
| P9 | Bars are not split by operation | read | 3: the two cards draw the segments and a legend | The two cards and `working-time-breakdown.tsx`, reusing the full view's segment logic; after A |
| A4 | The progress line shows "N of M days" | read (`history.tsx`) | 3: it renders from the percentage when the day counts are absent | `history.tsx`; after A |

### Wave 3: verification

One dated evidence file. The stack starts from an empty namespace (decision 19).

| # | Run |
| --- | --- |
| V8 | `up`, `up`, `down` with the fork server image and the full suites on both ClickHouse images |
| — | The recheck of every wave 2 row on the stack: a direct call for an unprocessed period; status as maintainer and as administrator; the technical account's project in the details table; an in-place upgrade read at once for the cutover; a redo and a group drag in the browser read back from the events table; a held frame key on a slow frame; the cards beside the prototype at 1400 px and 400 px |
| V5a | Default (e) |
| V5b | Default (f) |
| — | A count of sessions that reached the one-day limit |
| — | The security review of `main..HEAD`, after 0.1 |
| V11 | Each of the ten criteria ticked on a reading is restated in its ticket as what was shown; only what this wave shows is ticked again |

## 5. No longer planned

- OPA-1, OPA-4, OPA-5, OPA-6, OPA-7 (the mount path on `main`, the root
  override, file permissions, the either-file check, the missing command):
  they repair the Compose delivery, which decision 2 removes. The either-file
  check survives as "each file by itself" in 1.3b.
- Q9c, Q10, Q5, L6, L10b: decisions 17 and 18.
- A session longer than a day and the tab-close loss are written into the
  fork specification as limits, not fixed.

## 6. Carried over from the dropped conversion draft

Two things this plan relies on were only written there (history, up to
`fb3148e`); neither was run:

- Upstream's lint commands, scoped to our paths: `yarn run eslint <paths>`,
  `yarn run stylelint '<dir>/**/*.scss'`, `yarn run type-check`, after
  `yarn install --immutable`.
- The thin server image is valid only while the fork adds no Python
  dependency. Here it adds no Python at all.

## 7. Not verified

- Every *read* statement comes from the sources; line numbers are left out
  because they move. Nothing of sections 3 and 4 was tried.
- That upstream's root lint configuration loads with only the files named in
  0.2. The scratch-copy proof exists to find out before the one-shot filter.
- That a squashed subtree pull accepts a re-filtered mirror whose commit ids
  differ from the recorded ones.
- That the chart's `analytics` link resolves inside the import as it does in
  upstream's tree.
- The cost of the cutover's long-range query.
- Whether the events API accepts events with old timestamps.
- Remote state, fetched on 2026-11-14: the remote's `main` equalled local
  `main` before this branch was landed on it, so the one path line in
  `INFRA_MIGRATION.md` is published. The remote also holds this branch up to
  `f492c65`, the commit before implementation began; every commit that carries
  the path in the run logs or in compiled files came after it and is not
  published. An earlier version of this plan said the branch had no upstream
  and had never been pushed; both were wrong.
- The pasted list was cut in places; items 2 to 4 of its "confirmed" part were
  rebuilt from the review follow-ups below them, and the fragment about
  "refresh for up to 30 minutes" is read as S9.
- Overview latency under load (ledger S12), part-hour time zones (Q11) and
  the eighteen unanswered review questions (O15) are not in the owner's list
  and are not planned here.
