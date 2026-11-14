# Frontend harness and its browser environment, 2026-11-14

Seams 2 and 3 (`verify/team_analytics_logging.cjs`, `verify/team_analytics_page.cjs`)
mount UI code in jsdom. The harness took jsdom from `cvat/node_modules`, where it
is present only because another package of the import lists it as an optional
dependency, and it gated the tests that need a DOM on whether jsdom loaded.

Everything below was run on one host with Node 22.22.1 and npm 9.2.0.

## Before the fix (`e2f0499`)

jsdom was made unavailable without touching the shared dependency directory:
in one worktree, `cvat/node_modules` pointed at a directory of links to every
entry of the real one except `jsdom`.

| Suite | Exit code | Result |
| --- | --- | --- |
| `node --test verify/team_analytics_page.cjs` | 0 | 140 pass, 62 skipped with "jsdom is not installed in cvat/node_modules" |
| `node --test verify/team_analytics_logging.cjs` | 1 | 41 pass, 12 skipped with "jsdom does not load", 2 fail |
| `node --test verify/task_progress.cjs` | 0 | 20 pass, 1 skipped (no `BROWSER_BIN`) |

The page run passed with a third of its tests skipped. The logging run did
fail, but by accident: two tests of the closing summary call the DOM helper
without a gate and stopped on `Cannot read properties of null (reading
'document')`, which does not name jsdom. The twelve keyboard-and-mouse tests
skipped themselves. With jsdom present the same tree gave 206 and 55 passes,
none skipped.

## After the fix (`3a306e6`)

`verify/package.json` declares jsdom and `verify/package-lock.json` locks it,
at the version the import's lock resolves for that optional dependency, so the
suites run on the jsdom they ran on before. `verify/browser-environment.cjs`
loads it from `verify/node_modules` by path and throws when it does not load.
Both helpers require that file as they load. The gates in twelve page test
files and in the logging keyboard-and-mouse file are removed.

| State of `verify/node_modules` | Page suite | Logging suite | Task progress |
| --- | --- | --- | --- |
| Installed with `npm ci --prefix verify` | exit 0, 206 pass, 0 skipped | exit 0, 55 pass, 0 skipped | exit 0, 20 pass, 1 skipped (no `BROWSER_BIN`) |
| Moved away; `cvat/node_modules/jsdom` still present | exit 1 | exit 1 | exit 0, 20 pass, 1 skipped |
| Moved away; a jsdom reachable by name from a parent directory | exit 1 | exit 1 | not run |
| One dependency of jsdom removed | exit 1 | exit 1 | not run |
| A link to a `node_modules` directory installed elsewhere | exit 0, 206 pass, 0 skipped | exit 0, 55 pass, 0 skipped | not run |
| Installed again from the lock | exit 0, 206 pass, 0 skipped | exit 0, 55 pass, 0 skipped | exit 0, 20 pass, 1 skipped |

In each failing run `node --test` reports the suite file as its one failed
test and prints the message, with either reporter:

```text
Error: jsdom, the browser environment of the frontend suites, did not load from verify/node_modules: Cannot find module 'verify/node_modules/jsdom'. Install the harness's dependencies: npm ci --prefix verify
```

With one dependency removed the message names it instead (`Cannot find module
'tough-cookie'`).

The second and third rows show that the harness does not fall back to the
import's copy or to any other copy. The first version of the loader
(`75048a1`) resolved jsdom by name and passed the second row too, but on this
host Node also searches a system-wide module directory, from which one
optional helper of a jsdom dependency does load; a jsdom installed there would
have been used silently. The loader therefore requires the installed path.

Other observations:

- `npm ci --prefix verify` exits 0 and leaves the lock unchanged. The lock
  names 70 packages, all resolved from the public npm registry, none with an
  install script. npm prints deprecation notices for four of them.
- npm resolved jsdom's own dependencies afresh, so nine of them are newer than
  the copies in `cvat/node_modules` (the selector engine among them). The
  totals above are the same as with the old copies.
- jsdom no longer reaches the import's `canvas` package, whose binary is not
  built; its canvas binding is empty after loading. The code that hid that
  package while jsdom loaded is removed.
- `git status` shows neither the directory nor a link at
  `verify/node_modules`; the ignore rule has no trailing slash.

## Supplied boundaries

- "Unavailable" after the fix is the state of a fresh checkout: no
  `verify/node_modules`. It was produced by moving the directory away and back,
  and once by a real `npm ci` into an absent directory.
- The link was checked against a copy of the installed directory placed
  outside the repository, in a directory named `node_modules`. No other
  checkout was changed. A link to a directory with another name fails, because
  jsdom's dependencies are looked up beside it by that name.

## Not verified

- The task-progress browser check was not run with a browser.
  `verify/task_progress.cjs` is unchanged and loads neither jsdom nor the new
  file.
- Other versions of Node and npm, and an install without network access or a
  warm npm cache.
- Any newer jsdom. The pin keeps the test environment as it was; moving it is a
  separate change.

## Changed

`verify/package.json`, `verify/package-lock.json`,
`verify/browser-environment.cjs`, the two helpers and the two suite entry
files under `verify/`, twelve page test files and one logging test file,
`.gitignore`, and the frontend and Team Analytics parts of section 4 of
`docs/upstream-upgrade.md`. No file under `cvat/` is changed.
