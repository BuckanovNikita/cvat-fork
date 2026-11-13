-- The stored totals live in a database of their own; CVAT's events table is only read.
CREATE DATABASE IF NOT EXISTS $totals_db
