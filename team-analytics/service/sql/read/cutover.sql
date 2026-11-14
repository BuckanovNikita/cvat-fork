-- The cutover to the new activity logging: the hour of the first shape-tagged operation on the instance
-- (any organization or personal workspace), from the stored totals. No row when there is none yet.
-- History processing can move it earlier as older days are computed.
SELECT hour AS cutover
FROM $totals_db.operations_hourly
WHERE shape != 'untagged'
ORDER BY hour ASC
LIMIT 1
