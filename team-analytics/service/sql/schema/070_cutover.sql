-- The cutover to the new activity logging, stored once it is known (see team_analytics/cutover.py). The row
-- written first is the cutover; it never moves.
CREATE TABLE IF NOT EXISTS $totals_db.cutover
(
    at DateTime('Etc/UTC'),
    found_at DateTime64(3, 'Etc/UTC') DEFAULT now64(3, 'Etc/UTC')
)
ENGINE = MergeTree
ORDER BY found_at
