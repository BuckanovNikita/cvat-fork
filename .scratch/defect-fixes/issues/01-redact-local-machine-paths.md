# 01: Redact local machine paths

**What to build:** No tracked file and no captured run log shows a path of the machine the work was done on. The five tracked lines that carry one are redacted, and the stack launcher stops such a path from reaching a captured log. History is not rewritten; that is the owner's decision. See "Tooling" in the spec (`../spec.md`).

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] A search of the whole tracked tree for the local home prefix, binary files included, finds nothing.
- [x] The four run logs of the 2026-11-14 final run and the infrastructure migration note keep their meaning; only the path is replaced by a placeholder.
- [x] The launcher filters Helm's symbolic-link warning on every Helm call, not only when it renders the chart.
- [x] A captured log of one launcher command that calls Helm contains no local path. A full stack run is not needed for this.
- [x] No commit is rewritten.

## Comments

2026-11-14: Implemented on `ticket/01-redact-paths`. Evidence: `docs/evidence/2026-11-14-redact-local-paths.md`. Per criterion:

- Criterion 1. The search read every tracked file as bytes and looked for the prefix as
  written, through its `/home` alias, with other separators, URL-encoded, in UTF-16, hex
  and base64, and inside compressed content. Before: five lines in five files. After:
  nothing.
- Criterion 2. The prefix became `<home>` on the five lines; the diff is one line per
  file.
- Criterion 3. All four Helm calls go through one function, `helm_run`. Run and seen: the
  search that finds the `helm` binary called only inside it, the function against a
  stand-in `helm`, and `repo add` and `dependency build` against real Helm. Not run:
  `template` and `upgrade --install` against real Helm, which need a stack; no stack was
  started for this ticket.
- Criterion 4 was not ticked at this point; the next comment closes it. `run.sh
  fetch-chart` is the only command that calls Helm without the cluster. Its stderr held
  the warning with the local path before the change and holds no local path after it. Its
  stdout is one line that the command prints itself: the chart directory, then an absolute
  local path, so a capture of both streams together still held that path.
- Criterion 5. The branch only adds commits on top of `feat/team-analytics-page`; nothing
  before them was touched. The five lines are still in earlier commits, including the
  tree of `main`.
- Outside the five lines and left alone: `INFRA_MIGRATION.md` names the cluster's old
  volume directory on the host, and the stack's default namespace name ends in the
  machine user's name.

2026-11-14: Criterion 4 closed. It was decided that a captured log means stdout and stderr together, so the launcher must not print an absolute local path itself either.

- Every path the launcher prints goes through one function, `show_path`: relative to the
  repository root inside the repository, with `~` for the home directory under it,
  unchanged elsewhere. The last line of `fetch-chart` was the one line of the launcher
  that printed a path; no `log` or `die` message holds one. Nothing reads the output of
  `fetch-chart`.
- Run and seen: `run.sh fetch-chart` again with both streams in one file. Exit 0, Helm's
  lines all there, no line with the home prefix or its `/home` alias, no absolute path,
  and the chart directory on one line that starts with `~/`. Also `show_path` against
  made-up directories, including the repository-relative case that this run could not
  show while the chart lies in the cache.
- Limits, in the evidence under "Not verified": a path outside both the home directory
  and the repository is printed as it is; what Bash and the launcher's tools print when
  they fail does not go through `show_path`; `template` and `upgrade --install` are still
  not run against real Helm.
- `feat/team-analytics-page` was merged in at `e1d92b8` and the search of criterion 1 was
  repeated on the merged tree: nothing.

2026-11-14: Resolved on `feat/team-analytics-page` by merge `9fa742e`. Evidence: `docs/evidence/2026-11-14-redact-local-paths.md`.
