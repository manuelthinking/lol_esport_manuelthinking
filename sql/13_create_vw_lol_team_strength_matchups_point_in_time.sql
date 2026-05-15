/* ============================================================
   LoL Team Strength Matchups - Point In Time

   Purpose:
     For each historical series, compare the team's point-in-time
     strength bucket against the opponent's point-in-time strength
     bucket.

   This avoids future-data leakage.

   Source:
     dbo.vw_lol_team_strength_bucket_point_in_time

   Grain:
     one row per team / historical target series

   Example output:
     strong_vs_weak
     neutral_vs_strong
     weak_vs_neutral
   ============================================================ */

IF OBJECT_ID('dbo.vw_lol_team_strength_matchups_point_in_time', 'V') IS NOT NULL
BEGIN
    DROP VIEW dbo.vw_lol_team_strength_matchups_point_in_time;
END;
GO

CREATE VIEW dbo.vw_lol_team_strength_matchups_point_in_time AS

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

        prior_series_count,
        prior_series_wins,
        prior_series_losses,
        prior_game_wins,
        prior_game_losses,

        raw_prior_series_win_rate,
        league_prior_rows,
        league_prior_win_rate,
        prior_weight,
        smoothed_prior_series_win_rate,

        team_strength_bucket_point_in_time,
        team_strength_sample_label_point_in_time
    FROM dbo.vw_lol_team_strength_bucket_point_in_time
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

        t.prior_series_count AS team_prior_series_count,
        t.prior_series_wins AS team_prior_series_wins,
        t.prior_series_losses AS team_prior_series_losses,
        t.prior_game_wins AS team_prior_game_wins,
        t.prior_game_losses AS team_prior_game_losses,

        t.raw_prior_series_win_rate AS team_raw_prior_series_win_rate,
        t.smoothed_prior_series_win_rate AS team_smoothed_prior_series_win_rate,
        t.team_strength_bucket_point_in_time AS team_strength_bucket,
        t.team_strength_sample_label_point_in_time AS team_strength_sample_label,

        o.prior_series_count AS opponent_prior_series_count,
        o.prior_series_wins AS opponent_prior_series_wins,
        o.prior_series_losses AS opponent_prior_series_losses,
        o.prior_game_wins AS opponent_prior_game_wins,
        o.prior_game_losses AS opponent_prior_game_losses,

        o.raw_prior_series_win_rate AS opponent_raw_prior_series_win_rate,
        o.smoothed_prior_series_win_rate AS opponent_smoothed_prior_series_win_rate,
        o.team_strength_bucket_point_in_time AS opponent_strength_bucket,
        o.team_strength_sample_label_point_in_time AS opponent_strength_sample_label,

        t.league_prior_rows,
        t.league_prior_win_rate,
        t.prior_weight
    FROM base t
    LEFT JOIN base o
        ON t.target_series_id = o.target_series_id
        AND t.league = o.league
        AND t.season = o.season
        AND LOWER(LTRIM(RTRIM(t.opponent_teamname))) = LOWER(LTRIM(RTRIM(o.teamname)))
        AND LOWER(LTRIM(RTRIM(t.teamname))) = LOWER(LTRIM(RTRIM(o.opponent_teamname)))
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

    ISNULL(team_strength_bucket, 'unknown') AS team_strength_bucket,
    ISNULL(opponent_strength_bucket, 'unknown') AS opponent_strength_bucket,

    CONCAT(
        ISNULL(team_strength_bucket, 'unknown'),
        '_vs_',
        ISNULL(opponent_strength_bucket, 'unknown')
    ) AS strength_matchup_bucket,

    team_strength_sample_label,
    opponent_strength_sample_label,

    team_prior_series_count,
    opponent_prior_series_count,

    team_prior_series_wins,
    team_prior_series_losses,
    opponent_prior_series_wins,
    opponent_prior_series_losses,

    team_prior_game_wins,
    team_prior_game_losses,
    opponent_prior_game_wins,
    opponent_prior_game_losses,

    team_raw_prior_series_win_rate,
    opponent_raw_prior_series_win_rate,

    team_smoothed_prior_series_win_rate,
    opponent_smoothed_prior_series_win_rate,

    (
        ISNULL(team_smoothed_prior_series_win_rate, 0.50)
        - ISNULL(opponent_smoothed_prior_series_win_rate, 0.50)
    ) AS smoothed_strength_gap,

    league_prior_rows,
    league_prior_win_rate,
    prior_weight
FROM with_opponent;
GO