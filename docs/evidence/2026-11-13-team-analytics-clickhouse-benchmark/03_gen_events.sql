-- Expand sessions into events for days [d_from, d_to). Run month by month (see load.sh).
-- Gaps inside a session: 97.7% 1-9 s, 2% 60-240 s (think pauses, some over 100 s),
-- 0.3% 300-600 s (splits the session by the 5-minute rule).
-- Payload is written the way Python json.dumps writes it (": " and ", " separators),
-- because that is how CVAT's server stores it.

-- ---------- client events ----------
INSERT INTO events
WITH
  cityHash64(h, 's') % 1000 AS r,
  cityHash64(h, 'x') AS x,
  cityHash64(sid, intDiv(i, 6), 'obj') AS bh,          -- "current object" changes every 6 events
  multiIf(r < 300, 'zoom:image', r < 500, 'change:frame', r < 620, 'draw:object',
          r < 740, 'resize:object', r < 800, 'drag:object', r < 830, 'delete:object',
          r < 850, 'paste:object', r < 860, 'propagate:object', r < 940, 'click:element',
          r < 980, 'debug:info', r < 990, 'save:job', 'lock:object') AS scope_,
  multiIf(scope_ = 'debug:info', if(r < 960, 'change:label', 'input:stats'),
          scope_ = 'click:element', ['Save', 'Next', 'Previous', 'Menu'][1 + x % 4],
          NULL) AS obj_name_,
  (scope_ = 'click:element' AND x % 4 = 0) AS no_job,   -- client rows not bound to a job
  (scope_ IN ('draw:object', 'resize:object', 'drag:object', 'delete:object', 'paste:object', 'propagate:object')
     OR obj_name_ = 'change:label') AS is_shape_op,
  ['SWITCH_DRAW_MODE_STANDARD_CONTROLS', 'NEXT_FRAME', 'PREV_FRAME', 'SAVE_JOB', 'UNDO', 'REDO',
   'DELETE_OBJECT', 'SWITCH_LOCK', 'SWITCH_HIDDEN', 'COPY_SHAPE', 'PASTE_SHAPE', 'SWITCH_LABEL',
   'FORWARD_FRAME', 'BACKWARD_FRAME', 'NEXT_KEY_FRAME', 'CANCEL'] AS key_names,
  arrayStringConcat(arrayMap(k -> concat(', "key.', k, '": ', toString(1 + cityHash64(h, k) % 40)),
       arrayFilter(k -> cityHash64(h, k, 'on') % 100 < 40, key_names))) AS key_part,
  concat(', "mouse.canvas": ', toString(x % 200), ', "mouse.controls": ', toString(x % 13),
         ', "mouse.objects": ', toString(x % 7)) AS mouse_part,
  cityHash64(h, 'shape') % 100 AS sr
SELECT
  scope_ AS scope,
  obj_name_ AS obj_name,
  if(scope_ IN ('resize:object', 'drag:object', 'delete:object') AND bh % 5 != 0, toUInt64(bh % 100000 + 1), NULL) AS obj_id,
  CAST(NULL AS Nullable(String)) AS obj_val,
  'client' AS source,
  start_ts + toIntervalMillisecond(off) AS timestamp,
  CAST(NULL AS Nullable(UInt16)) AS count,
  toUInt32(multiIf(scope_ = 'draw:object', 3000 + x % 17001,
                   scope_ IN ('resize:object', 'drag:object'), 500 + x % 3501,
                   scope_ = 'change:frame', 100 + x % 1901, 0)) AS duration,
  if(no_job, NULL, project_id) AS project_id,
  if(no_job, NULL, task_id) AS task_id,
  if(no_job, NULL, job_id) AS job_id,
  user_id,
  concat('user_', toString(user_id)) AS user_name,
  concat('user_', toString(user_id), '@example.com') AS user_email,
  toUInt64(1) AS org_id, 'org1' AS org_slug,
  concat('{"client_id": "', toString(1000000000 + sid % 8999999999), '", "is_active": true, "frame": ',
         toString(x % 5000), ', "tab_id": "', lower(hex(h)), '"',
         multiIf(is_shape_op,
                   concat(', "shape_type": "', multiIf(sr < 80, 'rectangle', sr < 92, 'polygon', sr < 97, 'points', 'mixed'),
                          '", "input_method": "', if(x % 3 = 0, 'mouse', 'hotkey'),
                          '", "object_type": "shape", "label_id": ', toString(x % 30)),
                 obj_name_ = 'input:stats', concat(key_part, mouse_part),
                 concat(', "location": "/tasks/', toString(task_id), '/jobs/', toString(job_id), '"')),
         '}') AS payload,
  CAST(NULL AS Nullable(UInt64)) AS access_token_id,
  concat('10.0.', toString(user_id % 250), '.', toString(1 + user_id % 200)) AS remote_addr
