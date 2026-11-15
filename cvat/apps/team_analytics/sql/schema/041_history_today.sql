-- Processed history of the current day, used only with a refresh window shorter than a day. Today's hours
-- before the window are then neither inside the ten-minute refresh nor part of a whole day yet. The history
-- step computes them once they have left the window and adds a row: every hour of that day (UTC) before
-- `computed_to`, where the window began, is computed. Only the newest row counts, and only for the day it
-- lies in: once that day is over it is computed as a whole like any other (history_days). Two workers
-- whose clocks straddle midnight can answer differently for a short time: the one still before midnight
-- reads yesterday's row as today's and may say a period is processed, the one past midnight says it is
-- not until that day is computed as a whole. The one that says processed is right (every hour up to
-- `computed_to` was computed); the other is only cautious. They agree once the whole-day step has run.
-- No `hour` column, so the superseded-row removal of refreshes leaves this table alone.
CREATE TABLE IF NOT EXISTS $totals_db.history_today
(
    computed_to DateTime('Etc/UTC'),
    at DateTime64(3, 'Etc/UTC')
)
ENGINE = MergeTree
ORDER BY computed_to
TTL computed_to + INTERVAL 30 DAY
