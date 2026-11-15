# 12: Delete the service

**What to build:** The separate service and everything that existed only for it are removed.

**Blocked by:** 11.

**Status:** resolved

- [x] `team-analytics/`, its build script, the service's access code, HTTP server and entry point, the lease's SQL and table, and their tests are gone.
- [x] The calculation tests live in `verify/team-analytics-backend/` and pass.
- [x] Nothing in the repository outside history, dated evidence and resolved tickets names the service's address or its settings.
- [x] The check pipeline passes.

## Comments

2026-11-15: `d00afd9c`. Removed: `team-analytics/`, `build-team-analytics-service.sh`, `verify/team_analytics_service.sh`, the lease's code in `core/refresh.py`, its three control files and its table definition, and the settings only the service read. A totals database made earlier keeps an unused `refresh_lock` table.

The calculation tests are in `verify/team-analytics-backend/`, run by `verify/team_analytics_backend.sh`: 318 tests, none failed, on the tree of this commit (1,199 s, default ClickHouse image). They are the old tree's 361, less 41 that tested the deleted HTTP server, entry point, shutdown, access check and lease, less 7 inside kept files (five asserting who is refused, one comparing the engine with the service, one starting the service's process), plus 5 converted (four on what each scope sees in the overview, one on work done after the lock was lost). No expectation was changed to make a test pass. Not run on the second ClickHouse image after the move; the suite before the move passed on both.

`git grep` over tracked files outside dated evidence and `.scratch/` finds no mention of the service's address, its settings, its image or its paths. The page's own texts still call what it asks "the analytics service" (the error panel and the access hint); they are user-facing wording and were left. The check pipeline passed with twelve hooks. `./build-server.sh` rebuilt `cvat/server:v2.82.0-fork` (`0eb0b3582fb8`) from this tree with its three checks passing.
