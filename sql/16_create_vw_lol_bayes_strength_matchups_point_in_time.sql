/* ============================================================
   LoL Bayesian Strength Matchups - Point In Time

   Purpose:
     Combine point-in-time team strength matchup buckets with
     point-in-time lane strength matchup buckets.

   This is the main historical backtest source.

   Important:
     Every strength bucket is calculated using only data available
     before the target series date.

   Sources:
     dbo.vw_lol_team_strength_matchups_point_in_time
     dbo.vw_lol_lane_strength_matchups_point_in_time

   Grain:
     one row per team / historical target series

   Used for:
     Historical Bayesian backtesting without future-data leakage
   ============================================================ */

IF OBJECT_ID('dbo.vw_lol_bayes_strength_matchups_point_in_time', 'V') IS NOT NULL
BEGIN
    DROP VIEW dbo.vw_lol_bayes_strength_matchups_point_in_time;
END;
GO

CREATE VIEW dbo.vw_lol_bayes_strength_matchups_point_in_time AS

SELECT
    t.target_series_id,
    t.league,
    t.season,
    t.target_series_date,
    t.teamname,
    t.opponent_teamname,

    -- Actual result
    t.actual_series_result,
    t.actual_won_series,
    t.actual_game_wins,
    t.actual_game_losses,

    -- Team strength point-in-time layer
    t.team_strength_bucket,
    t.opponent_strength_bucket,
    t.strength_matchup_bucket,

    t.team_strength_sample_label,
    t.opponent_strength_sample_label,

    t.team_prior_series_count,
    t.opponent_prior_series_count,

    t.team_prior_series_wins,
    t.team_prior_series_losses,
    t.opponent_prior_series_wins,
    t.opponent_prior_series_losses,

    t.team_prior_game_wins,
    t.team_prior_game_losses,
    t.opponent_prior_game_wins,
    t.opponent_prior_game_losses,

    t.team_raw_prior_series_win_rate,
    t.opponent_raw_prior_series_win_rate,

    t.team_smoothed_prior_series_win_rate,
    t.opponent_smoothed_prior_series_win_rate,
    t.smoothed_strength_gap,

    t.league_prior_rows,
    t.league_prior_win_rate,
    t.prior_weight,

    -- Lane strength point-in-time layer
    l.team_top_strength,
    l.team_jng_strength,
    l.team_mid_strength,
    l.team_bot_strength,
    l.team_sup_strength,

    l.opponent_top_strength,
    l.opponent_jng_strength,
    l.opponent_mid_strength,
    l.opponent_bot_strength,
    l.opponent_sup_strength,

    l.top_lane_matchup_bucket,
    l.jng_lane_matchup_bucket,
    l.mid_lane_matchup_bucket,
    l.bot_lane_matchup_bucket,
    l.sup_lane_matchup_bucket,

    l.team_top_sample_label,
    l.team_jng_sample_label,
    l.team_mid_sample_label,
    l.team_bot_sample_label,
    l.team_sup_sample_label,

    l.opponent_top_sample_label,
    l.opponent_jng_sample_label,
    l.opponent_mid_sample_label,
    l.opponent_bot_sample_label,
    l.opponent_sup_sample_label,

    l.team_top_dk_index,
    l.team_jng_dk_index,
    l.team_mid_dk_index,
    l.team_bot_dk_index,
    l.team_sup_dk_index,

    l.opponent_top_dk_index,
    l.opponent_jng_dk_index,
    l.opponent_mid_dk_index,
    l.opponent_bot_dk_index,
    l.opponent_sup_dk_index,

    l.team_top_games,
    l.team_jng_games,
    l.team_mid_games,
    l.team_bot_games,
    l.team_sup_games,

    l.opponent_top_games,
    l.opponent_jng_games,
    l.opponent_mid_games,
    l.opponent_bot_games,
    l.opponent_sup_games,

    l.team_top_kill_index,
    l.team_jng_kill_index,
    l.team_mid_kill_index,
    l.team_bot_kill_index,
    l.team_sup_assist_index,

    l.opponent_top_kill_index,
    l.opponent_jng_kill_index,
    l.opponent_mid_kill_index,
    l.opponent_bot_kill_index,
    l.opponent_sup_assist_index

FROM dbo.vw_lol_team_strength_matchups_point_in_time t
LEFT JOIN dbo.vw_lol_lane_strength_matchups_point_in_time l
    ON t.target_series_id = l.target_series_id
    AND t.league = l.league
    AND t.season = l.season
    AND LOWER(LTRIM(RTRIM(t.teamname))) = LOWER(LTRIM(RTRIM(l.teamname)))
    AND LOWER(LTRIM(RTRIM(t.opponent_teamname))) = LOWER(LTRIM(RTRIM(l.opponent_teamname)));
GO