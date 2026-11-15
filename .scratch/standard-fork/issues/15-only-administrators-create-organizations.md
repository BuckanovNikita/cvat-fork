# 15: Only administrators create organizations

**What to build:** An account that is not an administrator cannot create an organization. Decided by the owner on 2026-11-15, after the independent review found that an organization's owner reads its Team Analytics and that, by upstream's default, every account with the `user` role may create an organization and so make itself a reader. The owner's words: "Allow user see only their organizations. All org stats available only for admins" and "If role is not MAINTAINER or admin user has no access to stat. Disallow users create organizations if they are not admins".

**Blocked by:** 14.

**Status:** resolved

- [x] The fork's default for who may create an organization is the administrator; upstream's environment variable still overrides it.
- [x] On the stack, accounts with the `user` and the `worker` role, and an owner or maintainer of an organization, are refused when they try to create one, and no organization is left behind; an administrator creates one.
- [x] The seeded organizations and their owners' and maintainers' access to Team Analytics are unaffected.
- [x] The access rule for the figures is as the owner states it: administrators read any organization or the whole instance; owners and maintainers read their own organization; nobody else reads anything; instance scope is the administrators' alone.
- [x] The fork specification states the rule, that it changes CVAT for every user of the fork, and what it does not reach: organizations created earlier keep their owners.

## Comments

2026-11-15: The fork sets `ORGANIZATIONS_MIN_ROLE_TO_CREATE` to `admin` in its lines of `cvat/settings/base.py`, on every instance. Inside the built server image the setting reads `admin`, and `user` when upstream's `CVAT_ORGANIZATIONS_MIN_ROLE_TO_CREATE` says so. The launcher gained `check-org-creation`, part of every `up`. It ran in the fresh install of the default stack: four accounts that are not administrators (the `user` role in no organization, the `worker` role, an owner and a maintainer of an organization) were refused with 403 and nothing was created; the administrator created an organization (201), which the check removed again; the two seeded organizations answered their maintainers' `status` with 200. That `up` passed whole, with the access cases and the Team Analytics checks, so the access rule for the figures is as it was. The check pipeline passed with twelve hooks.

The fork specification states the rule as IAM-2. Not changed: CVAT's interface still offers "Create" to every user, whose attempt ends in the server's 403; organizations made before the rule keep their owners. Not run: joining an organization by invitation under the rule; it is read as unaffected, since the setting is used only by the create rule.
