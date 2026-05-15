/* ============================================================
   LoL Lane Strength Matchup View

   Purpose:
     For each historical team-series row, attach the team's
     lane strength and opponent's lane strength.

   Sources:
     dbo.lol_team_series_results
     dbo.vw_lol_lane_strength_bucket

   Grain:
     one row per team per historical series

   Output:
     team strength by lane
     opponent strength by lane
     lane matchup labels:
       top_lane_matchup_bucket
       jng_lane_matchup_bucket
       mid_lane_matchup_bucket
       bot_lane_matchup_bucket
       sup_lane_matchup_bucket
   ============================================================ */

IF OBJECT_ID('dbo.vw_lol_lane_strength_matchups', 'V') IS NOT NULL
BEGIN
    DROP VIEW dbo.vw_lol_lane_strength_matchups;
END;
GO

CREATE VIEW dbo.vw_lol_lane_strength_matchups AS

WITH base AS
(
    SELECT
        r.series_id,
        r.league,
        r.[year] AS season,
        r.series_start_date AS series_date,
        r.teamname,
        r.opponent AS opponent_teamname,
        r.series_result,
        CAST(r.is_series_win AS INT) AS won_series,
        r.games_played,
        r.wins,
        r.losses,

        r.player_dk_fp_base,
        r.player_dk_fp_with_gnp,
        r.team_slot_dk_fp_base,
        r.team_slot_dk_fp_with_gnp,
        r.total_team_kills,
        r.total_team_deaths,
        r.avg_game_length_minutes,
        r.total_game_length_minutes
    FROM dbo.lol_team_series_results r
    WHERE r.league IN ('LPL', 'LCK')
      AND r.[year] = 2026
      AND r.series_result IN ('2-0', '2-1', '1-2', '0-2')
      AND r.teamname IS NOT NULL
      AND r.opponent IS NOT NULL
),

team_lane_pivot AS
(
    SELECT
        league,
        season,
        teamname,

        MAX(CASE WHEN position = 'TOP' THEN lane_strength_bucket END) AS team_top_strength,
        MAX(CASE WHEN position = 'JNG' THEN lane_strength_bucket END) AS team_jng_strength,
        MAX(CASE WHEN position = 'MID' THEN lane_strength_bucket END) AS team_mid_strength,
        MAX(CASE WHEN position = 'BOT' THEN lane_strength_bucket END) AS team_bot_strength,
        MAX(CASE WHEN position = 'SUP' THEN lane_strength_bucket END) AS team_sup_strength,

        MAX(CASE WHEN position = 'TOP' THEN lane_dk_index END) AS team_top_dk_index,
        MAX(CASE WHEN position = 'JNG' THEN lane_dk_index END) AS team_jng_dk_index,
        MAX(CASE WHEN position = 'MID' THEN lane_dk_index END) AS team_mid_dk_index,
        MAX(CASE WHEN position = 'BOT' THEN lane_dk_index END) AS team_bot_dk_index,
        MAX(CASE WHEN position = 'SUP' THEN lane_dk_index END) AS team_sup_dk_index,

        MAX(CASE WHEN position = 'TOP' THEN lane_games END) AS team_top_games,
        MAX(CASE WHEN position = 'JNG' THEN lane_games END) AS team_jng_games,
        MAX(CASE WHEN position = 'MID' THEN lane_games END) AS team_mid_games,
        MAX(CASE WHEN position = 'BOT' THEN lane_games END) AS team_bot_games,
        MAX(CASE WHEN position = 'SUP' THEN lane_games END) AS team_sup_games
    FROM dbo.vw_lol_lane_strength_bucket
    GROUP BY
        league,
        season,
        teamname
),

