# 11: The Ingress route and four access cases on the stack

**What to build:** The service's Ingress route is shown to work, and four access cases that were only ever seen against a stand-in are seen against a real CVAT. See "Stack and removals" in the spec (`../spec.md`) and story 106 of the Team Analytics spec.

**Blocked by:** 08 (The stack runs on the fork server image and the in-tree chart).

**Status:** resolved

- [x] The service's Ingress manifest is applied in the stack's namespace beside the proxy, under the cluster's Ingress class, and adds no cluster-wide object.
- [x] One status request through the Ingress with a real session is answered; the same request without a session is refused as signed out.
- [x] A member removed from the organization is refused once the service's identity cache has expired.
- [x] An administrator by group who is not a superuser reads instance scope and a named organization.
- [x] Job work done in a personal workspace appears under instance scope and under no organization.
- [x] Credentials sent as an authorization header get the same decisions as a session cookie.
- [x] The run judges each case itself, and the results are kept in a dated evidence file.
- [x] Teardown removes the Ingress with the namespace.

## Comments

2026-11-14, part one: the tooling is done on branch `ticket/11-ingress-access`, and it was checked without a running stack. No stack could be started on this date. Every criterion is live, so none is ticked. What was checked and how is in `docs/evidence/2026-11-14-stack-ingress-and-access-cases.md`. The removed-member case waits out the identity cache: `ANSWER_TTL` in `access.py` is one minute and has no setting.

Part two runs later, with a stack running (`verify/team-analytics-stack/run.sh up`, which calls every step below in order). Each step prints `[access] PASS ...`, or stops with `[access] FAIL ...` / `[ta-stack] error: ...`.

0. Before anything else, the images. The server, UI and service images (`TA_SERVER_IMAGE`, `TA_UI_IMAGE`, `TA_SERVICE_IMAGE`) must be built from this branch's tree, merged with the integration branch. On 2026-11-14 neither the default service tag nor the default UI tag was local, and without them `up` stops in `pull_images`. The service image must include ticket 15: without it, `status` lacks the administrator-only keys, and the group-admin case fails for that reason, not for an access rule.
1. `apply_ingress` (in `up`, after the proxy). `kubectl --context docker-desktop -n <namespace> get ingress team-analytics` must show class `nginx` and host `<namespace>.k8s.docker.internal`. `kubectl get ingress -A` must list it in no other namespace, and the render guard must have accepted it. Criterion 1.
2. `run.sh check-ingress` (in `up`, after `seed`). `GET https://<namespace>.k8s.docker.internal/team-analytics-api/v1/status?org=ta-org-a`, sent to the controller on 127.0.0.1:443 with certificate verification. With `ta-maintainer`'s session it must return 200 with `history`, `refresh` and `cutover`. Without a session it must return 401 with `error: not_authenticated`. Criterion 2.
3. `run.sh check-access removed-member` (in `up`, last, after `seed-access`). Before the removal, `ta-leaver` reads `status` of `ta-org-r`: 200. `ta-owner-r` then deletes the membership through `/api/memberships/<id>`, and the membership list no longer shows it. 65 s after the first read was answered, the same session must get 403 `forbidden` on `status` and `overview`, with `org=ta-org-r` and with no organization. The read made right after the removal is logged and not judged. Criterion 3.
4. `run.sh check-access group-admin`. `/api/users/self` of `ta-group-admin` must show `groups` containing `admin`, with `is_superuser` and `is_staff` false. `status` with no organization and with `ta-org-a` must return 200 with `first_day`, `days_ready` and `days_total`. `overview` for `ta-org-a` must list the annotators `ta-owner` sees there. `overview` with no organization must equal what `ta-admin` sees at instance scope, and must differ from the `ta-org-a` list. Criterion 4.
5. `run.sh check-access personal-workspace`. `ta-solo` is a member of nothing and works 20 min in a job of project `ta-personal` in the personal workspace (loaded once per stack). Within `TA_REFRESH_INTERVAL_S * 3 + 60` s, `ta-admin`'s `details` with no organization and `search=ta-solo` must return exactly one row, `ta-solo` with 1,200,000 ms, and `by=projects&ids=<project>` must list the project. For every organization `ta-admin` lists, the processed week must have no `ta-solo` row and no row for that project. Criterion 5.
6. `run.sh check-access header-credentials`. For `ta-maintainer`/`ta-org-a` (200), `ta-worker`/`ta-org-a` (403 `forbidden`), `ta-outsider`/`ta-org-a` (403 `forbidden`), `ta-maintainer`/none (403 `organization_required`) and `ta-group-admin`/none (200), `status` (no period) and `overview` (week) are requested with the session cookie and then with an `Authorization` header that carries no cookie. Basic and Bearer are judged apart, each with its own `[access] PASS header-credentials (Basic)` or `(Bearer)` line, and the Bearer token is a read-only personal access token, revoked after use. Each header result must equal the cookie result: the expected (status, error) and, for an overview, the same annotators. No credentials, a wrong Basic password and an unknown token must each give 401 `not_authenticated`. Basic passing meets the criterion. A Bearer failure is recorded as its own finding. Criterion 6.
7. Copy the `[access] PASS` lines and the `check-ingress` lines of the `up` log into a "Live outcome" section of the evidence file, along with the stack's commit and image tags. Criterion 7.
8. `run.sh down`, then `run.sh check-ingress-gone`. The namespace must be gone, no Ingress anywhere may name the host, and the controller must answer 404 for it. Criterion 8.

