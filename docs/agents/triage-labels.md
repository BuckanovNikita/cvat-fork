# Triage Labels

The skills speak in terms of five canonical triage roles. Each is a Linear label in team `SIP`, kept separate from the issue's lifecycle state.

| Label in mattpocock/skills | Label in Linear   | Meaning                                                      |
| -------------------------- | ----------------- | ------------------------------------------------------------ |
| `needs-triage`             | `needs-triage`    | Maintainer needs to evaluate this issue                      |
| `needs-info`               | `needs-info`      | Waiting on reporter for more information                     |
| `ready-for-agent`          | `ready-for-agent` | Fully specified, ready for an AFK agent                      |
| `ready-for-human`          | `ready-for-human` | Requires human implementation                                |
| `wontfix`                  | `wontfix`         | Will not be actioned; set the lifecycle state to Canceled    |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label from this table.

An issue carries one readiness label at a time; wayfinding maps and tickets carry none ([wayfinding operations](issue-tracker.md#wayfinding-operations)). Readiness does not override blockers, verification or the human merge. Completion evidence belongs in the issue and its linked PR and evidence, not in a label.
