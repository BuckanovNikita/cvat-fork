-- How do the JSON functions behave on json.dumps-style text (": " and ", " separators)?
SELECT
  simpleJSONExtractString('{"a": 1, "shape_type": "rectangle"}', 'shape_type') AS simple_spaced,
  simpleJSONExtractString('{"a":1,"shape_type":"rectangle"}', 'shape_type')    AS simple_compact,
  JSONExtractString('{"a": 1, "shape_type": "rectangle"}', 'shape_type')       AS json_spaced
FORMAT Vertical;

SELECT
  JSONExtractKeysAndValues('{"client_id": "12", "is_active": true, "key.A": 3, "key.B": 5, "mouse.canvas": 12}', 'Int64') AS kv_int64,
  JSONExtractKeysAndValuesRaw('{"client_id": "12", "key.A": 3}') AS kv_raw,
  extractAllGroupsVertical('{"client_id": "12", "is_active": true, "key.A": 3, "key.B": 5, "mouse.canvas": 12}', '"key\\.([^"]+)": ?(\\d+)') AS rx
FORMAT Vertical;

-- On the generated data: share of shape rows where each extractor returns 'rectangle' (expect ~80%).
SELECT
  count() AS shape_rows,
  countIf(JSONExtractString(payload, 'shape_type') = 'rectangle') AS json_rect,
  countIf(simpleJSONExtractString(payload, 'shape_type') = 'rectangle') AS simple_rect,
  countIf(payload LIKE '%"shape_type": "rectangle"%') AS like_rect
FROM events
WHERE scope = 'draw:object' AND timestamp >= '2026-11-13 00:00:00'
FORMAT Vertical;
