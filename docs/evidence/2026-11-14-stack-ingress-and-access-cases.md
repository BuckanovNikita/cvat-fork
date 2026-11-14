# The Ingress route and four access cases on the stack, 2026-11-14

Ticket 11 of the defect fixes
(`.scratch/defect-fixes/issues/11-the-ingress-route-and-four-access-cases-on-the-stack.md`),
plan rows 1.3d and 1.3e.

This is part one: the tooling, checked without a running stack. No stack could be
started on this date. The live run is part two, listed in the ticket's comments, and
its outcome gets its own section here when it has run.

## Added

- `verify/team-analytics-stack/run.sh`:
  - `apply_ingress`, called by `up` after the proxy, applies
    `team-analytics/k8s/ingress.yaml` in the stack's namespace. The class is set to
    `TA_INGRESS_CLASS` (`nginx`) and the host to `TA_INGRESS_HOST`
    (`<namespace>.k8s.docker.internal`). The render goes through `guard_render` first.
  - `check_ingress`, called after `seed`, makes the status request through the Ingress.
  - `check_access_cases`, called last, runs the four cases.
  - `check_ingress_gone` is for after `down`.
  - The subcommands are `render-ingress`, `check-ingress`, `seed-access`,
    `check-access [CASE]` and `check-ingress-gone`.
- `verify/team-analytics-stack/access_cases.py`: one command per case. Each one decides
  pass or fail itself and prints `[access] PASS <case>` or exits with
  `[access] FAIL <case>: ...`.
- `verify/team-analytics-stack/access_accounts.json` and `seed_access.py` hold the
  cases' own accounts. `ta-group-admin` is in the `admin` group with
  `is_superuser`/`is_staff` false, which `seed_users.py` cannot express. `ta-org-r` has
  `ta-owner-r` and `ta-leaver`, and the membership is active again on every run.
  `ta-solo` is in no organization. `accounts.json` is unchanged, because
  `stack_api.py seed` requires its memberships to match exactly.

## How the request reaches the Ingress on this machine

These facts come from the k8s-infra skill (platform add-ons, host port table):

- ingress-nginx is class `nginx` and is exposed on the host's `localhost:80/443`. Those
  ports are already in the port table as the k8s-infra ingress, so no new host port is
  taken.
- The default certificate covers `*.k8s.docker.internal`, so one label under the zone
  validates. An Ingress without `tls:` gets that certificate on 443.
- Project names do not resolve on the host, and there is no wildcard lookup. The check
  connects to `127.0.0.1:443` and keeps the name for SNI, certificate verification and
  `Host`. Python's default trust store already holds the local CA (the host bundle), so
  verification stays on.

## Checks with supplied boundaries (part one)

Run in the worktree on 2026-11-14. Only cluster reads were made.

- `bash -n verify/team-analytics-stack/run.sh`: passes.
- Byte-compilation of `access_cases.py` and `seed_access.py` (output outside the tree):
  passes. `ruff check` with the repository's configuration: passes.
- `TA_RUN_ID=t11check run.sh render-ingress` prints the manifest with
  `ingressClassName: nginx` and
  `host: cvat-ta-it-t11check.k8s.docker.internal`.
  `kubectl --context docker-desktop apply --dry-run=client` of that render: accepted
  (`ingress.networking.k8s.io/team-analytics created (dry run)`).
- `guard_render` (the launcher's own function, with the dispatcher cut off) accepts that
  render. The same render with an `IngressClass` document appended is refused:
  `cluster-wide kind in render: IngressClass`, `render refused`.
- Cluster reads: `kubectl get ingressclass` lists `nginx`
  (controller `k8s.io/ingress-nginx`). The controller runs with `--ingress-class=nginx`,
  with no namespace restriction, and with
  `--default-ssl-certificate=ingress-nginx/k8s-docker-internal-tls`. Its Service
  `ingress-nginx-controller` is a LoadBalancer on `localhost`, 80 and 443.
- `curl --resolve probe-ta.k8s.docker.internal:443:127.0.0.1`, without `-k`: TLS
  verified (`ssl_verify_result` 0), and the controller answers 404 for a host with no
  Ingress. `access_cases.ingress_get` (the connection the check uses) does the same for
  `cvat-ta-it-t11check.k8s.docker.internal`: verified TLS, 404. That 404 is also what
  `check-ingress-gone` expects after `down`.
- The identity cache: `ANSWER_TTL = timedelta(minutes=1)` in
  `team-analytics/service/team_analytics/access.py`. `config.py` has no setting for it,
  so the removed-member case waits it out (60 s plus 5 s). `access_cases.py` reads the
  value from that source line and stops when it cannot find it (the parse gives 60).
- Read against the service's access code and the seam 1 tests:
  - Removed member: `test_cvats_answers_are_reused_for_at_most_one_minute` and
    `test_reuse_does_not_extend_the_minute` show the same session is refused only
    after the minute. So the case keeps one session, waits from the moment its last
    allowed read was answered, and does not judge the read made right after the
    removal. After the removal, `/api/organizations?slug=ta-org-r` no longer lists the
    organization to the leaver, and `/api/memberships` returns no row. Either way the
    answer is 403 `forbidden`. Without an organization there are no reading
    memberships, so the answer is `forbidden`, not `organization_required`
    (`test_ordinary_member_without_an_organization_is_refused_not_asked_to_select_one`).
  - Administrator by group: `Access.scope` reads only `groups` from
    `/api/users/self` (`test_admin_is_decided_by_the_admin_group_not_by_the_superuser_flag`).
    CVAT's own privilege also comes from the groups (`iam/middleware.py` of the stock
    server image). The `/api/users/self` serializer returns `is_superuser` and
    `is_staff`, so the case confirms both are false before it judges. Ticket 15's
    administrator-only history keys (`first_day`, `days_ready`, `days_total`) are
    expected in `status` with and without an organization
    (`test_an_administrator_gets_the_full_block_with_or_without_an_organization`).
  - Personal workspace: `org=` empty is a personal workspace in CVAT's IAM middleware
    (organization specified, none found). The service puts work with no organization
    under instance scope and under no organization
    (`test_admin_group_without_an_organization_reads_instance_scope_with_personal_workspaces`,
    `IsolationTest`). The case reads the details table with `search` and with `ids`, as
    `test_details_show_only_the_callers_organization` does.
  - Authorization header: the service forwards `Cookie` and `Authorization` as they
    arrive (`FORWARDED_HEADERS`). The stock server authenticates with
    `TokenAuthentication`, `AccessTokenAuthentication` (`Bearer`),
    `SessionAuthentication` and `BasicAuthenticationEx`, and its e-mail verification is
    `none`. The header requests are sent with no cookie jar, so the header is the only
    credential.

## Unverified

Every live criterion of the ticket: the Ingress applied and answered on a running
stack, the four cases against the real CVAT, and teardown removing the Ingress. In
particular, nothing has shown yet that a read-only personal access token is accepted
for these GET requests, or that CVAT returns 401, not 403, for a wrong Basic password
and an unknown token on this server.
