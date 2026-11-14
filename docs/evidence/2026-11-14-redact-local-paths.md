# Local machine paths redacted, 2026-11-14

Evidence for ticket 01 of the defect fixes
(`.scratch/defect-fixes/issues/01-redact-local-machine-paths.md`). The home directory of
the machine the work was done on is called the home prefix here and is not written out;
the commands below take it from `$HOME`.

## The search

Every tracked file was read as bytes, binary files included, together with the target of
the one tracked symbolic link and every file name. The prefix was searched for, without
regard to letter case, in these forms:

- as written, and as the same directory reached through `/home`, where on this machine a
  symbolic link named after the user points to it;
- with anything of up to six bytes between its components, which covers backslashes,
  escaped slashes and percent-encoded slashes at once;
- URL-encoded once and twice, with JSON-escaped slashes, with single and with doubled
  backslashes, and with dashes or underscores in place of the slashes (the form agent
  tooling gives its directory names);
- in UTF-16 of both byte orders, as hexadecimal digits, and in base64 at its three
  alignments;
- inside compressed content: gzip, zip and tar members, and every zlib stream found
  anywhere in a file, which is how PDF streams and PNG chunks are stored.

The script that did this is not committed. Before it was trusted it was run on a
throwaway repository holding one file per form, and it reported each of them.

Anyone can repeat the plain form of the search (`-a` reads binary files as text):

```
git grep -a -i -n -F "$HOME"
git grep -a -i -n -F "/home/$(id -un)"
```

| Tree | Result |
| --- | --- |
| `e2f0499`, before the ticket | Five lines in five files, all in the plain form: one line in each of `run-up1.log`, `run-up2.log`, `run-up-review-fixes.log` and `run-up-review-fixes-2.log` under `docs/evidence/2026-11-14-team-analytics-final-run/`, with the prefix twice on the line, and the last line of `INFRA_MIGRATION.md`. No other form anywhere |
| The ticket branch, with this file in it | Nothing in any form. Both commands above print nothing |

## The redaction

On the five lines the prefix is replaced by `<home>` and nothing else changed: the diff
of commit `7af9626` is one line out and one line in for each of the five files. A log line
still names the chart build directory, with the upstream commit and the lock checksum in
its name, and both ends of the symbolic link. The migration note still names the plan's
file in the infrastructure repository.

No commit was rewritten. The commits that introduced the five lines, and every tree
between them and this ticket, still carry the prefix; so does the tree of local `main`
(`6cedd04`). The fix plan records that `main` was pushed on 2026-11-14; the remote was not
looked at here. What to do about history is the owner's decision.

## The launcher

`verify/team-analytics-stack/run.sh` runs Helm in four places: `repo add`,
`dependency build`, `template` and `upgrade --install`. It dropped Helm's symbolic-link
warning, which carries the chart's full local path, only on `template`. Since commit
`8ab01db` all four go through one function, `helm_run`, with the filter that `template`
had: the line `found symbolic link in path` is dropped from Helm's stderr and every other
message is kept.

### Live outcome

`run.sh fetch-chart` is the launcher's only command that calls Helm without touching the
cluster: it runs `helm repo add` for the five dependency repositories and
`helm dependency build`. It was run twice, once before the change and once after, each
time through the shared lock and with a temporary cache directory under the home
directory that held nothing but the chart source, so that the chart was built again and
its path lay under the prefix. The chart source was copied from the copy already
downloaded on this machine; nothing was fetched from upstream, the dependency charts came
from their repositories. Helm v3.16.3. stdout and stderr were captured apart.

| | Before the change, 13:28-13:30 UTC | After, 13:31-13:38 UTC (most of it waiting for the lock) |
| --- | --- | --- |
| Exit status | 0 | 0, and the launcher's check of the dependency archives against `chart-deps.sha256` passed |
| Lines on stderr | 23 | 22 |
| Lines on stderr with the home prefix | 1: the symbolic-link warning, printed by `helm dependency build` | 0 |
| Difference between the two stderr captures, order aside | | that one line |
| stdout | one line, the chart directory | the same |

The stderr of the second run, whole:

```
[ta-stack] building chart dependencies from the pinned Chart.lock
"ta-dep-1" has been added to your repositories
"ta-dep-2" has been added to your repositories
"ta-dep-3" has been added to your repositories
"ta-dep-4" has been added to your repositories
"ta-dep-5" has been added to your repositories
Hang tight while we grab the latest from your chart repositories...
...Successfully got an update from the "ta-dep-4" chart repository
...Successfully got an update from the "ta-dep-3" chart repository
...Successfully got an update from the "ta-dep-5" chart repository
...Successfully got an update from the "ta-dep-2" chart repository
...Successfully got an update from the "ta-dep-1" chart repository
Update Complete. ⎈Happy Helming!⎈
Saving 7 charts
Downloading postgresql from repo https://charts.bitnami.com/bitnami
Downloading nuclio from repo https://nuclio.github.io/nuclio/charts
Downloading vector from repo https://helm.vector.dev
Downloading clickhouse from repo https://charts.bitnami.com/bitnami
Downloading grafana from repo https://grafana.github.io/helm-charts
Downloading traefik from repo https://helm.traefik.io/traefik
Downloading redis from repo https://charts.bitnami.com/bitnami
Deleting outdated charts
```

### Checks with supplied boundaries

- `bash -n` on the launcher passes, and the launcher run with no command prints its usage.
- A search of the launcher for `helm` as a command word finds it once, inside `helm_run`.
  The four calls are `helm_run repo add`, `helm_run dependency build`, and
  `"${H[@]}" template` and `"${H[@]}" upgrade --install`, where `H` starts with
  `helm_run`. Nothing puts `nice`, `env` or `command` in front of them.
- `helm_run`, taken from the launcher and run against a stand-in `helm` that prints a
  manifest on stdout and the warning plus two other messages on stderr:

  | Case | Seen |
  | --- | --- |
  | A successful call | exit 0; stdout unchanged, including a manifest line that holds the warning's words; stderr is the two other messages in order; the arguments reach `helm` unchanged |
  | `helm` exits 7 | `helm_run` returns 7; no path on stderr |
  | `helm` prints the warning and nothing else | exit 0, empty stderr |
  | stdout joined to stderr at the call, as the install does | every line but the warning arrives |

## Not verified

- **The path that `fetch-chart` prints itself.** The command ends by printing the chart
  directory on stdout, an absolute local path, by design; it is not Helm's output and the
  filter does not touch it. A capture of stdout and stderr together would therefore hold
  one local path. This ticket left the command's output as it was. Ticket 08 replaces the
  chart download this command belongs to.
- **`template` and `upgrade --install` through `helm_run` against real Helm.** Both need
  the stack, and no stack was started for this ticket. What stands for them: the search
  and the stand-in above, the live `dependency build`, and the four run logs of the
  2026-11-14 final run, where the same filter kept the warning out of `template` while
  `upgrade --install`, then unfiltered, printed it. The next fresh `up` (ticket 08) shows it.
- `shellcheck` is not installed on this machine and was not run.

## Also seen, not changed

- `INFRA_MIGRATION.md`, step 4 of its required outcome, names the cluster's old volume
  directory on the host. It is a machine path outside the home directory, and the line
  exists to say which references to remove.
- The stack's default namespace name ends in the machine user's name (`TA_RUN_ID`
  defaults to `$USER`), so the name appears in the run logs and in the two evidence files
  about the stack. It is a namespace name, not a path.
