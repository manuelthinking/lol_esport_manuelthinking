USE lol_esports;
GO

CREATE OR ALTER VIEW dbo.vw_lol_bayes_lane_power_backtest_summary_v1 AS
WITH base AS (
    SELECT
        comparison_version,
        game_date,
        league,
        game_id,
        team,
        opponent,

        actual_series_result,
        actual_won_series,

        bayes_win_pct,
        bayes_predicted_win_flag,
        bayes_winner_correct_flag,

        lane_power_predicted_win_flag,
        lane_power_winner_correct_flag,

        bayes_favorite_status,
        bayes_lane_alignment_label,

        team_strength_bucket,
        opponent_strength_bucket,
        strength_matchup_bucket,

        total_lane_edge,
        carry_lane_edge,
        main_carry_lane_edge,

        upset_resistance_score,
        upset_resistance_tier,
        upset_signal_label,

        bayes_overconfidence_warning_flag,
        bayes_possible_upset_signal_flag,
        lane_power_breaks_bayes_tie_flag,

        favorite_stomp_warning_flag,
        underdog_live_flag,
        favorite_stomp_support_flag
    FROM dbo.lol_bayes_lane_power_comparison_snapshot
    WHERE actual_won_series IS NOT NULL
),
overall AS (
    SELECT
        'Overall' AS summary_group,
        'All Matches' AS summary_bucket,

        COUNT(*) AS rows_count,

        SUM(CASE WHEN bayes_winner_correct_flag IS NOT NULL THEN 1 ELSE 0 END) AS bayes_eval_rows,
        AVG(CASE WHEN bayes_winner_correct_flag IS NOT NULL THEN CAST(bayes_winner_correct_flag AS float) END) AS bayes_winner_accuracy,

        SUM(CASE WHEN lane_power_winner_correct_flag IS NOT NULL THEN 1 ELSE 0 END) AS lane_power_eval_rows,
        AVG(CASE WHEN lane_power_winner_correct_flag IS NOT NULL THEN CAST(lane_power_winner_correct_flag AS float) END) AS lane_power_winner_accuracy,

        SUM(CASE WHEN bayes_winner_correct_flag = 1 THEN 1 ELSE 0 END) AS bayes_correct_count,
        SUM(CASE WHEN bayes_winner_correct_flag = 0 THEN 1 ELSE 0 END) AS bayes_wrong_count,

        SUM(CASE WHEN lane_power_winner_correct_flag = 1 THEN 1 ELSE 0 END) AS lane_power_correct_count,
        SUM(CASE WHEN lane_power_winner_correct_flag = 0 THEN 1 ELSE 0 END) AS lane_power_wrong_count
    FROM base
),
by_alignment AS (
    SELECT
        'Bayes/Lane Alignment' AS summary_group,
        bayes_lane_alignment_label AS summary_bucket,

        COUNT(*) AS rows_count,

        SUM(CASE WHEN bayes_winner_correct_flag IS NOT NULL THEN 1 ELSE 0 END) AS bayes_eval_rows,
        AVG(CASE WHEN bayes_winner_correct_flag IS NOT NULL THEN CAST(bayes_winner_correct_flag AS float) END) AS bayes_winner_accuracy,

        SUM(CASE WHEN lane_power_winner_correct_flag IS NOT NULL THEN 1 ELSE 0 END) AS lane_power_eval_rows,
        AVG(CASE WHEN lane_power_winner_correct_flag IS NOT NULL THEN CAST(lane_power_winner_correct_flag AS float) END) AS lane_power_winner_accuracy,

        SUM(CASE WHEN bayes_winner_correct_flag = 1 THEN 1 ELSE 0 END) AS bayes_correct_count,
        SUM(CASE WHEN bayes_winner_correct_flag = 0 THEN 1 ELSE 0 END) AS bayes_wrong_count,

        SUM(CASE WHEN lane_power_winner_correct_flag = 1 THEN 1 ELSE 0 END) AS lane_power_correct_count,
        SUM(CASE WHEN lane_power_winner_correct_flag = 0 THEN 1 ELSE 0 END) AS lane_power_wrong_count
    FROM base
    GROUP BY bayes_lane_alignment_label
),
by_upset_signal AS (
    SELECT
        'Upset Signal' AS summary_group,
        upset_signal_label AS summary_bucket,

        COUNT(*) AS rows_count,

        SUM(CASE WHEN bayes_winner_correct_flag IS NOT NULL THEN 1 ELSE 0 END) AS bayes_eval_rows,
        AVG(CASE WHEN bayes_winner_correct_flag IS NOT NULL THEN CAST(bayes_winner_correct_flag AS float) END) AS bayes_winner_accuracy,

        SUM(CASE WHEN lane_power_winner_correct_flag IS NOT NULL THEN 1 ELSE 0 END) AS lane_power_eval_rows,
        AVG(CASE WHEN lane_power_winner_correct_flag IS NOT NULL THEN CAST(lane_power_winner_correct_flag AS float) END) AS lane_power_winner_accuracy,

        SUM(CASE WHEN bayes_winner_correct_flag = 1 THEN 1 ELSE 0 END) AS bayes_correct_count,
        SUM(CASE WHEN bayes_winner_correct_flag = 0 THEN 1 ELSE 0 END) AS bayes_wrong_count,

        SUM(CASE WHEN lane_power_winner_correct_flag = 1 THEN 1 ELSE 0 END) AS lane_power_correct_count,
        SUM(CASE WHEN lane_power_winner_correct_flag = 0 THEN 1 ELSE 0 END) AS lane_power_wrong_count
    FROM base
    GROUP BY upset_signal_label
),
by_resistance_tier AS (
    SELECT
        'Upset Resistance Tier' AS summary_group,
        upset_resistance_tier AS summary_bucket,

        COUNT(*) AS rows_count,

        SUM(CASE WHEN bayes_winner_correct_flag IS NOT NULL THEN 1 ELSE 0 END) AS bayes_eval_rows,
        AVG(CASE WHEN bayes_winner_correct_flag IS NOT NULL THEN CAST(bayes_winner_correct_flag AS float) END) AS bayes_winner_accuracy,

        SUM(CASE WHEN lane_power_winner_correct_flag IS NOT NULL THEN 1 ELSE 0 END) AS lane_power_eval_rows,
        AVG(CASE WHEN lane_power_winner_correct_flag IS NOT NULL THEN CAST(lane_power_winner_correct_flag AS float) END) AS lane_power_winner_accuracy,

        SUM(CASE WHEN bayes_winner_correct_flag = 1 THEN 1 ELSE 0 END) AS bayes_correct_count,
        SUM(CASE WHEN bayes_winner_correct_flag = 0 THEN 1 ELSE 0 END) AS bayes_wrong_count,

        SUM(CASE WHEN lane_power_winner_correct_flag = 1 THEN 1 ELSE 0 END) AS lane_power_correct_count,
        SUM(CASE WHEN lane_power_winner_correct_flag = 0 THEN 1 ELSE 0 END) AS lane_power_wrong_count
    FROM base
    GROUP BY upset_resistance_tier
),
by_bayes_status AS (
    SELECT
        'Bayes Favorite Status' AS summary_group,
        bayes_favorite_status AS summary_bucket,

        COUNT(*) AS rows_count,

        SUM(CASE WHEN bayes_winner_correct_flag IS NOT NULL THEN 1 ELSE 0 END) AS bayes_eval_rows,
        AVG(CASE WHEN bayes_winner_correct_flag IS NOT NULL THEN CAST(bayes_winner_correct_flag AS float) END) AS bayes_winner_accuracy,

        SUM(CASE WHEN lane_power_winner_correct_flag IS NOT NULL THEN 1 ELSE 0 END) AS lane_power_eval_rows,
        AVG(CASE WHEN lane_power_winner_correct_flag IS NOT NULL THEN CAST(lane_power_winner_correct_flag AS float) END) AS lane_power_winner_accuracy,

        SUM(CASE WHEN bayes_winner_correct_flag = 1 THEN 1 ELSE 0 END) AS bayes_correct_count,
        SUM(CASE WHEN bayes_winner_correct_flag = 0 THEN 1 ELSE 0 END) AS bayes_wrong_count,

        SUM(CASE WHEN lane_power_winner_correct_flag = 1 THEN 1 ELSE 0 END) AS lane_power_correct_count,
        SUM(CASE WHEN lane_power_winner_correct_flag = 0 THEN 1 ELSE 0 END) AS lane_power_wrong_count
    FROM base
    GROUP BY bayes_favorite_status
)
SELECT * FROM overall
UNION ALL
SELECT * FROM by_alignment
UNION ALL
SELECT * FROM by_upset_signal
UNION ALL
SELECT * FROM by_resistance_tier
UNION ALL
SELECT * FROM by_bayes_status;
GO