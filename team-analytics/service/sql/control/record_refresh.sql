-- Records a refresh that finished: its hours are marked and readers already see its totals.
INSERT INTO $totals_db.refresh_runs (data_as_of, version, window_from, window_to)
VALUES ({data_as_of:DateTime64(3, 'Etc/UTC')}, {version:UInt64},
        {window_from:DateTime('Etc/UTC')}, {window_to:DateTime('Etc/UTC')})
