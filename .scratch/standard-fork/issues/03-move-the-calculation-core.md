# 03: Move the calculation core into the backend app

**What to build:** The service's calculation code and SQL files move into `cvat/apps/team_analytics/` unchanged and stay free of Django. The service keeps running as a thin shell over the moved code, so its whole suite still judges it. See "The app" in the spec.

**Blocked by:** 02.

**Status:** resolved

- [x] The periods, rows, withholding, SQL runner, cutover, history, refresh, step, endpoints and their sections, and every SQL file, live in the app; `Request` and endpoint discovery no longer live beside the service's dispatch.
- [x] The move is one commit that only moves and adjusts imports; no line of calculation or SQL changes.
- [x] The core imports nothing from Django.
- [x] The service suite passes unchanged in count on the moved code, on the default ClickHouse image.
- [x] The service image still builds and starts.
- [x] Formatting to upstream's black and isort settings is a separate commit that changes nothing else, with the suite rerun.

## Comments

2026-11-15: Moved in `5cdd1237` (renames, relative imports, `Scope` to `core/scope.py`, `Request` and discovery to `core/request.py`); formatted in `784e9e3f` (black 26.10.1 and isort 7.0.0 with the root `pyproject.toml`, nothing else in that commit). The service suite at `5cdd1237`, from a snapshot of the commit: 321 tests, none failed. The service image built from the moved code under a throwaway tag, and the service's shell loaded in it with its five endpoints; the tag was removed. `grep` finds no Django import under `core/`.

After the formatting commit only parts of the suite were run on the working tree (working time, HTTP, access, lease, refresh, isolation, status, entry point: 89 tests, none failed). The whole suite on the tip is running as this is written and is recorded with ticket 11.
