/* ============================================================
   Backfill actual starters/subs history from DB game records

   Source:
     dbo.fact_lol_player_game

   Logic:
     - One row per date / league / team / position / player
     - If only one player appears in that team-position that day:
         starter_role = starter
     - If multiple players appear:
         highest games_played, then highest DK points = starter
         others = sub

   Stored in:
     dbo.lol_manual_starters_history

   source_type:
     actual_games
   ============================================================ */

WITH player_day AS
(
    SELECT
        CAST(game_date AS DATE) AS slate_date,
        CAST('actual_games' AS VARCHAR(100)) AS slate_name,

        league,
        team_name AS teamname,

        CASE
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('top') THEN 'top'
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('jng', 'jungle') THEN 'jng'
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('mid') THEN 'mid'
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('bot', 'adc') THEN 'bot'
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('sup', 'support') THEN 'sup'
            ELSE LOWER(LTRIM(RTRIM(position)))
        END AS position,

        player_name AS playername,

        COUNT(DISTINCT game_id) AS games_played,
        SUM(CAST(ISNULL(dk_points, 0) AS FLOAT)) AS total_dk_points,
        AVG(CAST(ISNULL(dk_points, 0) AS FLOAT)) AS avg_dk_points,
        MIN(CAST(game_date AS DATE)) AS actual_game_date,
        STRING_AGG(CAST(game_id AS VARCHAR(50)), ',') AS actual_series_ids
    FROM dbo.fact_lol_player_game
    WHERE league IN ('LPL', 'LCK')
      AND season = 2026
      AND team_name IS NOT NULL
      AND player_name IS NOT NULL
      AND position IS NOT NULL
      AND CAST(game_date AS DATE) IS NOT NULL
    GROUP BY
        CAST(game_date AS DATE),
        league,
        team_name,
        CASE
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('top') THEN 'top'
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('jng', 'jungle') THEN 'jng'
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('mid') THEN 'mid'
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('bot', 'adc') THEN 'bot'
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('sup', 'support') THEN 'sup'
            ELSE LOWER(LTRIM(RTRIM(position)))
        END,
        player_name
),

ranked AS
(
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY slate_date, league, teamname, position
            ORDER BY games_played DESC, total_dk_points DESC, playername
        ) AS lane_player_rank
    FROM player_day
),

final_rows AS
(
    SELECT
        slate_date,
        slate_name,
        teamname,
        position,
        playername,
        CAST(1 AS BIT) AS is_starter,
        CAST(NULL AS VARCHAR(300)) AS source_file,
        CAST('actual_games' AS VARCHAR(50)) AS source_type,
        CASE
            WHEN lane_player_rank = 1 THEN 'starter'
            ELSE 'sub'
        END AS starter_role,
        games_played,
        total_dk_points,
        avg_dk_points,
        actual_game_date,
        league AS actual_league,
        actual_series_ids
    FROM ranked
)

MERGE dbo.lol_manual_starters_history AS tgt
USING final_rows AS src
    ON tgt.slate_date = src.slate_date
    AND tgt.slate_name = src.slate_name
    AND LOWER(LTRIM(RTRIM(tgt.teamname))) = LOWER(LTRIM(RTRIM(src.teamname)))
    AND LOWER(LTRIM(RTRIM(tgt.position))) = LOWER(LTRIM(RTRIM(src.position)))
    AND LOWER(LTRIM(RTRIM(tgt.playername))) = LOWER(LTRIM(RTRIM(src.playername)))
WHEN MATCHED THEN
    UPDATE SET
        tgt.is_starter = src.is_starter,
        tgt.source_file = src.source_file,
        tgt.source_type = src.source_type,
        tgt.starter_role = src.starter_role,
        tgt.games_played = src.games_played,
        tgt.total_dk_points = src.total_dk_points,
        tgt.avg_dk_points = src.avg_dk_points,
        tgt.actual_game_date = src.actual_game_date,
        tgt.actual_league = src.actual_league,
        tgt.actual_series_ids = src.actual_series_ids,
        tgt.updated_at = SYSUTCDATETIME()
WHEN NOT MATCHED THEN
    INSERT
    (
        slate_date,
        slate_name,
        teamname,
        position,
        playername,
        is_starter,
        source_file,
        source_type,
        starter_role,
        games_played,
        total_dk_points,
        avg_dk_points,
        actual_game_date,
        actual_league,
        actual_series_ids
    )
    VALUES
    (
        src.slate_date,
        src.slate_name,
        src.teamname,
        src.position,
        src.playername,
        src.is_starter,
        src.source_file,
        src.source_type,
        src.starter_role,
        src.games_played,
        src.total_dk_points,
        src.avg_dk_points,
        src.actual_game_date,
        src.actual_league,
        src.actual_series_ids
    );