/* ============================================================
   LoL Team Strength Bucket - Point In Time

   Purpose:
     Calculate each team's strength as of BEFORE each historical
     series date.

   This avoids future-data leakage when backtesting.

   Example:
     For BLG vs TES on 2026-05-15:
       BLG strength uses only BLG series before 2026-05-15
       TES strength uses only TES series before 2026-05-15

   Source:
     dbo.lol_team_series_results

   Grain:
     one row per team / historical target series

   Output:
     team strength entering that series
   ============================================================ */

IF OBJECT_ID('dbo.vw_lol_team_strength_bucket_point_in_time', 'V') IS NOT NULL
BEGIN
    DROP VIEW dbo.vw_lol_team_strength_bucket_point_in_time;
END;
GO

CREATE VIEW dbo.vw_lol_team_strength_bucket_point_in_time AS

WITH target_series AS
(
    SELECT
        r.series_id AS target_series_id,
        r.league,
        r.[year] AS season,
        r.series_start_date AS target_series_date,
        r.teamname,
        r.opponent AS opponent_teamname,
        r.series_result AS actual_series_result,
        CAST(r.is_series_win AS INT) AS actual_won_series,
        r.wins AS actual_game_wins,
        r.losses AS actual_game_losses
    FROM dbo.lol_team_series_results r
    WHERE r.league IN ('LPL', 'LCK')
      AND r.[year] = 2026
      AND r.series_result IN ('2-0', '2-1', '1-2', '0-2')
      AND r.teamname IS NOT NULL
      AND r.opponent IS NOT NULL
      AND r.series_start_date IS NOT NULL
),

prior_series AS
(
    SELECT
        t.target_series_id,
        t.league,
        t.season,
        t.target_series_date,
        t.teamname,

        p.series_id AS prior_series_id,
        p.series_start_date AS prior_series_date,
        CAST(p.is_series_win AS FLOAT) AS prior_is_series_win,
        CAST(ISNULL(p.wins, 0) AS INT) AS prior_game_wins,
        CAST(ISNULL(p.losses, 0) AS INT) AS prior_game_losses
    FROM target_series t
    LEFT JOIN dbo.lol_team_series_results p
        ON t.league = p.league
        AND t.season = p.[year]
        AND LOWER(LTRIM(RTRIM(t.teamname))) = LOWER(LTRIM(RTRIM(p.teamname)))
        AND p.series_result IN ('2-0', '2-1', '1-2', '0-2')
        AND p.series_start_date < t.target_series_date
),

league_prior_before_series AS
(
    SELECT
        t.target_series_id,
        t.league,
        t.season,
        t.target_series_date,

        COUNT(p.series_id) AS league_prior_rows,
        AVG(CAST(p.is_series_win AS FLOAT)) AS league_prior_win_rate
    FROM target_series t
    LEFT JOIN dbo.lol_team_series_results p
        ON t.league = p.league
        AND t.season = p.[year]
        AND p.series_result IN ('2-0', '2-1', '1-2', '0-2')
        AND p.series_start_date < t.target_series_date
    GROUP BY
        t.target_series_id,
        t.league,
        t.season,
        t.target_series_date
),

team_record_before_series AS
(
    SELECT
        target_series_id,
        league,
        season,
        target_series_date,
        teamname,

        COUNT(prior_series_id) AS prior_series_count,
        SUM(CASE WHEN prior_is_series_win = 1 THEN 1 ELSE 0 END) AS prior_series_wins,
        SUM(CASE WHEN prior_is_series_win = 0 THEN 1 ELSE 0 END) AS prior_series_losses,

        SUM(prior_game_wins) AS prior_game_wins,
        SUM(prior_game_losses) AS prior_game_losses,

        MIN(prior_series_date) AS first_prior_series_date,
        MAX(prior_series_date) AS last_prior_series_date,

        AVG(prior_is_series_win) AS raw_prior_series_win_rate
    FROM prior_series
    GROUP BY
        target_series_id,
        league,
        season,
        target_series_date,
        teamname
),

smoothed AS
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

        tr.prior_series_count,
        tr.prior_series_wins,
        tr.prior_series_losses,
        tr.prior_game_wins,
        tr.prior_game_losses,
        tr.first_prior_series_date,
        tr.last_prior_series_date,
        tr.raw_prior_series_win_rate,

        lp.league_prior_rows,
        ISNULL(lp.league_prior_win_rate, 0.50) AS league_prior_win_rate,

        CAST(12 AS FLOAT) AS prior_weight,

        (
            ISNULL(tr.prior_series_wins, 0)
            + (ISNULL(lp.league_prior_win_rate, 0.50) * 12.0)
        )
        /
        NULLIF(ISNULL(tr.prior_series_count, 0) + 12.0, 0) AS smoothed_prior_series_win_rate
    FROM target_series t
    LEFT JOIN team_record_before_series tr
        ON t.target_series_id = tr.target_series_id
        AND LOWER(LTRIM(RTRIM(t.teamname))) = LOWER(LTRIM(RTRIM(tr.teamname)))
    LEFT JOIN league_prior_before_series lp
        ON t.target_series_id = lp.target_series_id
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

    ISNULL(prior_series_count, 0) AS prior_series_count,
    ISNULL(prior_series_wins, 0) AS prior_series_wins,
    ISNULL(prior_series_losses, 0) AS prior_series_losses,
    ISNULL(prior_game_wins, 0) AS prior_game_wins,
    ISNULL(prior_game_losses, 0) AS prior_game_losses,

    first_prior_series_date,
    last_prior_series_date,

    raw_prior_series_win_rate,
    league_prior_rows,
    league_prior_win_rate,
    prior_weight,
    smoothed_prior_series_win_rate,

    CASE
        WHEN ISNULL(prior_series_count, 0) < 5 THEN 'neutral'
        WHEN smoothed_prior_series_win_rate >= 0.55 THEN 'strong'
        WHEN smoothed_prior_series_win_rate <= 0.45 THEN 'weak'
        ELSE 'neutral'
    END AS team_strength_bucket_point_in_time,

    CASE
        WHEN ISNULL(prior_series_count, 0) < 5 THEN 'low_sample'
        WHEN ISNULL(prior_series_count, 0) BETWEEN 5 AND 9 THEN 'medium_sample'
        ELSE 'solid_sample'
    END AS team_strength_sample_label_point_in_time
FROM smoothed;
GO