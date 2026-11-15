# 05: Technical accounts list (backend)

**What to build:** The Technical accounts list moves from the environment variable `TEAM_ANALYTICS_TECHNICAL_ACCOUNTS` into Postgres (item 5 of the spec), and the backend gains the actions the page needs: `settings`, `settings/users` and `project-names`, exactly as the spec's API contract states them.

- A model `TechnicalAccount` (`user_id` primary key with no foreign key, `user_name` as the last known name, `updated_date`) in a new `models.py` of `cvat/apps/team_analytics/`, with `migrations/0001_initial.py`. One list for the instance; a deleted user stays listed until removed.
- `GET` and `PUT settings`, `GET settings/users` and `GET project-names` on `TeamAnalyticsViewSet`, answered by the API process from Postgres, never through the read queue, with `Cache-Control: no-store`, and kept out of the OpenAPI schema. DRF's views already have a `settings` attribute, so the method gets another name and `url_path="settings"`. `PUT` replaces the list in one transaction, then advances the totals generation after the commit, and logs who added and removed which ids. A new `serializers.py` holds the validation rules.
- Permission: an `update` scope in `permissions.py` and policy rows for the new actions; the rego stays one administrators rule.
- The worker's read job reads the list after it reads the generation and passes the ids to `Engine.answer(...)` as a value; the core stays free of Django. The 31 predicates in 14 files under `sql/read/` match on `user_id` (`{technical_accounts:Array(UInt64)}`). The `technical_accounts` count in the answers stays. The variable no longer gives the list and leaves `core/config.py`; `default_settings.py` still looks at it once at start, only to warn that it is ignored.

**Blocked by:** 01.

**Status:** ready-for-agent

- [ ] New `verify/team-analytics-backend/tests/test_technical_accounts.py`: `PUT` refuses with 400 `bad_request` a non-list, a non-positive or non-integer id, a duplicate, more than 1000 ids, and a new id with no user; it keeps an id already listed whose user is gone; `GET` reports that id with its last known name and `deleted: true`, ordered by `user_name` then `user_id`.
- [ ] A save commits before the generation advances, and the worker reads the list after the generation, so an answer stored under the new generation is computed on the new list (shown by a test or by reading the two call orders, named in the comment).
- [ ] The calculation suite runs with `Stack(technical_accounts=(99,))` and passes, including new cases: a renamed technical account still counts as Model, an Annotator with the old name of a technical account counts as a person, and an empty list counts nobody as technical.
- [ ] `settings/users` returns at most 20 users of the whole instance, matching username, first or last name case-insensitively, ordered by username; a `search` over 150 characters gives 400.
- [ ] `project-names` returns the names of existing projects of any organization, leaves unknown ids out, and refuses more than 500 ids or a non-positive id with 400.
- [ ] Every new action is refused to non-administrators (403) and to signed-out callers (401) in the policy tests and the view tests; `makemigrations --check` passes; `test_api_side.py`'s module list includes the new modules.
- [ ] `TEAM_ANALYTICS_TECHNICAL_ACCOUNTS` no longer gives the list: the app looks at it only once at start, to warn that it is ignored; docs handoff recorded: TA-1's settings table, the Technical account entry of `GLOSSARY.md`, and an upgrade step in `docs/upstream-upgrade.md` (the list starts empty and is filled in the settings modal).

## Comments
