/* ============================================================
   LoL Lane Strength Matchups - Point In Time

   Purpose:
     For each historical series, compare the team's point-in-time
     lane strength against the opponent's point-in-time lane strength.

   This avoids future-data leakage.

   Source:
     dbo.vw_lol_lane_strength_bucket_point_in_time

   Grain:
     one row per team / historical target series

   Output:
     top_lane_matchup_bucket
     jng_lane_matchup_bucket
     mid_lane_matchup_bucket
     bot_lane_matchup_bucket
     sup_lane_matchup_bucket

   Example:
     MID strong_vs_weak
     BOT neutral_vs_strong
     SUP weak_vs_neutral
   ============================================================ */

IF OBJECT_ID('dbo.vw_lol_lane_strength_matchups_point_in_time', 'V') IS NOT NULL
BEGIN
    DROP VIEW dbo.vw_lol_lane_strength_matchups_point_in_time;
END;
GO

CREATE VIEW dbo.vw_lol_lane_strength_matchups_point_in_time AS

WITH base AS
(
    SELECT
        target_series_id,
        league,
        season,
        target_series_date,
        teamname,
        opponent_teamname,

        actual_series_result,
        actual_won_series,
        actual_game_wins,
        actual_game_losses,

        position,

        lane_games,
        lane_players_used,
        first_prior_game_date,
        last_prior_game_date,

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
        league_position_avg_damage_share,

        lane_avg_vision_score,
        league_position_avg_vision_score,
        lane_vision_index,

        lane_avg_gold_diff_10,
        lane_avg_xp_diff_10,
        lane_avg_cs_diff_10,

        league_position_games,

        lane_strength_bucket_point_in_time,
        lane_strength_sample_label_point_in_time
    FROM dbo.vw_lol_lane_strength_bucket_point_in_time
),

with_opponent AS
(
    SELECT
        t.target_series_id,
        t.league,
        t.season,
        t.target_series_date,
        t.teamname,
        t.opponent_teamname,

        t.actual_series_result,
        t.actual_won_series,
        t.actual_game_wins,
        t.actual_game_losses,

        t.position,

        t.lane_games AS team_lane_games,
        t.lane_players_used AS team_lane_players_used,
        t.first_prior_game_date AS team_first_prior_game_date,
        t.last_prior_game_date AS team_last_prior_game_date,

        t.lane_avg_dk AS team_lane_avg_dk,
        t.league_position_avg_dk,
        t.lane_dk_index AS team_lane_dk_index,

        t.lane_avg_kills AS team_lane_avg_kills,
        t.league_position_avg_kills,
        t.lane_kill_index AS team_lane_kill_index,

        t.lane_avg_deaths AS team_lane_avg_deaths,
        t.league_position_avg_deaths,

        t.lane_avg_assists AS team_lane_avg_assists,
        t.league_position_avg_assists,
        t.lane_assist_index AS team_lane_assist_index,

        t.lane_avg_dpm AS team_lane_avg_dpm,
        t.league_position_avg_dpm,
        t.lane_dpm_index AS team_lane_dpm_index,

        t.lane_avg_damage_share AS team_lane_avg_damage_share,
        t.league_position_avg_damage_share,

        t.lane_avg_vision_score AS team_lane_avg_vision_score,
        t.league_position_avg_vision_score,
        t.lane_vision_index AS team_lane_vision_index,

        t.lane_avg_gold_diff_10 AS team_lane_avg_gold_diff_10,
        t.lane_avg_xp_diff_10 AS team_lane_avg_xp_diff_10,
        t.lane_avg_cs_diff_10 AS team_lane_avg_cs_diff_10,

        t.league_position_games,

        t.lane_strength_bucket_point_in_time AS team_lane_strength_bucket,
        t.lane_strength_sample_label_point_in_time AS team_lane_strength_sample_label,

        o.lane_games AS opponent_lane_games,
        o.lane_players_used AS opponent_lane_players_used,
        o.first_prior_game_date AS opponent_first_prior_game_date,
        o.last_prior_game_date AS opponent_last_prior_game_date,

        o.lane_avg_dk AS opponent_lane_avg_dk,
        o.lane_dk_index AS opponent_lane_dk_index,

        o.lane_avg_kills AS opponent_lane_avg_kills,
        o.lane_kill_index AS opponent_lane_kill_index,

        o.lane_avg_deaths AS opponent_lane_avg_deaths,

        o.lane_avg_assists AS opponent_lane_avg_assists,
        o.lane_assist_index AS opponent_lane_assist_index,

        o.lane_avg_dpm AS opponent_lane_avg_dpm,
        o.lane_dpm_index AS opponent_lane_dpm_index,

        o.lane_avg_damage_share AS opponent_lane_avg_damage_share,

        o.lane_avg_vision_score AS opponent_lane_avg_vision_score,
        o.lane_vision_index AS opponent_lane_vision_index,

        o.lane_avg_gold_diff_10 AS opponent_lane_avg_gold_diff_10,
        o.lane_avg_xp_diff_10 AS opponent_lane_avg_xp_diff_10,
        o.lane_avg_cs_diff_10 AS opponent_lane_avg_cs_diff_10,

        o.lane_strength_bucket_point_in_time AS opponent_lane_strength_bucket,
        o.lane_strength_sample_label_point_in_time AS opponent_lane_strength_sample_label
    FROM base t
    LEFT JOIN base o
        ON t.target_series_id = o.target_series_id
        AND t.league = o.league
        AND t.season = o.season
        AND t.position = o.position
        AND LOWER(LTRIM(RTRIM(t.opponent_teamname))) = LOWER(LTRIM(RTRIM(o.teamname)))
        AND LOWER(LTRIM(RTRIM(t.teamname))) = LOWER(LTRIM(RTRIM(o.opponent_teamname)))
),

