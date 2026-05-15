/* ============================================================
   LoL Bayesian Strength Matchup View

   Purpose:
     Combine team strength matchup buckets with lane strength
     matchup buckets.

   Sources:
     dbo.vw_lol_team_strength_matchups
     dbo.vw_lol_lane_strength_matchups

   Grain:
     one row per team per historical series

   Used by:
     Streamlit Bayesian Matchup Read
   ============================================================ */

IF OBJECT_ID('dbo.vw_lol_bayes_strength_matchups', 'V') IS NOT NULL
BEGIN
    DROP VIEW dbo.vw_lol_bayes_strength_matchups;
END;
GO

CREATE VIEW dbo.vw_lol_bayes_strength_matchups AS

SELECT
    t.series_id,
    t.league,
    t.season,
    t.series_date,
    t.teamname,
    t.opponent_teamname,
    t.series_result,
    t.won_series,
    t.games_played,
    t.wins,
    t.losses,

    -- Team strength layer
    t.team_strength_bucket,
    t.opponent_strength_bucket,
    t.strength_matchup_bucket,
    t.team_smoothed_win_rate,
    t.opponent_smoothed_win_rate,
    t.team_series_count,
    t.opponent_series_count,
    t.team_strength_sample_label,
    t.opponent_strength_sample_label,

    -- Lane strength layer
    l.team_top_strength,
    l.team_jng_strength,
    l.team_mid_strength,
    l.team_bot_strength,
    l.team_sup_strength,

    l.opp_top_strength,
    l.opp_jng_strength,
    l.opp_mid_strength,
    l.opp_bot_strength,
    l.opp_sup_strength,

    l.top_lane_matchup_bucket,
    l.jng_lane_matchup_bucket,
    l.mid_lane_matchup_bucket,
    l.bot_lane_matchup_bucket,
    l.sup_lane_matchup_bucket,

    l.team_top_dk_index,
    l.team_jng_dk_index,
    l.team_mid_dk_index,
    l.team_bot_dk_index,
    l.team_sup_dk_index,

    l.opp_top_dk_index,
    l.opp_jng_dk_index,
    l.opp_mid_dk_index,
    l.opp_bot_dk_index,
    l.opp_sup_dk_index,

    -- DFS context
    t.player_dk_fp_base,
    t.player_dk_fp_with_gnp,
    t.team_slot_dk_fp_base,
    t.team_slot_dk_fp_with_gnp,
    t.total_team_kills,
    t.total_team_deaths,
    t.avg_game_length_minutes,
    t.total_game_length_minutes
FROM dbo.vw_lol_team_strength_matchups t
LEFT JOIN dbo.vw_lol_lane_strength_matchups l
    ON t.series_id = l.series_id
    AND t.league = l.league
    AND t.season = l.season
    AND LOWER(LTRIM(RTRIM(t.teamname))) = LOWER(LTRIM(RTRIM(l.teamname)))
    AND LOWER(LTRIM(RTRIM(t.opponent_teamname))) = LOWER(LTRIM(RTRIM(l.opponent_teamname)));
GO  