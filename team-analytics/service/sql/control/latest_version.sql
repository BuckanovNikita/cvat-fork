-- The newest version any refresh has marked; a new refresh takes a larger one.
SELECT max(version) AS version FROM $totals_db.hour_versions
