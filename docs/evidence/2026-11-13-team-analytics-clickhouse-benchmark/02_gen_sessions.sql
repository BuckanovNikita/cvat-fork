-- Work sessions: (day, user, slot). 5 fixed slots per day, 150 minutes apart, start jitter 0-20 min.
-- Weekdays: user present with p=0.92; weekends p=0.05; each slot used with p=0.8.
-- n = number of client events in the session, scaled by a per-user activity weight (0.3 .. 1.8).
-- Param: base_n (average client events per session before weighting).
DROP TABLE IF EXISTS gen_sessions;
CREATE TABLE gen_sessions ENGINE = MergeTree ORDER BY (day, user_id, slot) AS
WITH
  toDate('2025-11-14') AS d0,
  d0 + dnum AS day_,
  cityHash64(dnum, u, slot, 'sid') AS sid_,
  1 + cityHash64(u, 'np') % 3 AS nproj,
  1 + cityHash64(u, 'proj', cityHash64(u, intDiv(dnum, 3), 'pj') % nproj) % 40 AS project_,
  project_ * 100 + cityHash64(u, intDiv(dnum, 5), 't') % 20 AS task_,
  0.3 + 1.5 * (cityHash64(u, 'w') % 1000) / 1000 AS w
SELECT
  day_ AS day, toUInt64(u) AS user_id, toUInt8(slot) AS slot, sid_ AS sid,
  toUInt64(project_) AS project_id, toUInt64(task_) AS task_id,
  toUInt64(task_ * 10 + cityHash64(sid_, 'j') % 3) AS job_id,
  toDateTime64(day_, 3, 'Etc/UTC') + toIntervalMillisecond(
      6 * 3600000 + slot * 150 * 60000 + cityHash64(sid_, 'jit') % 1200000) AS start_ts,
  toUInt32({base_n:UInt32} * w * (0.7 + 0.6 * (cityHash64(sid_, 'n') % 1000) / 1000)) AS n
FROM (SELECT number AS dnum FROM numbers(365)) AS d
CROSS JOIN (SELECT number + 1 AS u FROM numbers(100)) AS us
CROSS JOIN (SELECT number AS slot FROM numbers(5)) AS sl
WHERE cityHash64(dnum, u, 'present') % 100 < if(toDayOfWeek(day_) <= 5, 92, 5)
  AND cityHash64(dnum, u, slot, 'slot') % 100 < 80;
