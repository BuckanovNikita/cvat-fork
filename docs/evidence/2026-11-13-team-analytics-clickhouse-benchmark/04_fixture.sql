-- Hand-made fixture with known answers for queries 1-6 (expected values are in NOTES.md).
TRUNCATE TABLE events_fx;
INSERT INTO events_fx (scope, obj_name, obj_id, source, timestamp, duration, project_id, task_id, job_id, user_id, org_id, payload)
SELECT * FROM VALUES('scope String, obj_name Nullable(String), obj_id Nullable(UInt64), source String, timestamp DateTime64(3,\'Etc/UTC\'), duration UInt32, project_id Nullable(UInt64), task_id Nullable(UInt64), job_id Nullable(UInt64), user_id Nullable(UInt64), org_id Nullable(UInt64), payload Nullable(String)',
-- user 1, session 1
('zoom:image',    NULL, NULL, 'client', '2026-11-10 09:00:00.000',     0, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true}'),
('change:frame',  NULL, NULL, 'client', '2026-11-10 09:00:10.000',   500, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true}'),
('zoom:image',    NULL, NULL, 'client', '2026-11-10 09:00:20.000',     0, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true}'),
('draw:object',   NULL, NULL, 'client', '2026-11-10 09:00:30.000', 15000, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "shape_type": "rectangle", "input_method": "hotkey"}'),
('resize:object', NULL,    7, 'client', '2026-11-10 09:00:40.000',  2000, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "shape_type": "rectangle", "input_method": "mouse"}'),
('zoom:image',    NULL, NULL, 'client', '2026-11-10 09:00:45.000',     0, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true}'),
('drag:object',   NULL,    7, 'client', '2026-11-10 09:00:50.000',  3000, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "shape_type": "rectangle", "input_method": "mouse"}'),
('resize:object', NULL,    8, 'client', '2026-11-10 09:01:00.000',  1000, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "shape_type": "rectangle", "input_method": "mouse"}'),
('resize:object', NULL, NULL, 'client', '2026-11-10 09:01:10.000',  1000, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "shape_type": "rectangle", "input_method": "mouse"}'),
('drag:object',   NULL, NULL, 'client', '2026-11-10 09:01:15.000',  4000, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "shape_type": "rectangle", "input_method": "mouse"}'),
('zoom:image',    NULL, NULL, 'client', '2026-11-10 09:01:20.000',     0, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true}'),
('resize:object', NULL, NULL, 'client', '2026-11-10 09:01:25.000',  1000, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "shape_type": "rectangle", "input_method": "mouse"}'),
('debug:info', 'change:label', NULL, 'client', '2026-11-10 09:01:30.000', 0, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "shape_type": "rectangle", "input_method": "hotkey"}'),
('resize:object', NULL, NULL, 'client', '2026-11-10 09:01:40.000',  1000, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "shape_type": "polygon", "input_method": "mouse"}'),
('delete:object', NULL,    8, 'client', '2026-11-10 09:01:50.000',     0, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "shape_type": "rectangle", "input_method": "hotkey"}'),
('draw:object',   NULL, NULL, 'client', '2026-11-10 09:04:00.000',  5000, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "shape_type": "rectangle", "input_method": "hotkey"}'),
-- user 1, session 2 (gap 360 s)
('zoom:image',    NULL, NULL, 'client', '2026-11-10 09:10:00.000',     0, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true}'),
('debug:info', 'input:stats', NULL, 'client', '2026-11-10 09:10:05.000', 0, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "key.A": 3, "key.B": 5, "mouse.canvas": 12}'),
('click:element', 'Menu', NULL, 'client', '2026-11-10 09:10:10.000',   0, NULL, NULL, NULL, 1, 1, '{"client_id": "1", "is_active": true}'),
('draw:object',   NULL, NULL, 'client', '2026-11-10 09:10:30.000', 25000, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "shape_type": "rectangle", "input_method": "hotkey"}'),
('resize:object', NULL,    9, 'client', '2026-11-10 09:10:40.000',  2000, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "shape_type": "rectangle", "input_method": "mouse"}'),
('draw:object',   NULL, NULL, 'client', '2026-11-10 09:10:45.000',  8000, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "shape_type": "rectangle", "input_method": "hotkey"}'),
('zoom:image',    NULL, NULL, 'client', '2026-11-10 09:10:50.000',     0, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true}'),
('resize:object', NULL,    9, 'client', '2026-11-10 09:10:52.000',  3000, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "shape_type": "rectangle", "input_method": "mouse"}'),
('draw:object',   NULL, NULL, 'client', '2026-11-10 09:10:55.000',  6000, 10, 100, 1000, 1, 1, '{"client_id": "1", "is_active": true, "shape_type": "rectangle", "input_method": "hotkey"}'),
-- user 2: one session crossing midnight (and an hour boundary)
('draw:object',   NULL, NULL, 'client', '2026-11-10 23:59:50.000',  4000, 11, 110, 1100, 2, 1, '{"client_id": "2", "is_active": true, "shape_type": "rectangle", "input_method": "hotkey"}'),
('resize:object', NULL, NULL, 'client', '2026-11-11 00:00:10.500',  2500, 11, 110, 1100, 2, 1, '{"client_id": "2", "is_active": true, "shape_type": "rectangle", "input_method": "mouse"}'),
-- server rows
('send:working_time', 'working_time', NULL, 'server', '2026-11-10 09:01:30.100', 80000, 10, 100, 1000, 1, 1, '{"working_time": 80000}'),
('send:working_time', 'working_time', NULL, 'server', '2026-11-10 09:11:00.100', 30000, 10, 100, 1000, 1, 1, '{"working_time": 30000}'),
('send:working_time', 'working_time', NULL, 'server', '2026-11-11 00:00:20.100', 20000, 11, 110, 1100, 2, 1, '{"working_time": 20000}'));
