# 13: One gate for a change

**What to build:** One command checks a change the same way every time: the linters, the type check, the policy test and the fast suites. A hook pipeline holds the commands. The owner chose how the lint configuration arrives but was not asked whether the gate should be a hook pipeline; that is a default. See "Tooling" in the spec (`../spec.md`).

**Blocked by:** 02 (Frontend tests fail without their browser environment), 05 (First lint run on the fork's UI code), 06 (Policies patched in place with the role floor).

**Status:** ready-for-agent

- [ ] A hook pipeline configuration holds ESLint, stylelint and the type check on the fork's UI code, ruff on the fork's Python, the policy test, and the three fast frontend suites.
- [ ] The pipeline's all-files run passes on the branch.
- [ ] It fails when a lint error is introduced, when a policy expectation is broken and when a frontend test fails. Each is shown once and noted in this ticket.
- [ ] Hooks check and change only files the fork owns or edited; they never reformat untouched upstream files of the import.
- [ ] Tool versions come from the project's dependency configuration.
- [ ] The suites that need ClickHouse or the stack are not in the pipeline; they are documented as separate commands with their prerequisites.
- [ ] The invocation and its prerequisites are written in one place.