2026-11-14: Merged into `feat/team-analytics-page` as `f273549f`, after ticket 10 (`3aa2b78b`). Git merged `run.sh` and `README.md` without a conflict; the merged `up` calls `apply_ingress` after `apply_proxy`, `check_ingress` after `seed`, and `check_access_cases` last, after ticket 10's `check_task_progress` and `check_final`. On the merged tree `bash -n` on `run.sh` and `py_compile` on `access_cases.py` and `seed_access.py` passed; no launcher command was run. The ticket stays open: part two, the live run above, is outstanding. Evidence: `docs/evidence/2026-11-14-stack-ingress-and-access-cases.md`.

2026-11-15, part two: steps 1 to 7 ran live on the stack ticket 08 brought up, using only this ticket's own subcommands and read-only commands. Every case passed: `ingress`, `removed-member`, `group-admin`, `personal-workspace`, and `header-credentials` (Basic and Bearer, judged separately). The outcome is in "Live outcome, 2026-11-15" of `docs/evidence/2026-11-14-stack-ingress-and-access-cases.md`.

Both points left open in part one are settled. CVAT accepts a read-only Bearer access token for the three identity reads. It answers 401 to a wrong Basic password and to an unknown token, and the service passes that on as 401 `not_authenticated`.

The stack is shared with other tickets, so `access_cases.py` now reads a compared pair of service reads again, up to 4 times, before it judges a difference (`same_reads`).

Criterion 8 was left unticked at that point: the stack stayed up for further tickets.

2026-11-15, step 8: the stack was taken down once the live work had finished. `run.sh down` exited 0, and so did `run.sh check-ingress-gone`, which found no Ingress naming the host and a 404 from the controller. Afterwards nothing of the stack remained: no namespace, no Ingress, none of the five persistent volumes, no port-forward, port 8490 free, no state directory. Details are in "Teardown, 2026-11-15" of the evidence file.
- 2026-11-15: The live run merged into `feat/team-analytics-page` as `aa03acae`, with no conflict. On the merged tree `py_compile` on `access_cases.py` passed; no launcher command was run by the merger. The ticket stays open for criterion 8 (teardown removes the Ingress), shown when the stack comes down. Evidence: `docs/evidence/2026-11-14-stack-ingress-and-access-cases.md`.

2026-11-15: Resolved on `feat/team-analytics-page` by merges `f273549f` (the checks), `aa03acae` (the live cases) and `c0e2cdde` (the teardown); evidence `docs/evidence/2026-11-14-stack-ingress-and-access-cases.md`.
