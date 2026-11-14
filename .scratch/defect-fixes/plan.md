# Fix plan for the confirmed defects and recorded gaps

Status: needs-triage

Draft of 2026-11-14 for the owner to review. Nothing here is implemented, and
no ticket files exist yet; they are cut from section 5 once the decisions of
section 2 are answered.

It covers the list the owner asked to have fixed: the problems confirmed on
2026-11-14 around the issue and comment policies, the gaps the Team Analytics
implementation left behind, and what was never verified. Rows carry the ids of
[`../standard-fork/decisions-ledger.md`](../standard-fork/decisions-ledger.md)
where one exists; policy items are new and are numbered `OPA-n`.

How each statement is known:

- *observed*: produced by a run recorded in `docs/evidence/`.
- *read*: found by reading the code on `feat/team-analytics-page` at `0a26a8c`
  for this plan. Nothing was run for this plan: no test, build or stack.
- *recorded*: taken from the ledger or a review write-up, not re-read.

## 1. What decides the order

The fork conversion in [`../standard-fork/plan.md`](../standard-fork/plan.md)
is still `needs-triage`. It deletes the separate service process, the Compose
overlays, the copied policies and the stand-in access layer, so about half of
the fixes below would be written and then thrown away. Each item therefore has
one disposition:

| Disposition | Meaning | Items |
| --- | --- | --- |
| **K** keep | Fix now. The code moves into the fork unchanged (UI, UI logging, SQL, refresh logic, page) | S13, A4, Q9, Q10, Q8, S15, Q6, L2, L10, L9, P9, P10, V2, V7 findings, R8 |
| **T** throwaway | Fix now only if the conversion is declined or more than a few weeks away; it is deleted by the conversion | OPA-2, S9, V10, the Ingress |
| **P** production | Throwaway under the conversion, but a deployment uses it today or a check of it depends on it, so fix now regardless | OPA-1, OPA-3, OPA-4, OPA-5, OPA-6, OPA-7 |
| **C** conversion | Closed properly only by the conversion; an interim check is offered where cheap | V7 (lint as a gate), V4, L6 |
| **V** verify | Not a code change: a run that was never made | OPA-8, V5, V8, V11, the security review |

Waves 0 and 1 (section 4) contain only **P** and **K** items and the one
verification run that belongs to them (OPA-8), so they can start before the
conversion is decided.

## 2. Decisions for the owner

None of the recommendations below has been approved. The arrows in the earlier
session's summary were recommendations too. The nine questions that summary
calls "Q1 to Q9 of the revised round" are not in the repository; this table
replaces them where they overlap and cannot say what else they asked.

