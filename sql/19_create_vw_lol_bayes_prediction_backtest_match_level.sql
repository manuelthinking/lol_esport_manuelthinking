/* ============================================================
   LoL Bayesian Prediction Backtest - Match Level View

   Purpose:
     Convert team-side backtest rows into one row per historical
     match/series.

   Source:
     dbo.lol_bayes_prediction_backtest

   Grain:
     one row per target_series_id

   Output:
     predicted winner
     predicted score
     actual winner
     actual score
     winner correct
     score correct
     path correct
     team-side Bayesian probabilities
   ============================================================ */

IF OBJECT_ID('dbo.vw_lol_bayes_prediction_backtest_match_level', 'V') IS NOT NULL
BEGIN
    DROP VIEW dbo.vw_lol_bayes_prediction_backtest_match_level;
END;
GO

CREATE VIEW dbo.vw_lol_bayes_prediction_backtest_match_level AS

WITH base AS
(
    SELECT
        backtest_id,
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

        strength_matchup_bucket,
        mid_lane_matchup_bucket,
        bot_lane_matchup_bucket,
        sup_lane_matchup_bucket,

        sample_type,
        similar_sample,

        bayes_win_pct,
        bayes_p_2_0,
        bayes_p_2_1,
        bayes_p_1_2,
        bayes_p_0_2,

        suggested_path,
        suggested_winner_teamname,
        suggested_match_score,

        winner_correct,
        score_correct,
        path_correct,

        dfs_note,
        prediction_source,
        prior_weight,
        created_at,
        updated_at
    FROM dbo.lol_bayes_prediction_backtest
    WHERE prediction_source = 'historical_point_in_time_bayes'
),

ranked AS
(
    SELECT
        b.*,

        ROW_NUMBER() OVER (
            PARTITION BY target_series_id
            ORDER BY bayes_win_pct DESC, similar_sample DESC, teamname
        ) AS prediction_rank,

        ROW_NUMBER() OVER (
            PARTITION BY target_series_id
            ORDER BY teamname
        ) AS team_order
    FROM base b
),

team_a AS
(
    SELECT
        *
    FROM ranked
    WHERE team_order = 1
),

team_b AS
(
    SELECT
        *
    FROM ranked
    WHERE team_order = 2
),

best_prediction AS
(
    SELECT
        *
    FROM ranked
    WHERE prediction_rank = 1
),

actual_winner AS
(
    SELECT
        target_series_id,
        MAX(CASE WHEN actual_won_series = 1 THEN teamname END) AS actual_winner_teamname,
        MAX(CASE WHEN actual_won_series = 0 THEN teamname END) AS actual_loser_teamname,
        MAX(
            CASE
                WHEN actual_series_result IN ('2-0', '0-2') THEN '2-0'
                WHEN actual_series_result IN ('2-1', '1-2') THEN '2-1'
                ELSE NULL
            END
        ) AS actual_match_score
    FROM base
    GROUP BY
        target_series_id
)

SELECT
    bp.target_series_id,
    bp.league,
    bp.season,
    bp.target_series_date,

    a.teamname AS team_a,
    b.teamname AS team_b,

    a.bayes_win_pct AS team_a_bayes_win_pct,
    b.bayes_win_pct AS team_b_bayes_win_pct,

    a.suggested_path AS team_a_suggested_path,
    b.suggested_path AS team_b_suggested_path,

    a.sample_type AS team_a_sample_type,
    b.sample_type AS team_b_sample_type,

    a.similar_sample AS team_a_similar_sample,
    b.similar_sample AS team_b_similar_sample,

    a.strength_matchup_bucket AS team_a_strength_matchup,
    b.strength_matchup_bucket AS team_b_strength_matchup,

    a.mid_lane_matchup_bucket AS team_a_mid_matchup,
    b.mid_lane_matchup_bucket AS team_b_mid_matchup,

    a.bot_lane_matchup_bucket AS team_a_bot_matchup,
    b.bot_lane_matchup_bucket AS team_b_bot_matchup,

    a.sup_lane_matchup_bucket AS team_a_sup_matchup,
    b.sup_lane_matchup_bucket AS team_b_sup_matchup,

    bp.teamname AS predicted_winner_teamname,

    CASE
        WHEN bp.suggested_path IN ('2-0', '0-2') THEN '2-0'
        WHEN bp.suggested_path IN ('2-1', '1-2') THEN '2-1'
        ELSE bp.suggested_match_score
    END AS predicted_match_score,

    bp.suggested_path AS predicted_team_path,
    bp.bayes_win_pct AS predicted_winner_bayes_win_pct,
    bp.sample_type AS prediction_sample_type,
    bp.similar_sample AS prediction_similar_sample,

    bp.bayes_p_2_0 AS predicted_team_p_2_0,
    bp.bayes_p_2_1 AS predicted_team_p_2_1,
    bp.bayes_p_1_2 AS predicted_team_p_1_2,
    bp.bayes_p_0_2 AS predicted_team_p_0_2,

    aw.actual_winner_teamname,
    aw.actual_loser_teamname,
    aw.actual_match_score,

    CASE
        WHEN bp.teamname = aw.actual_winner_teamname THEN CAST(1 AS BIT)
        ELSE CAST(0 AS BIT)
    END AS match_winner_correct,

    CASE
        WHEN
            CASE
                WHEN bp.suggested_path IN ('2-0', '0-2') THEN '2-0'
                WHEN bp.suggested_path IN ('2-1', '1-2') THEN '2-1'
                ELSE bp.suggested_match_score
            END
            =
            aw.actual_match_score
        THEN CAST(1 AS BIT)
        ELSE CAST(0 AS BIT)
    END AS match_score_correct,

    CASE
        WHEN bp.teamname = aw.actual_winner_teamname
         AND
            CASE
                WHEN bp.suggested_path IN ('2-0', '0-2') THEN '2-0'
                WHEN bp.suggested_path IN ('2-1', '1-2') THEN '2-1'
                ELSE bp.suggested_match_score
            END
            =
            aw.actual_match_score
        THEN CAST(1 AS BIT)
        ELSE CAST(0 AS BIT)
    END AS match_winner_and_score_correct,

    CASE
        WHEN bp.sample_type = 'League Prior Only'
            THEN 'Low confidence: league prior only.'
        WHEN bp.similar_sample < 8
            THEN 'Thin sample: directional only.'
        WHEN bp.bayes_win_pct >= 65
            THEN 'Strong model lean.'
        WHEN bp.bayes_win_pct >= 58
            THEN 'Moderate model lean.'
        WHEN bp.bayes_win_pct >= 52
            THEN 'Small model lean.'
        ELSE 'No clear model lean.'
    END AS match_confidence_label,

    bp.dfs_note,
    bp.prior_weight,
    bp.created_at,
    bp.updated_at

FROM best_prediction bp
LEFT JOIN team_a a
    ON bp.target_series_id = a.target_series_id
LEFT JOIN team_b b
    ON bp.target_series_id = b.target_series_id
LEFT JOIN actual_winner aw
    ON bp.target_series_id = aw.target_series_id;
GO