-- The number of event rows the benchmark generator (03_gen_events.sql) writes for the sessions in
-- `gen_sessions`: one client row per session event, one working-time row per 90 s and one shapes row per
-- 300 s of session length. Used to find the `base_n` that reproduces the design measurements' row count
-- without generating the events.
SELECT sum(n) + sum(intDiv(len_ms, 90000)) + sum(intDiv(len_ms, 300000))
FROM
(
    SELECT n,
        arraySum(arrayMap(g -> multiIf(g % 1000 < 3, 300000 + intDiv(g, 1000) % 300000,
                                       g % 1000 < 23, 60000 + intDiv(g, 1000) % 180000,
                                       1000 + intDiv(g, 1000) % 8000),
                          arrayMap(j -> cityHash64(sid, j), range(n)))) AS len_ms
    FROM gen_sessions
)
