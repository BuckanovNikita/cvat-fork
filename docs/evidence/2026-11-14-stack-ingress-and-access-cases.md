# The Ingress route and four access cases on the stack, 2026-11-14

Ticket 11 of the defect fixes
(`.scratch/defect-fixes/issues/11-the-ingress-route-and-four-access-cases-on-the-stack.md`),
plan rows 1.3d and 1.3e.

Part one, the tooling, was checked on 2026-11-14 without a running stack. Part two, the
live run, is in "Live outcome, 2026-11-15" below.

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
  - In the stock image, a read-only access token is refused only for methods that are
    not safe (`access_tokens/permissions.py`). A token is revoked on `DELETE`, and the
    list holds only usable tokens, so the stale-token cleanup sees only a token left by
    an interrupted run. Basic and Bearer are judged apart, so a Bearer problem cannot
    hide the Basic result. `status` is sent without a period, as the existing access
    matrix sends it.

## Live outcome, 2026-11-15

Ticket 08 brought the stack up in namespace `cvat-ta-it-<user>` on `docker-desktop`. The
images were:

- UI: `310e9bbc6a47`
- service: `42d4bb9ab97e`, built from `3dc1a7bc`, which includes ticket 15
- server: `4b38c649ae96`

Ticket 08's `up` applied the Ingress, so its object was 29 minutes old when these
checks ran. Ticket 08's agent had also run `check-access` once before, so `ta-solo`'s
personal work was already loaded. These checks were run from branch
`ticket/11-ingress-access` at `44134f2f`, with the `same_reads` change below not yet
committed. Only this ticket's own subcommands and read-only commands were run. Tickets
09 and 10 were working on the same stack at the same time.

- Step 1, the Ingress. `run.sh render-ingress` gives `ingressClassName: nginx` and
  host `cvat-ta-it-<user>.k8s.docker.internal`. The live object
  `cvat-ta-it-<user>/team-analytics` matches it: class `nginx`, the same host, path
  `/team-analytics-api` to `team-analytics:http`. `kubectl get ingress -A` lists it in
  that namespace only. The other three Ingresses in the cluster are k8s-infra's
  ClearML hosts.
- Step 2, `run.sh check-ingress`. Requests go to the controller on 127.0.0.1:443 under
  that host, with the certificate verified.
  - `status?org=ta-org-a` with `ta-maintainer`'s session: 200 with
    `cutover`, `history` and `refresh`.
  - The same request without a session: 401 `not_authenticated`.
  - `[access] PASS ingress`.
- Steps 3 to 6, `run.sh check-access` (it runs `seed-access` first):
  - removed-member:
    - Before the removal, `ta-leaver` gets 200 on `org=ta-org-r`.
    - The owner deletes the membership through CVAT's API.
    - Right after that, the same session still gets 200. This read is not judged:
      the cache had not expired.
    - After the wait (60 s cache plus 5 s), `status` and `overview` give 403
      `forbidden`, both with `org=ta-org-r` and with no organization.
    - `[access] PASS removed-member`.
  - group-admin:
    - `ta-group-admin` has `groups=['admin']`, `is_superuser=False`,
      `is_staff=False`.
    - `status` with no organization and with `ta-org-a`: 200, with `first_day`,
      `days_ready` and `days_total`.
    - The overview for `ta-org-a` lists `['ta-worker', 'ta-supervisor']`, which is
      what the owner sees.
    - The overview with no organization lists 8 annotators, equal to what the
      superuser `ta-admin` sees.
    - `[access] PASS group-admin`.
  - personal-workspace:
    - `ta-admin`'s instance-wide details table with `search=ta-solo` gives
      `[('ta-solo', 1200000)]`, and project 49 (`ta-personal`) is listed.
    - In each of the 7 organizations, neither the row nor the project appears.
    - `[access] PASS personal-workspace`.
  - header-credentials:
    - With no credentials: 401 `not_authenticated`.
    - For 5 account/organization pairs on `status` and `overview`, each scheme gave
      the cookie's decision: 200, 403 `forbidden` (`ta-worker`, `ta-outsider` on
      `ta-org-a`), 403 `organization_required` (`ta-maintainer` with no
      organization), and 200 for `ta-group-admin` instance-wide. Overviews listed
      the same annotators.
    - A wrong Basic password and an unknown token: 401 `not_authenticated`.
    - `[access] PASS header-credentials (Basic)` and
      `[access] PASS header-credentials (Bearer)`.
