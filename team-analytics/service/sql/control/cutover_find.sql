-- Stores the cutover: the hour of the earliest shape-tagged operation event, by one streaming aggregate
-- over the raw events (no sort, no window). Operation events as in refresh/operations.sql: client rows of
-- a user inside a job, the operation scopes and the class change record, with `shape_type` in the payload.
-- Bounded by {until}: the end of the earliest stored hour holding a tagged operation (an operation is
-- stored in the hour of its last event, which is tagged), so nothing later is read. Stores nothing when
-- no such event is found.
INSERT INTO $totals_db.cutover (at)
SELECT toStartOfHour(toDateTime(min(timestamp), 'Etc/UTC'))
FROM $events_db.events
WHERE timestamp < {until:DateTime64(3, 'Etc/UTC')}
    AND source = 'client'
    AND user_id IS NOT NULL
    AND job_id IS NOT NULL
    AND (scope IN ('draw:object', 'paste:object', 'propagate:object', 'drag:object', 'resize:object', 'delete:object')
        OR (scope = 'debug:info' AND obj_name = 'team_analytics:class_change'))
    AND JSONHas(ifNull(payload, ''), 'shape_type')
HAVING count() > 0
