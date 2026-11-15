-- Whether a refresh handed any hour of the window to itself before (so older rows may need removing).
SELECT count() > 0 AS marked
FROM $totals_db.hour_versions
WHERE hour >= {window_from:DateTime('Etc/UTC')} AND hour < {window_to:DateTime('Etc/UTC')}