| # | Decision | Recommendation | Blocks |
| --- | --- | --- | --- |
| G0 | Is the fork conversion going ahead, and roughly when? | Yes. Then every **T** item is skipped | wave 2 |
| G1 | OPA-3: must the added member rule require a global role? | Yes: at least `worker`, in the added `allow` rule and the added filter branch of both files. A user in no group is normally a deactivated or half-provisioned account | wave 0, and the cherry-pick to `main` |
| G2 | OPA-2: deliver the policies on Kubernetes now, or with the fork server image? | With the image, unless members need the wider issue access on a cluster deployment now. If now: a ConfigMap mounted into the server pod through the chart's `additionalVolumes` and `additionalVolumeMounts` (both keys exist in the v2.82.0 chart, *read*) | wave 2 |
| G3 | S13: should the API itself withhold figures of a period that is not fully processed? | Yes. Answer `processed: false` without figures; the page already shows that state | wave 1 |
| G4 | A4: what may an organization maintainer see in `status`? | A `complete` flag, a progress percentage, which periods may be offered, the freshness stamp and the cutover day. Not the instance's first event day or its day counts. The cutover day stays because the page names it and it tells only when the upgraded UI first logged anywhere. The page's progress line shows "N of M days" today and changes with it | wave 1 |
| G5 | Q9: how is the cutover found and corrected? | Find it at start and in the daily check, not only when a tagged hour reaches the totals; let the daily check move it to an earlier hour; keep the manual correction for a wrongly dated event. Needs the cost of the long-range query measured first | wave 1 |
| G6 | L2: is frame navigation "every invocation" (spec) or "every frame moved" (ticket 13, glossary)? | Every frame moved: a repeat that arrives while a frame is loading is not counted | wave 1 |
| G7 | L10: which uncounted actions become counted? | Group drags and selection-box moves: yes, they are plain undercounts. Pasted tags, interactor and OpenCV objects need a class first (creation method "semi-automatic" is proposed); leave them out until it is named | wave 1 |
| G8 | P9 and P10: build the split bars and the definitions footer, or drop them on record? | Build both; the signed-off prototype shows them | wave 1 |
| G9 | Q5: a session longer than a day is cut | Do not fix. Count such sessions in the verification run and revisit if any exist; a longer read-back costs every refresh | — |
| G10 | R8: is redacting forward enough, or must the path leave the branch history? | Redact forward only. The same home prefix is already in `INFRA_MIGRATION.md` on `main` (one line), and local `main` equals the last fetched `origin/main`, so it is published already. On the branch it also sits in compiled Python files committed 133 commits back and removed later; removing it from history would mean rewriting most of the branch, merges included, and would still leave `main` | any push |
| G11 | V8: the kept stack must be torn down for a fresh full run | Tear down after wave 1; it was left running at the owner's request, so this needs the owner's word | wave 3 |

## 3. The items

Columns: *How known* as defined above. *Test first* names the failing test to
write before the fix and its seam (1 service against ClickHouse, 2 UI logging,
3 page, P policy test); a dash means the item is tooling, configuration or
documentation, which gets a check instead of a test. *Recheck* is how the
original failure path is shown fixed.

### 3.1 Issue and comment policies

