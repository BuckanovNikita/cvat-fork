-- Records that today's hours before `computed_to` (where the refresh window began) are computed.
INSERT INTO $totals_db.history_today (computed_to, at)
VALUES ({computed_to:DateTime('Etc/UTC')}, {at:DateTime64(3, 'Etc/UTC')})
