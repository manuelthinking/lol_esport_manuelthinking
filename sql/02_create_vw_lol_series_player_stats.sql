/* ============================================================
   Source view required by Bayesian population script

   IMPORTANT:
   This is a TEMPLATE view.

   You need this view to output one row per:
     series_id + teamname + opponent_teamname + player + position

   Required columns:
     series_id
     series_date
     season
     league
     teamname
     opponent_teamname
     player_name
     position
     series_result
     won_series
     games_played
     kills
     deaths
     assists
     dk_points

   Adjust the FROM table/column names in the source CTE to match
   your real Oracle Elixir/raw table.
   ============================================================ */

IF OBJECT_ID('dbo.vw_lol_series_player_stats', 'V') IS NOT NULL
BEGIN
    DROP VIEW dbo.vw_lol_series_player_stats;
END;
GO

CREATE VIEW dbo.vw_lol_series_player_stats AS

/* ============================================================
   CHANGE THIS CTE TO MATCH YOUR RAW HISTORICAL TABLE
   ============================================================ */
WITH source_rows AS
(
    SELECT
        -- Required series identifiers
        CAST(series_id AS NVARCHAR(200)) AS series_id,
        CAST(series_date AS DATE) AS series_date,
        CAST(season AS INT) AS season,
        CAST(league AS NVARCHAR(50)) AS league,

        -- Team/opponent
        CAST(teamname AS NVARCHAR(100)) AS teamname,
        CAST(opponent_teamname AS NVARCHAR(100)) AS opponent_teamname,

        -- Player/position
        CAST(player_name AS NVARCHAR(150)) AS player_name,

        CASE
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('bot', 'adc') THEN 'BOT'
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('jungle', 'jng') THEN 'JNG'
            WHEN LOWER(LTRIM(RTRIM(position))) = 'top' THEN 'TOP'
            WHEN LOWER(LTRIM(RTRIM(position))) = 'mid' THEN 'MID'
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('support', 'sup') THEN 'SUP'
            ELSE UPPER(LTRIM(RTRIM(position)))
        END AS position,

        -- Result from this team's perspective
        CAST(series_result AS NVARCHAR(10)) AS series_result,
        CAST(won_series AS BIT) AS won_series,
        CAST(games_played AS INT) AS games_played,

        -- Player stats for the series
        CAST(kills AS FLOAT) AS kills,
        CAST(deaths AS FLOAT) AS deaths,
        CAST(assists AS FLOAT) AS assists,
        CAST(dk_points AS FLOAT) AS dk_points

    FROM dbo.YOUR_RAW_SERIES_PLAYER_TABLE_HERE
    WHERE league IN ('LPL', 'LCK')
)

SELECT
    series_id,
    series_date,
    season,
    league,
    teamname,
    opponent_teamname,
    player_name,
    position,
    series_result,
    won_series,
    games_played,
    kills,
    deaths,
    assists,
    dk_points
FROM source_rows
WHERE position IN ('TOP', 'JNG', 'MID', 'BOT', 'SUP')
  AND series_result IN ('2-0', '2-1', '1-2', '0-2');
GO