FROM
(
  SELECT *,
    arrayMap(j -> cityHash64(sid, j), range(n)) AS hs,
    arrayCumSum(arrayMap(g -> multiIf(g % 1000 < 3, 300000 + intDiv(g, 1000) % 300000,
                                      g % 1000 < 23, 60000 + intDiv(g, 1000) % 180000,
                                      1000 + intDiv(g, 1000) % 8000), hs)) AS offs
  FROM gen_sessions
  WHERE day >= {d_from:Date} AND day < {d_to:Date}
)
ARRAY JOIN hs AS h, offs AS off, arrayEnumerate(hs) AS i
SETTINGS max_block_size = 300;

-- ---------- server events: send:working_time about every 90 s of session activity ----------
INSERT INTO events
SELECT
  'send:working_time' AS scope, 'working_time' AS obj_name, CAST(NULL AS Nullable(UInt64)) AS obj_id,
  CAST(NULL AS Nullable(String)) AS obj_val, 'server' AS source,
  start_ts + toIntervalMillisecond((k + 1) * 90000 + cityHash64(sid, k, 'wj') % 997) AS timestamp,
  CAST(NULL AS Nullable(UInt16)) AS count,
  toUInt32(60000 + cityHash64(sid, k, 'wd') % 30001) AS duration,
  project_id, task_id, job_id, user_id,
  concat('user_', toString(user_id)) AS user_name, concat('user_', toString(user_id), '@example.com') AS user_email,
  toUInt64(1) AS org_id, 'org1' AS org_slug,
  concat('{"working_time": ', toString(duration), '}') AS payload,
  CAST(NULL AS Nullable(UInt64)) AS access_token_id,
  concat('10.0.', toString(user_id % 250), '.', toString(1 + user_id % 200)) AS remote_addr
FROM
(
  SELECT *,
    arraySum(arrayMap(g -> multiIf(g % 1000 < 3, 300000 + intDiv(g, 1000) % 300000,
                                   g % 1000 < 23, 60000 + intDiv(g, 1000) % 180000,
                                   1000 + intDiv(g, 1000) % 8000),
                      arrayMap(j -> cityHash64(sid, j), range(n)))) AS len_ms
  FROM gen_sessions
  WHERE day >= {d_from:Date} AND day < {d_to:Date}
)
ARRAY JOIN range(toUInt32(intDiv(len_ms, 90000))) AS k
SETTINGS max_block_size = 2000;

-- ---------- server events: create/update/delete:shapes about every 5 minutes ----------
INSERT INTO events
WITH cityHash64(sid, k, 'sh') AS y
SELECT
  multiIf(y % 10 < 6, 'create:shapes', y % 10 < 9, 'update:shapes', 'delete:shapes') AS scope,
  if(intDiv(y, 10) % 5 = 0, 'polygon', 'rectangle') AS obj_name,
  CAST(NULL AS Nullable(UInt64)) AS obj_id, CAST(NULL AS Nullable(String)) AS obj_val, 'server' AS source,
  start_ts + toIntervalMillisecond((k + 1) * 300000 + 1500 + y % 991) AS timestamp,
  toUInt16(1 + intDiv(y, 100) % 30) AS count,
  toUInt32(0) AS duration,
  project_id, task_id, job_id, user_id,
  concat('user_', toString(user_id)) AS user_name, concat('user_', toString(user_id), '@example.com') AS user_email,
  toUInt64(1) AS org_id, 'org1' AS org_slug,
  concat('{"shapes": [', arrayStringConcat(arrayMap(q -> concat('{"id": ', toString(y % 100000 + q), '}'), range(count)), ', '), ']}') AS payload,
  CAST(NULL AS Nullable(UInt64)) AS access_token_id,
  concat('10.0.', toString(user_id % 250), '.', toString(1 + user_id % 200)) AS remote_addr
FROM
(
  SELECT *,
    arraySum(arrayMap(g -> multiIf(g % 1000 < 3, 300000 + intDiv(g, 1000) % 300000,
                                   g % 1000 < 23, 60000 + intDiv(g, 1000) % 180000,
                                   1000 + intDiv(g, 1000) % 8000),
                      arrayMap(j -> cityHash64(sid, j), range(n)))) AS len_ms
  FROM gen_sessions
  WHERE day >= {d_from:Date} AND day < {d_to:Date}
)
ARRAY JOIN range(toUInt32(intDiv(len_ms, 300000))) AS k
SETTINGS max_block_size = 2000;