with_lanes AS
(
    SELECT
        b.*,

        tl.team_top_strength,
        tl.team_jng_strength,
        tl.team_mid_strength,
        tl.team_bot_strength,
        tl.team_sup_strength,

        ol.team_top_strength AS opp_top_strength,
        ol.team_jng_strength AS opp_jng_strength,
        ol.team_mid_strength AS opp_mid_strength,
        ol.team_bot_strength AS opp_bot_strength,
        ol.team_sup_strength AS opp_sup_strength,

        tl.team_top_dk_index,
        tl.team_jng_dk_index,
        tl.team_mid_dk_index,
        tl.team_bot_dk_index,
        tl.team_sup_dk_index,

        ol.team_top_dk_index AS opp_top_dk_index,
        ol.team_jng_dk_index AS opp_jng_dk_index,
        ol.team_mid_dk_index AS opp_mid_dk_index,
        ol.team_bot_dk_index AS opp_bot_dk_index,
        ol.team_sup_dk_index AS opp_sup_dk_index,

        tl.team_top_games,
        tl.team_jng_games,
        tl.team_mid_games,
        tl.team_bot_games,
        tl.team_sup_games,

        ol.team_top_games AS opp_top_games,
        ol.team_jng_games AS opp_jng_games,
        ol.team_mid_games AS opp_mid_games,
        ol.team_bot_games AS opp_bot_games,
        ol.team_sup_games AS opp_sup_games
    FROM base b
    LEFT JOIN team_lane_pivot tl
        ON b.league = tl.league
        AND b.season = tl.season
        AND LOWER(LTRIM(RTRIM(b.teamname))) = LOWER(LTRIM(RTRIM(tl.teamname)))

    LEFT JOIN team_lane_pivot ol
        ON b.league = ol.league
        AND b.season = ol.season
        AND LOWER(LTRIM(RTRIM(b.opponent_teamname))) = LOWER(LTRIM(RTRIM(ol.teamname)))
)

SELECT
    series_id,
    league,
    season,
    series_date,
    teamname,
    opponent_teamname,
    series_result,
    won_series,
    games_played,
    wins,
    losses,

    ISNULL(team_top_strength, 'unknown') AS team_top_strength,
    ISNULL(team_jng_strength, 'unknown') AS team_jng_strength,
    ISNULL(team_mid_strength, 'unknown') AS team_mid_strength,
    ISNULL(team_bot_strength, 'unknown') AS team_bot_strength,
    ISNULL(team_sup_strength, 'unknown') AS team_sup_strength,

    ISNULL(opp_top_strength, 'unknown') AS opp_top_strength,
    ISNULL(opp_jng_strength, 'unknown') AS opp_jng_strength,
    ISNULL(opp_mid_strength, 'unknown') AS opp_mid_strength,
    ISNULL(opp_bot_strength, 'unknown') AS opp_bot_strength,
    ISNULL(opp_sup_strength, 'unknown') AS opp_sup_strength,

    CONCAT(ISNULL(team_top_strength, 'unknown'), '_vs_', ISNULL(opp_top_strength, 'unknown')) AS top_lane_matchup_bucket,
    CONCAT(ISNULL(team_jng_strength, 'unknown'), '_vs_', ISNULL(opp_jng_strength, 'unknown')) AS jng_lane_matchup_bucket,
    CONCAT(ISNULL(team_mid_strength, 'unknown'), '_vs_', ISNULL(opp_mid_strength, 'unknown')) AS mid_lane_matchup_bucket,
    CONCAT(ISNULL(team_bot_strength, 'unknown'), '_vs_', ISNULL(opp_bot_strength, 'unknown')) AS bot_lane_matchup_bucket,
    CONCAT(ISNULL(team_sup_strength, 'unknown'), '_vs_', ISNULL(opp_sup_strength, 'unknown')) AS sup_lane_matchup_bucket,

    team_top_dk_index,
    team_jng_dk_index,
    team_mid_dk_index,
    team_bot_dk_index,
    team_sup_dk_index,

    opp_top_dk_index,
    opp_jng_dk_index,
    opp_mid_dk_index,
    opp_bot_dk_index,
    opp_sup_dk_index,

    team_top_games,
    team_jng_games,
    team_mid_games,
    team_bot_games,
    team_sup_games,

    opp_top_games,
    opp_jng_games,
    opp_mid_games,
    opp_bot_games,
    opp_sup_games,

    player_dk_fp_base,
    player_dk_fp_with_gnp,
    team_slot_dk_fp_base,
    team_slot_dk_fp_with_gnp,
    total_team_kills,
    total_team_deaths,
    avg_game_length_minutes,
    total_game_length_minutes
FROM with_lanes;
GO