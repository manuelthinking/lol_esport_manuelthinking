USE lol_esports;
GO

CREATE OR ALTER VIEW dbo.vw_lol_lane_power_warning_backtest_v1 AS
WITH base AS (
    SELECT
        game_date,
        league,
        game_id,
        team,
        opponent,

        actual_series_result,
        actual_won_series,

        bayes_win_pct,
        bayes_favorite_status,
        bayes_lane_alignment_label,

        bayes_predicted_win_flag,
        bayes_winner_correct_flag,

        lane_power_predicted_win_flag,
        lane_power_winner_correct_flag,

        total_lane_edge,
        carry_lane_edge,
        main_carry_lane_edge,

        opponent_neutral_or_better_lanes,
        opponent_neutral_or_better_carry_lanes,

        upset_resistance_score,
        upset_resistance_tier,
        upset_signal_label,

        bayes_overconfidence_warning_flag,
        bayes_possible_upset_signal_flag,
        lane_power_breaks_bayes_tie_flag
    FROM dbo.lol_bayes_lane_power_comparison_snapshot
    WHERE actual_won_series IS NOT NULL
),
tagged AS (
    SELECT
        *,
        CASE
            WHEN bayes_overconfidence_warning_flag = 1
                THEN 'Bayes Overconfidence Warning'

            WHEN bayes_possible_upset_signal_flag = 1
                THEN 'Possible Upset Signal'

            WHEN lane_power_breaks_bayes_tie_flag = 1
                THEN 'Lane Power Breaks Bayes Tie'

            ELSE 'No Special Warning'
        END AS warning_type
    FROM base
)
SELECT
    warning_type,

    COUNT(*) AS rows_count,

    AVG(CAST(actual_won_series AS float)) AS actual_team_win_rate,

    AVG(CASE 
            WHEN bayes_winner_correct_flag IS NOT NULL 
            THEN CAST(bayes_winner_correct_flag AS float) 
        END) AS bayes_winner_accuracy,

    AVG(CASE 
            WHEN lane_power_winner_correct_flag IS NOT NULL 
            THEN CAST(lane_power_winner_correct_flag AS float) 
        END) AS lane_power_winner_accuracy,

    SUM(CASE WHEN bayes_winner_correct_flag = 1 THEN 1 ELSE 0 END) AS bayes_correct_count,
    SUM(CASE WHEN bayes_winner_correct_flag = 0 THEN 1 ELSE 0 END) AS bayes_wrong_count,

    SUM(CASE WHEN lane_power_winner_correct_flag = 1 THEN 1 ELSE 0 END) AS lane_power_correct_count,
    SUM(CASE WHEN lane_power_winner_correct_flag = 0 THEN 1 ELSE 0 END) AS lane_power_wrong_count,

    AVG(bayes_win_pct) AS avg_bayes_win_pct,
    AVG(total_lane_edge) AS avg_total_lane_edge,
    AVG(carry_lane_edge) AS avg_carry_lane_edge,
    AVG(CAST(upset_resistance_score AS float)) AS avg_upset_resistance_score
FROM tagged
GROUP BY warning_type;
GO