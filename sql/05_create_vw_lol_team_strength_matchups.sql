/* ============================================================
   LoL Team Strength Matchup View

   Purpose:
     Add team strength bucket and opponent strength bucket
     to each historical team-series result.

   Source:
     dbo.lol_team_series_results
     dbo.vw_lol_team_strength_bucket

   Grain:
     one row per team per historical series

   Example:
     strong_vs_weak
     weak_vs_strong
     neutral_vs_strong
   ============================================================ */

IF OBJECT_ID('dbo.vw_lol_team_strength_matchups', 'V') IS NOT NULL
BEGIN
    DROP VIEW dbo.vw_lol_team_strength_matchups;
END;
GO

CREATE VIEW dbo.vw_lol_team_strength_matchups AS

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

with_buckets AS
(
    SELECT
        b.*,

        ts.team_strength_bucket,
        ts.smoothed_series_win_rate AS team_smoothed_win_rate,
        ts.series_count AS team_series_count,
        ts.team_strength_sample_label,

        os.team_strength_bucket AS opponent_strength_bucket,
        os.smoothed_series_win_rate AS opponent_smoothed_win_rate,
        os.series_count AS opponent_series_count,
        os.team_strength_sample_label AS opponent_strength_sample_label
    FROM base b
    LEFT JOIN dbo.vw_lol_team_strength_bucket ts
        ON b.league = ts.league
        AND b.season = ts.season
        AND LOWER(LTRIM(RTRIM(b.teamname))) = LOWER(LTRIM(RTRIM(ts.teamname)))

    LEFT JOIN dbo.vw_lol_team_strength_bucket os
        ON b.league = os.league
        AND b.season = os.season
        AND LOWER(LTRIM(RTRIM(b.opponent_teamname))) = LOWER(LTRIM(RTRIM(os.teamname)))
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

    ISNULL(team_strength_bucket, 'unknown') AS team_strength_bucket,
    ISNULL(opponent_strength_bucket, 'unknown') AS opponent_strength_bucket,

    CONCAT(
        ISNULL(team_strength_bucket, 'unknown'),
        '_vs_',
        ISNULL(opponent_strength_bucket, 'unknown')
    ) AS strength_matchup_bucket,

    team_smoothed_win_rate,
    opponent_smoothed_win_rate,
    team_series_count,
    opponent_series_count,
    team_strength_sample_label,
    opponent_strength_sample_label,

    player_dk_fp_base,
    player_dk_fp_with_gnp,
    team_slot_dk_fp_base,
    team_slot_dk_fp_with_gnp,
    total_team_kills,
    total_team_deaths,
    avg_game_length_minutes,
    total_game_length_minutes
FROM with_buckets;
GO