-- The cutover to the new activity logging: the hour of the first shape-tagged operation event on the
-- instance (any organization or personal workspace). Table `cutover` holds every hour the search stored
-- (control/cutover_find.sql); the earliest of them is the cutover, so it can only move earlier, and
-- workers that store at once leave one value. No row before one is stored.
SELECT min(at) AS cutover
FROM $totals_db.cutover
HAVING count() > 0
