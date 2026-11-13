---
status: accepted
---

# New measurements travel inside existing event types

The backend is the stock CVAT image, and it accepts client events only from a fixed list of types. One unknown type makes it reject the whole batch, and the client then resends that batch indefinitely, which stops all event logging and working time for that user. So everything Team Analytics needs that CVAT does not record (shape type, class change, detector use, hotkey and mouse counts) is added either as extra payload fields on events that already exist or as records of the existing `debug:info` type, told apart by name. No new event type is introduced.

## Consequences

- A class change or a hotkey summary appears in the events table as `debug:info`. That is deliberate; do not "fix" it by adding a proper event type unless the backend is also changed.
- These measurements exist only from the day the logging is deployed. Earlier periods are legacy periods and show less.
- Hotkey and mouse use is counted in the browser and sent as one summary record per interval rather than one event per key. An event per key would break the server's compression of frame changes and inflate the events table.
- The added logging can never break annotation. Each call into it is guarded so that it cannot throw into the code that called it, and sending is fire-and-forget.
- Every new record is logged through the job, with its project, task and job. The server credits working time to the identifiers of the preceding event, so a record without them would move working time off the job.
