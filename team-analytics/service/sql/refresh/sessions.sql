-- Sessions: a person's job-bound client events and job-bound working-time rows, ordered by time; a
-- pause longer than the session gap (five minutes, 300000 ms) starts a new session. Sessions are not
-- totals per hour: each is stored whole, in the hour it ends (see schema/020_session_intervals.sql).
-- A refresh writes every session that ends inside its window, with its full length:
--   * it reads back a day before the window, so a session that began before the window edge keeps
--     its real start (a session longer than a day is cut there), and
--   * it reads the session gap past the window end, so a session that goes on after the window
--     ends there in no hour of this window and is left to the window that holds its end.
-- Time between two events of a session is credited to the project of the later event (also across
-- a project switch); the session's first event credits nothing but still marks its project touched.
-- Rows without a user are dropped.
INSERT INTO $totals_db.session_intervals
    (hour, instance_wide, org_id, user_id, user_name, start_at, end_at, length_ms, project_ids, project_ms, version)
SELECT
    toStartOfHour(session_end) AS session_hour,
    set_instance,
    set_org,
    set_user,
    argMax(project_user_name, project_last),
    min(project_first),
    max(project_last) AS session_end,
    sum(project_credit),
    arrayMap(pair -> pair.1, arraySort(groupArray((event_project, project_credit)))),
    arrayMap(pair -> pair.2, arraySort(groupArray((event_project, project_credit)))),
    {version:UInt64}
FROM (
    SELECT
        set_instance, set_org, set_user, session_no, event_project,
        argMax(event_user_name, at) AS project_user_name,
        min(at) AS project_first,
        max(at) AS project_last,
        sum(credit_ms) AS project_credit
    FROM (
        SELECT
            set_instance, set_org, set_user, at, event_user_name, event_project,
            if(is_start, 0, gap_ms) AS credit_ms,
            sum(is_start) OVER (PARTITION BY set_instance, set_org, set_user ORDER BY at ASC, position ASC
                                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS session_no
        FROM (
            SELECT
                set_instance, set_org, set_user, at, event_user_name, event_project,
                row_number() OVER w AS position,
                toUnixTimestamp64Milli(at) - toUnixTimestamp64Milli(lagInFrame(at) OVER w) AS gap_ms,
                position = 1 OR gap_ms > 300000 AS is_start
            FROM (
                SELECT
                    timestamp AS at,
                    instance_flag AS set_instance,
                    if(instance_flag = 1, 0, ifNull(org_id, 0)) AS set_org,
                    assumeNotNull(user_id) AS set_user,
                    ifNull(user_name, '') AS event_user_name,
                    ifNull(project_id, 0) AS event_project
                FROM $events_db.events
                ARRAY JOIN [0, 1] AS instance_flag
                WHERE timestamp >= {window_from:DateTime64(3, 'Etc/UTC')} - toIntervalDay(1)
                    AND timestamp <= {window_to:DateTime64(3, 'Etc/UTC')} + toIntervalMillisecond(300000)
                    AND job_id IS NOT NULL
                    AND user_id IS NOT NULL
                    AND (source = 'client' OR scope = 'send:working_time')
            )
            WINDOW w AS (PARTITION BY set_instance, set_org, set_user ORDER BY at ASC
                         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        )
    )
    GROUP BY set_instance, set_org, set_user, session_no, event_project
)
GROUP BY set_instance, set_org, set_user, session_no
HAVING session_end >= {window_from:DateTime64(3, 'Etc/UTC')} AND session_end < {window_to:DateTime64(3, 'Etc/UTC')}