- What CVAT itself answers. Probed through the proxy on the three identity endpoints
  the service asks (`/api/users/self`, `/api/organizations?slug=ta-org-a`,
  `/api/memberships?org=ta-org-a&user=ta-maintainer`):

  | Credential | Answer on all three |
  | --- | --- |
  | Read-only Bearer access token | 200 |
  | Basic with the right password | 200 |
  | Basic with a wrong password | 401, `Invalid username/password.` |
  | Unknown Bearer token | 401, `Invalid token.` |

  This settles both points part one left open. CVAT accepts a read-only token for
  these reads. It answers 401, not 403, to bad credentials, and the service passes
  that on as 401 `not_authenticated`. The token was revoked afterwards.

### Change made for the shared stack

Other agents add work to the stack while the cases run. Two comparisons read the
service twice, one read after the other, so a refresh in between could make them
differ without any rule being wrong:

- group-admin: the owner's view against the group admin's, and the superuser's
  instance view against the group admin's;
- header-credentials: an overview's annotators with the cookie against the same
  overview with the header.

`same_reads` in `access_cases.py` now reads such a pair again, up to 4 times, 3 s
apart, before judging a difference. Status and error are compared the same way, but
they do not move with other work, so a rule that decides differently still fails on
every attempt.

Stated check: called with stand-in readers, `same_reads` returns the matching pair
when the readers agree on a later attempt. When they never agree it returns the
differing pair after 4 attempts. In the live run, every pair matched on the first
read, so the retry was not used.

## Teardown, 2026-11-15

The live work of tickets 08 to 11, 25 and 26 was finished. The launcher was run from
branch `ticket/11-ingress-access` at `da7aaa28`, with the integration branch at
`273b266e` merged in. Times are UTC.

Before `down` (23:11):

- `run.sh status` reported namespace `cvat-ta-it-<user>` as Active and a running
  port-forward. The namespace was created 21:18 and held 14 pods.
- The namespace held Ingress `team-analytics`, class `nginx`, host
  `cvat-ta-it-<user>.k8s.docker.internal`.
- It had five Bound claims: `cvat-backend-data`, `cvat-kvrocks-data-cvat-kvrocks-0`,
  `data-cvat-clickhouse-shard0-0`, `data-cvat-postgresql-0` and
  `redis-data-cvat-redis-master-0`. Each was bound to its own persistent volume of
  the default class, with reclaim policy `Delete`.
- Host port 8490 was held by the launcher's `kubectl port-forward` to `svc/ta-proxy`.
- The launcher's state directory for the namespace held the run files, including the
  rendered `ingress.yaml` and the port-forward state.

`run.sh down` (23:11 to 23:12, exit 0) printed:

- `stopping port-forward`
- `deleting namespace cvat-ta-it-<user> (with every volume claim in it)`
- `nothing of cvat-ta-it-<user> remains`

`run.sh check-ingress-gone` (exit 0) printed: `no Ingress names
cvat-ta-it-<user>.k8s.docker.internal; the controller answers 404 for it`.

Looked at after `down` (23:12). Nothing was deleted by hand.

- The namespace is not found.
- No namespace carries the stack's `managed-by` label.
- No Ingress anywhere names the host. Only k8s-infra's three ClearML Ingresses remain.
- None of the five persistent volumes exists, and no persistent volume has a claim in
  the namespace.
- The port-forward process is gone. Nothing listens on 8490 in WSL, nor on Windows
  (`Get-NetTCPConnection`).
- The state directory for the namespace is absent.

So `down` left nothing behind of what the stack created: in the cluster (namespace,
Ingress, claims, volumes) and on the host (port-forward, host port, state directory).
Not looked at: the empty per-claim parent directories that the `hostpath`
provisioner leaves inside Docker Desktop's virtual disk (k8s-infra, "Storage"). They
are not visible from the cluster API.

## Unverified

- The retry in `same_reads` has not run live.
