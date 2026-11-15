-- Which refresh owns each stored hour. A refresh writes all of its totals tables with one version,
-- then marks every hour of its window with that version; readers take, per hour, only rows of the
-- hour's newest marked version. An hour is thereby replaced as a whole, at once, and an hour that a
-- later refresh found empty reads as empty. Superseded rows are removed after the marking.
CREATE TABLE IF NOT EXISTS $totals_db.hour_versions
(
    hour DateTime('Etc/UTC'),
    version UInt64
)
ENGINE = MergeTree
ORDER BY (hour, version)
