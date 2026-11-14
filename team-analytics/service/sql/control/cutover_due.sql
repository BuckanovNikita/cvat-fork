-- Whether the cutover is to be found now: no cutover is stored and the stored totals (any hour, any
-- version) hold a shape-tagged operation. One row with the earliest such hour, else no row.
SELECT min(hour) AS tagged_hour
FROM $totals_db.operations_hourly
WHERE shape != 'untagged'
HAVING count() > 0 AND (SELECT count() FROM $totals_db.cutover) = 0
