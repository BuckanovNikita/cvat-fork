# Independent review of Team Analytics in the backend, 2026-11-15

Ticket 14 of `.scratch/standard-fork/`. Two reviewers that wrote none of the code read the
integrated branch at `05c86536`, read-only: one on access, isolation between organizations and
the read path; one on the refresh, the lock, the worker's jobs, failure isolation and delivery.
Each was given the code and the questions, not the author's conclusions. Neither ran the stack.
The second downloaded the pinned `rq`, `rq-scheduler`, `redis` and `django-rq` to read their
behaviour.

No finding was rated high. Neither found a way to figures without the permission check, a way
to another organization's figures, or an injection path into SQL.

## Found clean

- The permission check runs before the cache is consulted, for every combination of
  administrator or not, organization named, absent or unknown, `org`, `org_id` or the
  organization header, an inactive membership, and token credentials. Only GET and HEAD reach
  the view.
- The cache key cannot collide across organizations; an answer depends on nothing about the
  caller but the scope; a caller cannot write an entry another caller will read.
- Every value of a request reaches SQL as a bound parameter. The two database names and one
  table name substituted as text are checked as plain identifiers.
- The policy matches the specification: administrators anywhere, owners and maintainers of an
  active membership in their organization, nobody else.
- With analytics off nothing of the app is reachable or scheduled. Importing the app is
  harmless in every backend process, the scheduler included.
- History cannot be starved and the refresh of recent hours is not put off by reads.
- The fork's delta inside upstream's directories is exactly the specification's list.
- The server image equals a full build for the files it copies: owner, mode, compiled files,
  user and entry point.

## Fixed

| # | Finding | Rated | What was done |
| --- | --- | --- | --- |
| A1 | A parameter an endpoint does not read still made a new cache key and a new job, so one account could keep the shared read queue full with requests that differ only in an ignored value | medium | The API passes on only the parameters each endpoint reads. A test holds that list to what each endpoint really asks for |
| A2 | A refused value of up to 120,000 characters was repeated in the 400 answer, kept for fifteen minutes, and carried in the job, in the Redis that all of CVAT uses | medium | Each parameter has the length a valid value needs (`ids` keeps 100,000); a 400 is kept for seconds |
| A3 | A Redis that cannot be reached gave an unhandled 500, and the read job let a cache error out | low to medium | The endpoint answers 503; nothing in the read job is outside its handler |
| A4 | The generation was a clock value, and a waiting request accepts "the generation I saw or later": a worker whose clock is behind could make an old answer look new | low | The generation is a counter kept in the cache |
| A4 | A read job left "started" by a killed worker held its key at 429 until RQ's own clean-up | low | A job pending for longer than a read may take is queued again |
| A-N3 | A setting that is not a number stopped Django from starting, in the server and every worker | note | The value is reported and the default taken |
| R1 | A step that made hours visible and then failed, or lost the lock, did not advance the generation, so answers from before it stayed current | medium | A run advances the generation when a step did work, failed, or lost the lock. The run's rules moved to `core/run.py` and are tested |
| R2 | The periodic job is queued again every minute whether or not it was taken; the copies counted against the read queue's depth limit and as "a read is waiting" | medium | Only reads are counted; a run removes the copies of itself that piled up |
| R3 | A refresh statement had no limit on ClickHouse, where a client that gave up stops nothing | medium | Every statement of a refresh, of a day of history and of the control reads runs under `TEAM_ANALYTICS_REFRESH_STATEMENT_S` (300 s) unless it has a limit of its own |
| R4 | A waiting request held a Postgres connection through its wait | low to medium | It closes the connection before it waits |
| R6 | The image build did not see a renamed file, and shipped the working tree's tracked files while an untracked one would be missing | low | Renames count as a delete and an add; an untracked file under the copied directories refuses the build (provoked: it refuses and tags nothing) |
| R7 | The chart could not set the worker's replicas to zero | low | Zero is honoured (rendered with 0, with the default and with other values) |
| R10 | Nothing ran the refresh job's loop; one lock test used the same lock for both workers; the app was outside ruff | note | The run's rules are tested without Django; the lock tests use a second lock; ruff checks the app |

Checked after the fixes: see the acceptance record's last section.

## Recorded, not fixed

Each is stated in the fork specification as a limit.

- Any account that may create an organization owns it, and by default every account with the
  `user` role may. Such an owner reads their own organization's figures and `status`, which
  shows instance-wide state. This is the existing limit about what `status` shows a maintainer,
  with a wider circle of readers than "maintainers" suggests.
