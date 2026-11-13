-- Removes rows of one versioned table (a totals table or hour_versions itself) that a newer refresh
-- replaced. An asynchronous mutation: readers already ignore these rows.
ALTER TABLE $totals_db.$table DELETE
WHERE hour >= {window_from:DateTime('Etc/UTC')} AND hour < {window_to:DateTime('Etc/UTC')}
    AND version < {version:UInt64}
