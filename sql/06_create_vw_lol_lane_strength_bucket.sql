/* ============================================================
   LoL Lane Strength Bucket View

   Purpose:
     Label each team's lane/position as strong / neutral / weak.

   Source:
     dbo.fact_lol_player_game

   Grain:
     league + season + teamname + position

   Logic:
     lane_dk_index = team lane avg DK / league-position avg DK

   Buckets:
     strong  = lane_dk_index >= 1.10
     weak    = lane_dk_index <= 0.90
     neutral = everything between

   Notes:
     - Uses DK points because it best matches DFS usefulness.
     - Uses 2026 full-year data for each league.
     - Small samples are forced neutral.
   ============================================================ */

IF OBJECT_ID('dbo.vw_lol_lane_strength_bucket', 'V') IS NOT NULL
BEGIN
    DROP VIEW dbo.vw_lol_lane_strength_bucket;
END;
GO

CREATE VIEW dbo.vw_lol_lane_strength_bucket AS

WITH base AS
(
    SELECT
        league,
        season,
        team_name AS teamname,

        CASE
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('bot', 'adc') THEN 'BOT'
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('jng', 'jungle') THEN 'JNG'
            WHEN LOWER(LTRIM(RTRIM(position))) = 'mid' THEN 'MID'
            WHEN LOWER(LTRIM(RTRIM(position))) = 'top' THEN 'TOP'
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('sup', 'support') THEN 'SUP'
            ELSE UPPER(LTRIM(RTRIM(position)))
        END AS position,

        game_id,
        player_name,

        CAST(kills AS FLOAT) AS kills,
        CAST(deaths AS FLOAT) AS deaths,
        CAST(assists AS FLOAT) AS assists,
        CAST(dk_points AS FLOAT) AS dk_points,
        CAST(dpm AS FLOAT) AS dpm,
        CAST(damage_share AS FLOAT) AS damage_share,
        CAST(vision_score AS FLOAT) AS vision_score,
        CAST(gold_diff_10 AS FLOAT) AS gold_diff_10,
        CAST(xp_diff_10 AS FLOAT) AS xp_diff_10,
        CAST(cs_diff_10 AS FLOAT) AS cs_diff_10
    FROM dbo.fact_lol_player_game
    WHERE league IN ('LPL', 'LCK')
      AND season = 2026
      AND team_name IS NOT NULL
      AND player_name IS NOT NULL
      AND LOWER(LTRIM(RTRIM(position))) IN ('top', 'jng', 'jungle', 'mid', 'bot', 'adc', 'sup', 'support')
),

league_position_avg AS
(
    SELECT
        league,
        season,
        position,

        COUNT(*) AS league_position_games,
        AVG(dk_points) AS league_position_avg_dk,
        AVG(kills) AS league_position_avg_kills,
        AVG(deaths) AS league_position_avg_deaths,
        AVG(assists) AS league_position_avg_assists,
        AVG(dpm) AS league_position_avg_dpm,
        AVG(vision_score) AS league_position_avg_vision
    FROM base
    GROUP BY
        league,
        season,
        position
),

team_lane AS
(
    SELECT
        league,
        season,
        teamname,
        position,

        COUNT(*) AS lane_games,
        COUNT(DISTINCT player_name) AS lane_players,

        AVG(dk_points) AS lane_avg_dk,
        AVG(kills) AS lane_avg_kills,
        AVG(deaths) AS lane_avg_deaths,
        AVG(assists) AS lane_avg_assists,
        AVG(dpm) AS lane_avg_dpm,
        AVG(damage_share) AS lane_avg_damage_share,
        AVG(vision_score) AS lane_avg_vision_score,

        AVG(gold_diff_10) AS lane_avg_gold_diff_10,
        AVG(xp_diff_10) AS lane_avg_xp_diff_10,
        AVG(cs_diff_10) AS lane_avg_cs_diff_10
    FROM base
    GROUP BY
        league,
        season,
        teamname,
        position
),

joined AS
(
    SELECT
        tl.league,
        tl.season,
        tl.teamname,
        tl.position,

        tl.lane_games,
        tl.lane_players,

        tl.lane_avg_dk,
        lpa.league_position_avg_dk,

        tl.lane_avg_kills,
        lpa.league_position_avg_kills,

        tl.lane_avg_deaths,
        lpa.league_position_avg_deaths,

        tl.lane_avg_assists,
        lpa.league_position_avg_assists,

        tl.lane_avg_dpm,
        lpa.league_position_avg_dpm,

        tl.lane_avg_damage_share,
        tl.lane_avg_vision_score,
        lpa.league_position_avg_vision,

        tl.lane_avg_gold_diff_10,
        tl.lane_avg_xp_diff_10,
        tl.lane_avg_cs_diff_10,

        tl.lane_avg_dk / NULLIF(lpa.league_position_avg_dk, 0) AS lane_dk_index,
        tl.lane_avg_kills / NULLIF(lpa.league_position_avg_kills, 0) AS lane_kill_index,
        tl.lane_avg_assists / NULLIF(lpa.league_position_avg_assists, 0) AS lane_assist_index,
        tl.lane_avg_dpm / NULLIF(lpa.league_position_avg_dpm, 0) AS lane_dpm_index,
        tl.lane_avg_vision_score / NULLIF(lpa.league_position_avg_vision, 0) AS lane_vision_index
    FROM team_lane tl
    LEFT JOIN league_position_avg lpa
        ON tl.league = lpa.league
        AND tl.season = lpa.season
        AND tl.position = lpa.position
)

SELECT
    league,
    season,
    teamname,
    position,

    lane_games,
    lane_players,

    lane_avg_dk,
    league_position_avg_dk,
    lane_dk_index,

    lane_avg_kills,
    league_position_avg_kills,
    lane_kill_index,

    lane_avg_deaths,
    league_position_avg_deaths,

    lane_avg_assists,
    league_position_avg_assists,
    lane_assist_index,

    lane_avg_dpm,
    league_position_avg_dpm,
    lane_dpm_index,

    lane_avg_damage_share,
    lane_avg_vision_score,
    league_position_avg_vision,
    lane_vision_index,

    lane_avg_gold_diff_10,
    lane_avg_xp_diff_10,
    lane_avg_cs_diff_10,

    CASE
        WHEN lane_games < 5 THEN 'neutral'
        WHEN lane_dk_index >= 1.10 THEN 'strong'
        WHEN lane_dk_index <= 0.90 THEN 'weak'
        ELSE 'neutral'
    END AS lane_strength_bucket,

    CASE
        WHEN lane_games < 5 THEN 'low_sample'
        WHEN lane_games BETWEEN 5 AND 14 THEN 'medium_sample'
        ELSE 'solid_sample'
    END AS lane_strength_sample_label
FROM joined;
GO