pivoted AS
(
    SELECT
        target_series_id,
        league,
        season,
        target_series_date,
        teamname,
        opponent_teamname,

        actual_series_result,
        actual_won_series,
        actual_game_wins,
        actual_game_losses,

        -- Team lane buckets
        MAX(CASE WHEN position = 'TOP' THEN team_lane_strength_bucket END) AS team_top_strength,
        MAX(CASE WHEN position = 'JNG' THEN team_lane_strength_bucket END) AS team_jng_strength,
        MAX(CASE WHEN position = 'MID' THEN team_lane_strength_bucket END) AS team_mid_strength,
        MAX(CASE WHEN position = 'BOT' THEN team_lane_strength_bucket END) AS team_bot_strength,
        MAX(CASE WHEN position = 'SUP' THEN team_lane_strength_bucket END) AS team_sup_strength,

        -- Opponent lane buckets
        MAX(CASE WHEN position = 'TOP' THEN opponent_lane_strength_bucket END) AS opponent_top_strength,
        MAX(CASE WHEN position = 'JNG' THEN opponent_lane_strength_bucket END) AS opponent_jng_strength,
        MAX(CASE WHEN position = 'MID' THEN opponent_lane_strength_bucket END) AS opponent_mid_strength,
        MAX(CASE WHEN position = 'BOT' THEN opponent_lane_strength_bucket END) AS opponent_bot_strength,
        MAX(CASE WHEN position = 'SUP' THEN opponent_lane_strength_bucket END) AS opponent_sup_strength,

        -- Team lane sample labels
        MAX(CASE WHEN position = 'TOP' THEN team_lane_strength_sample_label END) AS team_top_sample_label,
        MAX(CASE WHEN position = 'JNG' THEN team_lane_strength_sample_label END) AS team_jng_sample_label,
        MAX(CASE WHEN position = 'MID' THEN team_lane_strength_sample_label END) AS team_mid_sample_label,
        MAX(CASE WHEN position = 'BOT' THEN team_lane_strength_sample_label END) AS team_bot_sample_label,
        MAX(CASE WHEN position = 'SUP' THEN team_lane_strength_sample_label END) AS team_sup_sample_label,

        -- Opponent lane sample labels
        MAX(CASE WHEN position = 'TOP' THEN opponent_lane_strength_sample_label END) AS opponent_top_sample_label,
        MAX(CASE WHEN position = 'JNG' THEN opponent_lane_strength_sample_label END) AS opponent_jng_sample_label,
        MAX(CASE WHEN position = 'MID' THEN opponent_lane_strength_sample_label END) AS opponent_mid_sample_label,
        MAX(CASE WHEN position = 'BOT' THEN opponent_lane_strength_sample_label END) AS opponent_bot_sample_label,
        MAX(CASE WHEN position = 'SUP' THEN opponent_lane_strength_sample_label END) AS opponent_sup_sample_label,

        -- DK indexes
        MAX(CASE WHEN position = 'TOP' THEN team_lane_dk_index END) AS team_top_dk_index,
        MAX(CASE WHEN position = 'JNG' THEN team_lane_dk_index END) AS team_jng_dk_index,
        MAX(CASE WHEN position = 'MID' THEN team_lane_dk_index END) AS team_mid_dk_index,
        MAX(CASE WHEN position = 'BOT' THEN team_lane_dk_index END) AS team_bot_dk_index,
        MAX(CASE WHEN position = 'SUP' THEN team_lane_dk_index END) AS team_sup_dk_index,

        MAX(CASE WHEN position = 'TOP' THEN opponent_lane_dk_index END) AS opponent_top_dk_index,
        MAX(CASE WHEN position = 'JNG' THEN opponent_lane_dk_index END) AS opponent_jng_dk_index,
        MAX(CASE WHEN position = 'MID' THEN opponent_lane_dk_index END) AS opponent_mid_dk_index,
        MAX(CASE WHEN position = 'BOT' THEN opponent_lane_dk_index END) AS opponent_bot_dk_index,
        MAX(CASE WHEN position = 'SUP' THEN opponent_lane_dk_index END) AS opponent_sup_dk_index,

        -- Lane games
        MAX(CASE WHEN position = 'TOP' THEN team_lane_games END) AS team_top_games,
        MAX(CASE WHEN position = 'JNG' THEN team_lane_games END) AS team_jng_games,
        MAX(CASE WHEN position = 'MID' THEN team_lane_games END) AS team_mid_games,
        MAX(CASE WHEN position = 'BOT' THEN team_lane_games END) AS team_bot_games,
        MAX(CASE WHEN position = 'SUP' THEN team_lane_games END) AS team_sup_games,

        MAX(CASE WHEN position = 'TOP' THEN opponent_lane_games END) AS opponent_top_games,
        MAX(CASE WHEN position = 'JNG' THEN opponent_lane_games END) AS opponent_jng_games,
        MAX(CASE WHEN position = 'MID' THEN opponent_lane_games END) AS opponent_mid_games,
        MAX(CASE WHEN position = 'BOT' THEN opponent_lane_games END) AS opponent_bot_games,
        MAX(CASE WHEN position = 'SUP' THEN opponent_lane_games END) AS opponent_sup_games,

        -- Optional detailed indexes
        MAX(CASE WHEN position = 'TOP' THEN team_lane_kill_index END) AS team_top_kill_index,
        MAX(CASE WHEN position = 'JNG' THEN team_lane_kill_index END) AS team_jng_kill_index,
        MAX(CASE WHEN position = 'MID' THEN team_lane_kill_index END) AS team_mid_kill_index,
        MAX(CASE WHEN position = 'BOT' THEN team_lane_kill_index END) AS team_bot_kill_index,
        MAX(CASE WHEN position = 'SUP' THEN team_lane_assist_index END) AS team_sup_assist_index,

        MAX(CASE WHEN position = 'TOP' THEN opponent_lane_kill_index END) AS opponent_top_kill_index,
        MAX(CASE WHEN position = 'JNG' THEN opponent_lane_kill_index END) AS opponent_jng_kill_index,
        MAX(CASE WHEN position = 'MID' THEN opponent_lane_kill_index END) AS opponent_mid_kill_index,
        MAX(CASE WHEN position = 'BOT' THEN opponent_lane_kill_index END) AS opponent_bot_kill_index,
        MAX(CASE WHEN position = 'SUP' THEN opponent_lane_assist_index END) AS opponent_sup_assist_index
    FROM with_opponent
    GROUP BY
        target_series_id,
        league,
        season,
        target_series_date,
        teamname,
        opponent_teamname,
        actual_series_result,
        actual_won_series,
        actual_game_wins,
        actual_game_losses
)

