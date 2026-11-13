"""Generate the Q3 variants from q/q3_template.sql. They differ only in the shape expression."""
from pathlib import Path

HERE = Path(__file__).resolve().parent / "q"
TEMPLATE = (HERE / "q3_template.sql").read_text()

VARIANTS = {
    # no payload access at all: every operation counted as rectangle
    "q3a_no_payload": "1",
    # payload column is read but not parsed (isolates the cost of reading the column)
    "q3b_read_only": "length(payload) >= 0",
    # full JSON parser on every client row
    "q3c_json": "JSONExtractString(payload, 'shape_type') = 'rectangle'",
    # full JSON parser only on rows that are one of the four operations
    "q3d_json_ops_only": "op != 0 AND JSONExtractString(payload, 'shape_type') = 'rectangle'",
    # simpleJSON* family (returns '' on json.dumps-style text, see 05_json_probe.out)
    "q3e_simplejson": "simpleJSONExtractString(payload, 'shape_type') = 'rectangle'",
    # substring match, tied to the exact text layout
    "q3f_like_ops_only": "op != 0 AND payload LIKE '%\"shape_type\": \"rectangle\"%'",
}

for name, expr in VARIANTS.items():
    sql = TEMPLATE.replace("__VARIANT__", name).replace("__SHAPE__", expr)
    (HERE / f"{name}.sql").write_text(sql)
    print("wrote", name)
