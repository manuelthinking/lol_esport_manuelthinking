USE lol_esports;
GO

CREATE OR ALTER VIEW dbo.vw_lol_bayes_lane_power_backtest_summary_pit_v1 AS
WITH base AS (
    SELECT
        *
    FROM dbo.vw_lol_bayes_lane_power_backtest_pit_v1
    WHERE actual_won_series IS NOT NULL
),
overall AS (
    SELECT
        'Overall' AS summary_group,
        'All Series' AS summary_bucket,
        COUNT(*) AS rows_count,

        SUM(CASE WHEN bayes_winner_correct_flag IS NOT NULL THEN 1 ELSE 0 END) AS bayes_eval_rows,
        AVG(CASE WHEN bayes_winner_correct_flag IS NOT NULL THEN CAST(bayes_winner_correct_flag AS float) END) AS bayes_winner_accuracy,

        SUM(CASE WHEN lane_power_winner_correct_flag IS NOT NULL THEN 1 ELSE 0 END) AS lane_power_eval_rows,
        AVG(CASE WHEN lane_power_winner_correct_flag IS NOT NULL THEN CAST(lane_power_winner_correct_flag AS float) END) AS lane_power_winner_accuracy,

        SUM(CASE WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN 1 ELSE 0 END) AS thin_pit_rows
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

        SUM(CASE WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN 1 ELSE 0 END) AS thin_pit_rows
    FROM base
    GROUP BY bayes_lane_alignment_label
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

        SUM(CASE WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN 1 ELSE 0 END) AS thin_pit_rows
    FROM base
    GROUP BY bayes_favorite_status
),
by_resistance AS (
    SELECT
        'Upset Resistance Tier' AS summary_group,
        upset_resistance_tier AS summary_bucket,
        COUNT(*) AS rows_count,

        SUM(CASE WHEN bayes_winner_correct_flag IS NOT NULL THEN 1 ELSE 0 END) AS bayes_eval_rows,
        AVG(CASE WHEN bayes_winner_correct_flag IS NOT NULL THEN CAST(bayes_winner_correct_flag AS float) END) AS bayes_winner_accuracy,

        SUM(CASE WHEN lane_power_winner_correct_flag IS NOT NULL THEN 1 ELSE 0 END) AS lane_power_eval_rows,
        AVG(CASE WHEN lane_power_winner_correct_flag IS NOT NULL THEN CAST(lane_power_winner_correct_flag AS float) END) AS lane_power_winner_accuracy,

        SUM(CASE WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN 1 ELSE 0 END) AS thin_pit_rows
    FROM base
    GROUP BY upset_resistance_tier
)
SELECT * FROM overall
UNION ALL
SELECT * FROM by_alignment
UNION ALL
SELECT * FROM by_bayes_status
UNION ALL
SELECT * FROM by_resistance;
GO