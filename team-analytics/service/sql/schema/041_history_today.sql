-- Processed history of the current day, used only with a refresh window shorter than a day. Today's hours
-- before the window are then neither inside the ten-minute refresh nor part of a whole day yet. The history
-- step computes them once they have left the window and adds a row: every hour of that day (UTC) before
-- `computed_to`, where the window began, is computed. The newest row of a day counts. When the day is over
-- it is computed as a whole like any other (history_days) and its rows here mean nothing any more.
-- No `hour` column, so the superseded-row removal of refreshes leaves this table alone.
CREATE TABLE IF NOT EXISTS $totals_db.history_today
(
    computed_to DateTime('Etc/UTC'),
    at DateTime64(3, 'Etc/UTC')
)
ENGINE = MergeTree
ORDER BY computed_to
TTL computed_to + INTERVAL 30 DAY
