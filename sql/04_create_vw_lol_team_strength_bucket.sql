/* ============================================================
   LoL Team Strength Bucket View

   Purpose:
     Label historical teams as strong / neutral / weak.

   Source:
     dbo.lol_team_series_results

   Logic:
     - Uses series wins and losses.
     - Smooths team win rate toward league/split average.
     - Prevents tiny samples from being labeled too aggressively.

   Buckets:
     strong  = smoothed win rate >= 55%
     weak    = smoothed win rate <= 45%
     neutral = everything between

   Output grain:
     league + season + split + teamname
   ============================================================ */

IF OBJECT_ID('dbo.vw_lol_team_strength_bucket', 'V') IS NOT NULL
BEGIN
    DROP VIEW dbo.vw_lol_team_strength_bucket;
END;
GO

CREATE VIEW dbo.vw_lol_team_strength_bucket AS

WITH base AS
(
    SELECT
        league,
        [year] AS season,
        split,
        teamname,
        series_id,
        CAST(is_series_win AS FLOAT) AS is_series_win,
        CAST(wins AS INT) AS wins,
        CAST(losses AS INT) AS losses,
        series_result,
        games_played,
        series_start_date
    FROM dbo.lol_team_series_results
    WHERE league IN ('LPL', 'LCK')
      AND series_result IN ('2-0', '2-1', '1-2', '0-2')
      AND teamname IS NOT NULL
),

league_priors AS
(
    SELECT
        league,
        season,
        split,
        COUNT(*) AS league_team_series_rows,
        AVG(is_series_win) AS league_win_rate
    FROM base
    GROUP BY
        league,
        season,
        split
),

team_record AS
(
    SELECT
        league,
        season,
        split,
        teamname,

        COUNT(*) AS series_count,
        SUM(CASE WHEN is_series_win = 1 THEN 1 ELSE 0 END) AS series_wins,
        SUM(CASE WHEN is_series_win = 0 THEN 1 ELSE 0 END) AS series_losses,

        SUM(wins) AS game_wins,
        SUM(losses) AS game_losses,

        MIN(series_start_date) AS first_series_date,
        MAX(series_start_date) AS last_series_date,

        AVG(is_series_win) AS raw_series_win_rate
    FROM base
    GROUP BY
        league,
        season,
        split,
        teamname
),

smoothed AS
(
    SELECT
        tr.league,
        tr.season,
        tr.split,
        tr.teamname,

        tr.series_count,
        tr.series_wins,
        tr.series_losses,
        tr.game_wins,
        tr.game_losses,
        tr.first_series_date,
        tr.last_series_date,

        tr.raw_series_win_rate,

        lp.league_team_series_rows,
        lp.league_win_rate,

        /* Prior weight controls how hard small samples are pulled toward league average. */
        CAST(12 AS FLOAT) AS prior_weight,

        (
            tr.series_wins
            + (lp.league_win_rate * 12.0)
        )
        /
        NULLIF(
            tr.series_count + 12.0,
            0
        ) AS smoothed_series_win_rate
    FROM team_record tr
    LEFT JOIN league_priors lp
        ON tr.league = lp.league
        AND tr.season = lp.season
        AND ISNULL(tr.split, '') = ISNULL(lp.split, '')
)

SELECT
    league,
    season,
    split,
    teamname,

    series_count,
    series_wins,
    series_losses,
    game_wins,
    game_losses,

    first_series_date,
    last_series_date,

    raw_series_win_rate,
    league_win_rate,
    prior_weight,
    smoothed_series_win_rate,

    CASE
        /*
           Small sample teams stay neutral unless they are very clearly separated.
           This avoids a 2-0 team being marked strong too quickly.
        */
        WHEN series_count < 5 THEN 'neutral'

        WHEN smoothed_series_win_rate >= 0.55 THEN 'strong'
        WHEN smoothed_series_win_rate <= 0.45 THEN 'weak'
        ELSE 'neutral'
    END AS team_strength_bucket,

    CASE
        WHEN series_count < 5 THEN 'low_sample'
        WHEN series_count BETWEEN 5 AND 9 THEN 'medium_sample'
        ELSE 'solid_sample'
    END AS team_strength_sample_label
FROM smoothed;
GO