SELECT
    target_series_id,
    league,
    season,
    target_series_date,
    teamname,
    opponent_teamname,

    actual_series_result,
    actual_won_series,
    actual_game_wins,
    actual_game_losses,

    ISNULL(team_top_strength, 'unknown') AS team_top_strength,
    ISNULL(team_jng_strength, 'unknown') AS team_jng_strength,
    ISNULL(team_mid_strength, 'unknown') AS team_mid_strength,
    ISNULL(team_bot_strength, 'unknown') AS team_bot_strength,
    ISNULL(team_sup_strength, 'unknown') AS team_sup_strength,

    ISNULL(opponent_top_strength, 'unknown') AS opponent_top_strength,
    ISNULL(opponent_jng_strength, 'unknown') AS opponent_jng_strength,
    ISNULL(opponent_mid_strength, 'unknown') AS opponent_mid_strength,
    ISNULL(opponent_bot_strength, 'unknown') AS opponent_bot_strength,
    ISNULL(opponent_sup_strength, 'unknown') AS opponent_sup_strength,

    CONCAT(ISNULL(team_top_strength, 'unknown'), '_vs_', ISNULL(opponent_top_strength, 'unknown')) AS top_lane_matchup_bucket,
    CONCAT(ISNULL(team_jng_strength, 'unknown'), '_vs_', ISNULL(opponent_jng_strength, 'unknown')) AS jng_lane_matchup_bucket,
    CONCAT(ISNULL(team_mid_strength, 'unknown'), '_vs_', ISNULL(opponent_mid_strength, 'unknown')) AS mid_lane_matchup_bucket,
    CONCAT(ISNULL(team_bot_strength, 'unknown'), '_vs_', ISNULL(opponent_bot_strength, 'unknown')) AS bot_lane_matchup_bucket,
    CONCAT(ISNULL(team_sup_strength, 'unknown'), '_vs_', ISNULL(opponent_sup_strength, 'unknown')) AS sup_lane_matchup_bucket,

    team_top_sample_label,
    team_jng_sample_label,
    team_mid_sample_label,
    team_bot_sample_label,
    team_sup_sample_label,

    opponent_top_sample_label,
    opponent_jng_sample_label,
    opponent_mid_sample_label,
    opponent_bot_sample_label,
    opponent_sup_sample_label,

    team_top_dk_index,
    team_jng_dk_index,
    team_mid_dk_index,
    team_bot_dk_index,
    team_sup_dk_index,

    opponent_top_dk_index,
    opponent_jng_dk_index,
    opponent_mid_dk_index,
    opponent_bot_dk_index,
    opponent_sup_dk_index,

    team_top_games,
    team_jng_games,
    team_mid_games,
    team_bot_games,
    team_sup_games,

    opponent_top_games,
    opponent_jng_games,
    opponent_mid_games,
    opponent_bot_games,
    opponent_sup_games,

    team_top_kill_index,
    team_jng_kill_index,
    team_mid_kill_index,
    team_bot_kill_index,
    team_sup_assist_index,

    opponent_top_kill_index,
    opponent_jng_kill_index,
    opponent_mid_kill_index,
    opponent_bot_kill_index,
    opponent_sup_assist_index
FROM pivoted;
GO