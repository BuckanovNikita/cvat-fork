# 10: Task progress checked on the stack

**What to build:** The task-progress summary on the tasks list is checked on the Kubernetes stack. Its live check existed only as a Compose launcher, which no longer runs. See "Stack and removals" in the spec (`../spec.md`).

**Blocked by:** 08 (The stack runs on the fork server image and the in-tree chart).

**Status:** ready-for-agent

- [ ] The stack seeds tasks that cover every job stage and state, as the Compose seed did.
- [ ] The browser check of the tasks list runs against the stack with the fork's UI image and passes.
- [ ] What the Compose launcher prepared and checked is listed in this ticket beside what the stack now does; nothing it covered is dropped.
- [ ] The check is part of the launcher's run and is judged pass or fail.
- [ ] The result is kept in a dated evidence file.
