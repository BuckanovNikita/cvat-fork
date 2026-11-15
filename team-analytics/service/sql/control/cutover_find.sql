-- Looks for the cutover in the recorded events and stores what it finds: the hour of the earliest
-- shape-tagged operation event before {until}. The events table is ordered by timestamp, so the statement
-- reads it in that order and stops at the first match; with no match (every search once a cutover is
-- stored) it reads every row before {until}, as the earlier aggregate did, and at the benchmark's scale takes
-- about as long (docs/evidence/2026-11-14-cutover-search-cost.md, 2026-11-15). Operation events as in
-- refresh/operations.sql: client rows of a user inside a job, the operation scopes and the class change
-- record, with `shape_type` in the payload.
-- {until} bounds the search from above, so nothing later is read (the callers are in cutover.py): the stored
-- cutover, when there is one, so that only an earlier hour can be found; without one, the end of the current
-- hour, or in a refresh the end of the earliest stored hour holding a tagged operation (an operation is
-- stored in the hour of its last event, which is tagged). Stores nothing when no such event is found. Rows
-- are only added; read/cutover.sql takes the earliest.
INSERT INTO $totals_db.cutover (at)
SELECT toStartOfHour(toDateTime(timestamp, 'Etc/UTC'))
FROM $events_db.events
WHERE timestamp < {until:DateTime64(3, 'Etc/UTC')}
    AND source = 'client'
    AND user_id IS NOT NULL
    AND job_id IS NOT NULL
    AND (scope IN ('draw:object', 'paste:object', 'propagate:object', 'drag:object', 'resize:object', 'delete:object')
        OR (scope = 'debug:info' AND obj_name = 'team_analytics:class_change'))
    AND JSONHas(ifNull(payload, ''), 'shape_type')
ORDER BY timestamp
LIMIT 1