| # | Problem | How known | Disp. | Test first | Fix | Recheck |
| --- | --- | --- | --- | --- | --- | --- |
| OPA-1 | The mount path fix `f97d41b` is only on the feature branch; `main` still mounts into a directory the server does not read | observed (bundle built in the stock image, three ways by the reviewer) | P | — | Bring the fix to `main` together with OPA-3 to OPA-7, never alone (section 4) | OPA-8 |
| OPA-2 | Nothing delivers the policies on Kubernetes; the cluster runs the stock rules | read (the stack's values and manifests mount no policy) | T | — | Decision G2 | the stack run reads `/api/auth/rules` and checks both files |
| OPA-3 | The added rule admits any organization member whatever their global role, including none. The added filter branch is the same. The policy test covers `user` and `worker` only | read (`opa/rules/issues.rego`, `comments.rego`: the added `allow` and `else` branches test membership only) | P | P: a case with `privilege: null` in `verify/opa_issues_test.rego`. For create, view, update and delete it expects refusal. For `list` it expects exactly what the stock rules give that caller, since stock lets any member list, restricted to their own assignments | `utils.has_perm(utils.WORKER)` in the two added rules of each file. The patch **replaced** the stock member branch of the list filter (compared with the stock v2.82.0 file, *read*), so that branch is restored after the patched one; otherwise a member below the floor gets no filter at all. IAM-1 wording in `docs/fork-specification.md` | policy test on stock and patched rules; OPA-8 |
| OPA-4 | The root override used from this checkout resolves its relative mounts beside `cvat/docker-compose.yml`, where no `opa/rules/` exists. Before the path fix that did nothing; now the server container fails to start | recorded (review of `f97d41b`) | P | — | Take the rules directory from a variable with the documented default, as the verification overlay already does; one sentence in the override header and in BUILD-1 | `docker compose config` rendered from the deployment layout and from this checkout: both name existing files |
| OPA-5 | A policy file the server's user cannot read makes the bundle build raise | recorded (same review) | P | — | A precondition in `docs/upstream-upgrade.md`: both files exist and are world-readable before the server is recreated | part of OPA-8 |
| OPA-6 | `verify/opa_issues.sh` accepts the patch marker in either file | read (`grep -l` over two files succeeds on one match) | P (OPA-8 relies on it) | — | Check each file by itself | run the check against a bundle with one stock file: it must fail |
| OPA-7 | The upgrade document says to build the bundle in the image and gives no command | read | P | — | Add the command used for the 2026-11-14 check | follow the document literally once |
| OPA-8 | The patch was never seen on a running stack: Compose applying the mounts, the bundle over HTTP, OPA loading it, real API outcomes | recorded | V | — | `verify/opa_issues.sh all` after OPA-3 and OPA-6, with an account in no group added to its matrix. Three of its images were not local on 2026-11-14. It starts a Compose stack, which the owner's Kubernetes-only rule and `INFRA_MIGRATION.md` argue against; it is still the only place the Compose overlay can be seen working, so it needs the owner's word, or G2 answered "now" to check on the cluster instead | its own output, kept as dated evidence |

### 3.2 Service: access and what the API returns

| # | Problem | How known | Disp. | Test first | Fix | Recheck |
| --- | --- | --- | --- | --- | --- | --- |
| S13 | Figures of a period that is not fully processed are returned with `processed: false`; only the page hides them | read (`covers()` is evaluated per endpoint and nothing withholds the answer) | K | 1: the existing processed-flag tests in `test_history.py`, `test_details_table.py`, `test_trends.py`, turned to expect no figures | Per endpoint, after the flag is known: `endpoints/overview.py`, `list.py`, `details.py`, `trends.py` (per bucket) | a direct call for an unprocessed period on the stack; 3: the page still shows its "being processed" state |
| A4 | `status` shows the instance's first event day, day counts and cutover to an organization maintainer | read (`status/history.py` and `sql/read/history_state.sql` have no organization clause; `test_isolation.py` has no status case) | K | 1: in `test_isolation.py`, a maintainer's `status` carries no first event day and no day counts, and an admin's still does. 3: the progress line renders from the percentage | `endpoints/status.py` and `status/history.py`; on the page `history.tsx`, which reads the day counts today. Per decision G4 | the same call as a maintainer and as an admin on the stack |
| Q8 | A project touched only by a technical account is missing from the details table | read (`sql/read/details.sql`: the row set comes from working time and operations, both of which exclude technical accounts; saved boxes are only joined onto it) | K | 1: in `test_details_table.py`, a project whose only work is a technical account's saved boxes has a row | Add the saved-box keys to the row set when the table is by project | the stack's `ta-bot` project in the details table |

### 3.3 Service: cutover, legacy flag, refresh

| # | Problem | How known | Disp. | Test first | Fix | Recheck |
| --- | --- | --- | --- | --- | --- | --- |
| Q9a | A wrong stored cutover stays until its row is deleted by hand | read (insert-once; the read takes the first row) | K | 1: in `test_cutover.py`, an earlier tagged event arriving after the cutover was stored moves it at the next daily check | `cutover.py`, `sql/control/cutover_*.sql`, `sql/read/cutover.sql`, per decision G5 | exercise the manual correction once too; it never was |
| Q9b | Right after an upgrade every period reads as legacy until the first refresh | read (no row means legacy) | K | 1: a service started on stored tagged events answers its first request with the cutover already known | Run the finder in the start-up schema step, before requests are served | upgrade the kept stack in place and read `status` at once |
| Q9c | An instance whose stored work is only untagged or 3D has no cutover, so its periods read as legacy. **The pasted wording ("a scope with only 3D work") is not what the code does:** the cutover is instance-wide, and a scope without tagged work is not legacy once any cutover exists | read (`cutover.py`; `test_cutover.py` asserts the scope case) | K | 1: tagged work that exists only in raw events, not yet in the totals, still yields a cutover | Covered by the Q9b change (the finder no longer waits for a tagged hour in the totals). An instance with 3D work only stays legacy; record that as the definition, not a defect | — |
| Q10 | The legacy flag can differ between the details table and the overview | read (details and list clear their own dimension filter before deciding whether the scope has job work; the overview applies both filters) | K | 1: `test_cutover.py`, the existing same-cutover test repeated with an annotator and a project filter set | One shared rule for "the scope has job work". The difference is made in `endpoints/details.py` and `endpoints/list.py`, which drop the table's own filter before asking; the SQL files only receive the result | the filtered page on the stack: one notice, everywhere or nowhere |
| S15 | A refresh window under 24 hours marks today's earlier hours as processed without computing them | read ("processed" is inferred from history reaching yesterday, not from the marked hours) | K | 1: with a 1-hour window, an event from earlier today is either computed or its period reads as not processed | Two service tests set a 1-hour window on purpose (`test_creation_methods.py`, `test_bounding_boxes.py`), so refusing short windows at start would break them. Preferred: let the history step also cover today's hours before the window. Fallback: refuse a window under 24 hours and rewrite those two tests | start with 12 hours on the stack and compare an early-morning figure with the raw events |
| Q6 | A redone creation has no shape type, so it counts only under All shapes. **The pasted "counts as one object" is the UI's doing, not the SQL's:** the SQL counts the event's `count`, and the UI always logs 1 | read (`annotation-actions.ts` redo logging; `sql/refresh/operations.sql`) | K | 2: a redo of a creation carries the shape fields and the number of objects restored. 1: such an event counts under Bounding boxes | UI: add the fields after the redo resolves, from the ids it returns. SQL: read them like any creation | redo a propagated box in the browser and read the events table |
| Q5 | A session longer than a day is cut | read (`sql/refresh/sessions.sql` reads one day back) | — | — | Decision G9: not fixed; counted in wave 3 | — |
| S9 | A replica killed mid-step blocks every refresh for up to 30 minutes | recorded; the lease length is a constant of 1800 s (*read*) | T | 1: a killed holder is overtaken within the shorter lease | Shorter lease with the same renewal ratio. Only if G0 is "no" | kill the pod mid-step on the stack |
| V10 | One lease test was loosened from 3 s to 8 s | read (`test_lease.py`, the hanging-renewal case; it still asserts that the release is not held up) | T | — | Not a product defect. Only if G0 is "no": replace wall-clock waits with a supplied clock | — |

### 3.4 UI logging

| # | Problem | How known | Disp. | Test first | Fix | Recheck |
| --- | --- | --- | --- | --- | --- | --- |
| L2 | Frame navigation counts key repeats that did not move a frame | read (repeats are skipped for every action except frame navigation; a repeat while a frame loads asks for the same frame again) | K | 2: in `keyboard-mouse.test.cjs`, repeats while the frame is loading add nothing | `input-summary.ts` (`hotkeyUsed`): skip a frame-navigation repeat while the player is fetching. Decision G6 | hold `F` on a slow frame in the browser; the summary equals the frames moved |
| L10a | A group drag logs only the grabbed shape; moving the selection box logs nothing | read (the canvas reports the whole group in one event that the UI saves without logging, and reports the grabbed shape a second time) | K | 2: a group drag of three boxes yields three aligned objects, not one and not four | `canvas-wrapper.tsx`, the group-moved handler; the single-shape event of the same gesture must not be counted twice | drag three selected boxes in the browser |
| L10b | Pasted tags, interactor and OpenCV objects are not counted | read (no event on those paths, upstream or ours) | K | after G7 | after G7 | — |
| L9 | The logging module has import cycles: `index` with each of `input-summary`, `class-change` and `model-creation` | read | K | — (no behaviour changes; the seam 2 suite must stay green) | Move the record writer out of `index.ts` into its own module | ESLint's cycle rule in V7 |
| L6 | Counts since the last summary are lost on tab close | recorded | C | — | Needs a cvat-core change; decision D8 of the fork plan | — |

### 3.5 Page

| # | Problem | How known | Disp. | Test first | Fix | Recheck |
| --- | --- | --- | --- | --- | --- | --- |
| P9 | Overview bars by project and by annotator are not split by operation | read (the overview answer has no per-row operations; only the full view's list has them) | K | 1: each overview row carries operation parts that add up as in the full view. 3: the two cards draw the segments and a legend | Service: per-row operations in the overview. Page: the two cards and `working-time-breakdown.tsx`, reusing the full view's segment logic | side by side with the prototype at 1400 px and 400 px |
| P10 | The definitions footer of the design is absent | read (nothing in the page directory renders definitions) | K | 3: the overview ends with the definitions, in glossary wording | A small component in the page directory | same browser check |

P9 needs the service change of its own row first; it also touches the overview
SQL, so it follows S13 and Q10.

### 3.6 Tests, lint, public repository

| # | Problem | How known | Disp. | Fix | Recheck |
| --- | --- | --- | --- | --- | --- |
| V7 | ESLint never ran on about 6,500 lines of UI code: the filtered import has no root ESLint configuration, and the package configuration requires one | read | K for the findings, C for the gate | One run with upstream v2.82.0's root configuration supplied from a full upstream checkout, not committed; findings fixed in their own commit before any other UI work. *Not run:* whether ESLint accepts a configuration outside the tree | the same run exits clean; it becomes a gate only with the conversion |
| V7b | Type checks resolved workspace packages from another checkout | recorded for the implementation worktrees. In this checkout they resolve through its own workspace links (*read*) | K | Run the type check from a checkout with its own install and record it | exit 0 in the evidence file |
| V2 | The frontend tests use a jsdom that is only another package's optional dependency, and **skip themselves when it is missing**: about 62 page tests in 13 files and the whole keyboard-and-mouse logging file would pass as skipped (*read*, counted by search) | read | K | Fail, not skip, when jsdom is absent; declare jsdom in a fork-owned manifest for the harness | remove jsdom from the path once: the suites must fail |
| R8 | A home-directory path is in the tree in five files: one line in each of four committed run logs, and one line of `INFRA_MIGRATION.md` that is on `main` as well. In the branch history it is also inside compiled Python files that were committed and later removed | read (a search of the whole tree and of every commit in `main..HEAD`, binary files included) | K | Redact the five lines; filter that warning where the launcher captures logs. Decision G10 for the history | the same search over the tree finds nothing |
| — | The commit security review never completed | recorded | V | Run it over `main..HEAD` after R8 | its report |

### 3.7 Never verified

| # | Gap | Disp. | Plan |
| --- | --- | --- | --- |
| V4 | Access against a real CVAT: removed member, admin by group and not by superuser flag, personal workspaces, credentials as an `Authorization` header | C | With the conversion these are REST tests on real roles. If G0 is "no": four cases added to the stack run's access matrix |
| — | The production Ingress route was never applied | T | Goes away with the conversion. If G0 is "no": the test stack routes through the Ingress instead of its own proxy |
| V5a | The detector record was posted through the API, not produced by the UI | V | Drive the real UI in the browser run with the model function's answer supplied at the HTTP boundary. A deployed model function stays unverified and is said so |
| V5b | The 100-annotator volume was inserted straight into ClickHouse | V | Send the current week through the events API and Vector. Older weeks stay direct inserts unless the API accepts old timestamps, which is not known |
| V8 | No full rerun after the two fix rounds: fast suites only, stack upgraded in place | V | `down`, `up`, `up`, `down` with the full suites on both ClickHouse images, after wave 1. Decision G11 |
| V11 | Ten ticket criteria were ticked on a stand-in, a script, or a rule later replaced | V | Restate each in its ticket as what was actually shown (three already carry a note); tick again only what wave 3 shows |

## 4. Waves

Each wave ends with the checks of its rows, then an independent review of the
integrated result, since every wave changes behaviour.

**Wave 0: safe to start now, no dependence on G0.**

1. R8 redaction and V2 (fail instead of skip). Small, independent.
2. V7: the one-off ESLint run and its findings commit, before any other UI
   edit, so later packages are not rebased over a formatting sweep.
3. Policies, in this order: OPA-3 (after G1), OPA-4, OPA-5, OPA-6, OPA-7 on
   the feature branch; then OPA-8. **Ordering constraint:** `f97d41b` is what
   switches the patch on, and with it the missing role floor and the start
   failure of OPA-4. It must reach `main` together with OPA-3 and OPA-4, as one
   reviewed series, not as a lone cherry-pick.

**Wave 1: kept fixes, in parallel packages with disjoint files.**

| Package | Items | Owns |
| --- | --- | --- |
| A: reads | S13, A4, Q8, Q10 | `team_analytics/endpoints/`, `team_analytics/status/`, `sql/read/`, their tests; `history.tsx` and its page test for A4 |
| B: cutover and refresh | Q9, S15, the SQL half of Q6 | `cutover.py`, `history.py`, `config.py`, `sql/control/`, `sql/refresh/`, `sql/read/cutover.sql`, their tests |
| C: UI logging | L2, L10a, L9, the UI half of Q6 | `utils/team-analytics-logging/`, the edited upstream UI files, `verify/team-analytics-logging/` |
| D: page | P10, then P9 | the page directory, `verify/team-analytics-page/` |

Sequential edges: A and B both add cases to `test_cutover.py` (Q10 and Q9), so
B lands first and A rebases on it. A's one page file (`history.tsx`) is outside
D's work on the cards. P9's service half adds to the overview that S13 and Q10
change, so it follows A. Q6's SQL half follows its UI half only for the
browser recheck.

**Wave 2: only if G0 is "no" or G2 is "now".** OPA-2, S9, V10, V4 on the
stack, the Ingress.

**Wave 3: verification.** After G11: the fresh full run (V8) carrying V5a,
V5b, the count of sessions over a day (G9) and the rechecks of every wave 1
row; the security review; V11. One dated evidence file.

Nothing is pushed until R8, G10 and the security review are settled.

## 5. From this plan to tickets

Once section 2 is answered: a specification in this directory stating the
decided behaviour, then one ticket per row group (the four packages of wave 1,
the policy series, hygiene, the verification run), each with its test-first
line from section 3 as acceptance criteria.

## 6. Not verified, and what could not be mapped

- Nothing in this plan was run. Every *read* statement comes from the sources
  at `0a26a8c`. Files are named; line numbers are left out because they move.
  Part of the reading was done by two read-only helpers whose reports were
  taken as given, not re-read line by line.
- The pasted list was cut in places. Items 2 to 4 of its "confirmed" part were
  rebuilt from the review follow-ups below them (Kubernetes delivery, the role
  floor, the root override). The fragment "…ry refresh for up to 30 minutes"
  is read as S9. If an item of the original list is missing here, it was in
  the cut text.
- Remote state: `feat/team-analytics-page` has no upstream configured and the
  remote was not fetched; "never pushed" rests on the local references.
- For OPA-3 only `issues.rego` was compared with the stock v2.82.0 file
  (taken from the stock server image). `comments.rego` carries the same two
  additions by reading; its stock counterpart was not compared.
- Whether the test namespace still holds the data of the last run was not
  looked at; only that the namespace exists.
- Whether the input summary is written in 3D jobs, which would give decision
  G5 a better cutover signal than the first shape-tagged event.
- Overview latency under load (ledger S12) is not in the owner's list and is
  not planned here.