- There is no limit per account on waiting requests or queued reads. One account sending many
  different valid requests can fill the read queue and make others get 429. CVAT's own
  endpoints are not affected.
- A request that waits holds a thread for up to its wait. Upstream's frame chunks wait the
  same way.
- The steps exclude each other by a lock that the holder proves before each write. A statement
  that began under the lock runs on if the lock is lost, and a Redis that loses its data frees
  the lock under a live holder. Readers take the highest version of an hour, and a step's
  version is above every version marked when it began, so an overlap does not normally hide
  newer totals. It can when the older step marks later and its worker's clock is ahead of the
  other's: its version is then the higher one.
- Rows of a failed attempt on hours never marked before stay unread in the totals tables. The
  next computation of those hours marks them without removing the leftovers; they go at a later
  refresh that finds the hours already marked.
- A Redis that accepts connections and never answers holds a request for as long as it holds
  any other of CVAT's requests: the connections have no socket timeout, which is upstream's
  setting.
- If Redis loses its data the refresh schedule is gone until the initializer runs again, as
  for upstream's own periodic jobs.
- A refresh statement has a time limit and no memory limit of its own.
- Upstream's Compose files enable analytics on the server and start no analytics worker.
  Compose is unsupported.
- The calculation suite calls the engine as the worker's job does; the job, the view and the
  queue themselves run only on the stack. The check that the API side imports no calculation
  code reads the sources and would not see an import made at run time.
- `INFRA_MIGRATION.md` names a machine path of the cluster's volumes. It was in the published
  tree before this work.

## Second pass

The fixes above were themselves read by a third reviewer that wrote none of them, at
`b908b0c8`: the diff since the first review in the app, the settings file, the image build and
the chart template, with the paths no test and no stack run had executed named for it. It read
the pinned `rq`, `redis`, `rq-scheduler` and `django-rq` sources, and Django's from 4.2. Nothing
was rated high or medium.

Fixed in `df8d9379`:

| Finding | Rated | What was done |
| --- | --- | --- |
| The fix for a failed step advanced the generation for every failure. With ClickHouse unreachable each run fails at its first read, so the cache was emptied every minute where it is all there is | low to medium | A failed step advances the generation only if it had reached a write |
| A setting that is a number the feature cannot work with (a job timeout of 0, a negative queue limit, an infinite wait) broke every request, one of them as a 500 | low | Such a value is reported and the default taken |
| An unreadable job record or a value rq refuses escaped the view as a 500 | low | The view answers 503 for any failure of its cache or queue |
| A read job counted as abandoned 30 s after the latest moment a live one can end, less than rq's own minute of grace or a clock difference between two API processes | low | The margin is 120 s |
| A generation counter lost while answers stayed in the cache would restart at 1, below their generations, and a waiting request would take one of them for new | note | A counter started anew starts at the current time in seconds |
| A comment said the refresh's cutover search has no limit; the image build's messages split file names with spaces | note | Corrected |

Found clean in the second pass: every Redis failure in the request path is caught; closing the
database connection before the wait is safe under CVAT's settings (no request-wide transaction,
one database, later users reconnect); nothing the page sends is dropped or refused by the
parameter lists; the removal of piled-up refresh jobs cannot touch the running one; the
statement limit leaves schema creation and the removal of superseded rows as they were; the
chart template's handling of absent, zero and empty values; and the organization rule: `admin`
means administrators only, an unexpected value of the setting refuses everyone but
administrators, and no other path makes an account an organization's owner without an
administrator or the owner of that organization.

Recorded, not fixed:

- The annotator search of the details table is refused above 200 characters, and the page's
  input has no limit of its own.
- A run that is stopped by force advances no generation; answers are then older than the totals
  by up to a refresh interval or the answer's time to live.
- If a job taken for abandoned was in fact alive, its second copy can be lost when the first
  finishes; the request gets 429 and asks again.
- Django's cache and connection behaviour was read from 4.2, not from the 5.2 the image runs.

## Not established by either reviewer

2026-11-16: two of the lines below were closed on that date (the failed-job registry, and
Postgres connections and Redis memory under the load check's load); whether ClickHouse cancels
an insert stays open. See
[`2026-11-16-open-lines-closed-and-admin-settings.md`](2026-11-16-open-lines-closed-and-admin-settings.md).

- Whether ClickHouse cancels an insert whose client disconnected; the statement limit makes
  the answer matter less.
- Why the queue's failed-job registry once held the periodic job's id while the job's record
  said finished. The likelier reading is copies of one id running at once, which the removal
  of piled-up copies now prevents.
- Postgres connection counts and Redis memory under a real load.
