-- Records `days` consecutive days from `first` as computed, with the raw event rows counted for them.
INSERT INTO $totals_db.history_days (day, raw_rows, pending, version, at)
SELECT addDays({first:Date}, number), {raw_rows:UInt64}, 0, {version:UInt64}, {at:DateTime64(3, 'Etc/UTC')}
FROM numbers({days:UInt32})
