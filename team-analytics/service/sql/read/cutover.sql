-- The cutover to the new activity logging: the hour of the first shape-tagged operation event on the
-- instance (any organization or personal workspace), as stored by control/cutover_find.sql. No row
-- before it is stored. The row stored first is the cutover, so it never moves.
SELECT at AS cutover
FROM $totals_db.cutover
ORDER BY found_at ASC, at ASC
LIMIT 1
