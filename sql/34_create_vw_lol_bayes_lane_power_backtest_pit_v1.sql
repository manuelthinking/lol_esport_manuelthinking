USE lol_esports;
GO

CREATE OR ALTER VIEW dbo.vw_lol_bayes_lane_power_backtest_pit_v1 AS
WITH bayes AS (
    SELECT
        target_series_id,
        league,
        season,
        target_series_date,
        teamname AS team,
        opponent_teamname AS opponent,

        actual_series_result,
        actual_won_series,
        actual_game_wins,
        actual_game_losses,

        team_strength_bucket,
        opponent_strength_bucket,
        strength_matchup_bucket,

        team_smoothed_prior_series_win_rate AS bayes_win_pct,
        opponent_smoothed_prior_series_win_rate AS opponent_bayes_win_pct,
        smoothed_strength_gap,

        team_prior_series_count,
        opponent_prior_series_count
    FROM dbo.vw_lol_bayes_strength_matchups_point_in_time
    WHERE league IN ('LPL', 'LCK')
      AND season = 2026
),
lane AS (
    SELECT
        *
    FROM dbo.vw_lol_matchup_lane_edge_summary_pit_v1
),
joined AS (
    SELECT
        b.target_series_id,
        b.league,
        b.season,
        b.target_series_date AS game_date,
        b.team,
        b.opponent,

        b.actual_series_result,
        b.actual_won_series,
        b.actual_game_wins,
        b.actual_game_losses,

        b.team_strength_bucket,
        b.opponent_strength_bucket,
        b.strength_matchup_bucket,

        b.bayes_win_pct,
        b.opponent_bayes_win_pct,
        b.smoothed_strength_gap,

        b.team_prior_series_count,
        b.opponent_prior_series_count,

        l.lane_rows,
        l.rated_lane_rows,

        l.top_lane_edge,
        l.jng_lane_edge,
        l.mid_lane_edge,
        l.adc_lane_edge,
        l.sup_lane_edge,

        l.total_lane_edge,
        l.carry_lane_edge,
        l.main_carry_lane_edge,
        l.secondary_lane_edge,

        l.clear_edge_lanes,
        l.clear_disadvantage_lanes,
        l.positive_edge_lanes,
        l.negative_edge_lanes,
        l.positive_carry_edge_lanes,
        l.negative_carry_edge_lanes,

        l.opponent_neutral_or_better_lanes,
        l.opponent_neutral_or_better_carry_lanes,

        l.min_team_prior_games,
        l.min_opponent_prior_games,
        l.avg_team_prior_games,
        l.avg_opponent_prior_games,

        l.total_lane_edge_tier,
        l.carry_lane_edge_tier
    FROM bayes b
    LEFT JOIN lane l
        ON b.target_series_id = l.target_series_id
       AND b.team = l.team
       AND b.opponent = l.opponent
),
scored AS (
    SELECT
        *,

        CASE
            WHEN bayes_win_pct IS NULL THEN NULL
            WHEN bayes_win_pct >= 0.50 THEN 1
            ELSE 0
        END AS bayes_predicted_win_flag,

        CASE
            WHEN rated_lane_rows < 3 THEN NULL
            WHEN carry_lane_edge >= 5 THEN 1
            WHEN carry_lane_edge <= -5 THEN 0
            ELSE NULL
        END AS lane_power_predicted_win_flag,

        CASE
            WHEN bayes_win_pct IS NULL THEN 'No Bayes'
            WHEN bayes_win_pct >= 0.65 THEN 'Bayes Strong Favorite'
            WHEN bayes_win_pct >= 0.55 THEN 'Bayes Lean Favorite'
            WHEN bayes_win_pct > 0.45 THEN 'Bayes Toss-Up'
            WHEN bayes_win_pct > 0.35 THEN 'Bayes Lean Underdog'
            ELSE 'Bayes Strong Underdog'
        END AS bayes_favorite_status,

        CASE
            WHEN rated_lane_rows < 3 THEN 'Thin PIT Rating'
            WHEN total_lane_edge >= 25 THEN 'Lane Favorite'
            WHEN total_lane_edge <= -25 THEN 'Lane Underdog'
            WHEN total_lane_edge >= 10 THEN 'Small Lane Favorite'
            WHEN total_lane_edge <= -10 THEN 'Small Lane Underdog'
            ELSE 'Lane Neutral'
        END AS lane_favorite_status,

        CASE
            WHEN rated_lane_rows < 3 THEN NULL
            WHEN opponent_neutral_or_better_carry_lanes >= 3 THEN 3
            WHEN opponent_neutral_or_better_carry_lanes = 2 THEN 2
            WHEN opponent_neutral_or_better_carry_lanes = 1 THEN 1
            ELSE 0
        END AS opponent_carry_resistance_level,

        CASE
            WHEN rated_lane_rows < 3 THEN NULL
            WHEN carry_lane_edge <= -15 THEN 3
            WHEN carry_lane_edge <= -5 THEN 2
            WHEN carry_lane_edge < 5 THEN 1
            ELSE 0
        END AS carry_lane_risk_level,

        CASE
            WHEN rated_lane_rows < 3 THEN NULL
            WHEN negative_carry_edge_lanes >= 3 THEN 3
            WHEN negative_carry_edge_lanes = 2 THEN 2
            WHEN negative_carry_edge_lanes = 1 THEN 1
            ELSE 0
        END AS negative_carry_lane_count_level
    FROM joined
),
final_scored AS (
    SELECT
        *,

        CASE
            WHEN rated_lane_rows < 3 THEN NULL
            ELSE (
                opponent_carry_resistance_level * 2
                + carry_lane_risk_level * 2
                + negative_carry_lane_count_level
            )
        END AS upset_resistance_score,

        CASE
            WHEN rated_lane_rows < 3 THEN 'Thin PIT Rating'

            WHEN bayes_win_pct >= 0.65
             AND total_lane_edge >= 25
             AND carry_lane_edge >= 15
             AND opponent_neutral_or_better_carry_lanes <= 1
             AND negative_carry_edge_lanes = 0
                THEN 'Bayes Favorite / Lane Stomp Support'

            WHEN bayes_win_pct >= 0.65
             AND total_lane_edge >= 25
             AND opponent_neutral_or_better_carry_lanes >= 2
                THEN 'Bayes Favorite / Lane Stomp Warning'

            WHEN bayes_win_pct >= 0.55
             AND carry_lane_edge < 0
                THEN 'Bayes Favorite / Carry Lanes Questionable'

            WHEN bayes_win_pct <= 0.45
             AND carry_lane_edge >= -5
                THEN 'Bayes Underdog / Lane Power Live'

            WHEN bayes_win_pct BETWEEN 0.45 AND 0.55
             AND ABS(carry_lane_edge) >= 10
                THEN 'Bayes Toss-Up / Lane Power Has Lean'

            ELSE 'Bayes and Lane Signal Aligned or Neutral'
        END AS bayes_lane_alignment_label,

        CASE
            WHEN rated_lane_rows < 3 THEN 0
            WHEN bayes_win_pct >= 0.65
             AND total_lane_edge >= 25
             AND opponent_neutral_or_better_carry_lanes >= 2
                THEN 1
            ELSE 0
        END AS bayes_overconfidence_warning_flag,

        CASE
            WHEN rated_lane_rows < 3 THEN 0
            WHEN bayes_win_pct <= 0.45
             AND carry_lane_edge >= -5
                THEN 1
            ELSE 0
        END AS bayes_possible_upset_signal_flag,

        CASE
            WHEN rated_lane_rows < 3 THEN 0
            WHEN bayes_win_pct BETWEEN 0.45 AND 0.55
             AND ABS(carry_lane_edge) >= 10
                THEN 1
            ELSE 0
        END AS lane_power_breaks_bayes_tie_flag,

        CASE
            WHEN rated_lane_rows < 3 THEN 0
            WHEN bayes_win_pct >= 0.65
             AND total_lane_edge >= 25
             AND carry_lane_edge >= 15
             AND opponent_neutral_or_better_carry_lanes <= 1
             AND negative_carry_edge_lanes = 0
                THEN 1
            ELSE 0
        END AS favorite_stomp_support_flag
    FROM scored
)
SELECT
    'bayes_lane_power_pit_v1' AS backtest_version,

    target_series_id,
    game_date,
    league,
    season,
    team,
    opponent,

    actual_series_result,
    actual_won_series,
    actual_game_wins,
    actual_game_losses,

    bayes_win_pct,
    opponent_bayes_win_pct,
    smoothed_strength_gap,

    team_strength_bucket,
    opponent_strength_bucket,
    strength_matchup_bucket,

    team_prior_series_count,
    opponent_prior_series_count,

    lane_rows,
    rated_lane_rows,

    top_lane_edge,
    jng_lane_edge,
    mid_lane_edge,
    adc_lane_edge,
    sup_lane_edge,

    total_lane_edge,
    carry_lane_edge,
    main_carry_lane_edge,
    secondary_lane_edge,

    positive_carry_edge_lanes,
    negative_carry_edge_lanes,

    opponent_neutral_or_better_lanes,
    opponent_neutral_or_better_carry_lanes,

    min_team_prior_games,
    min_opponent_prior_games,
    avg_team_prior_games,
    avg_opponent_prior_games,

    total_lane_edge_tier,
    carry_lane_edge_tier,

    bayes_predicted_win_flag,
    lane_power_predicted_win_flag,

    bayes_favorite_status,
    lane_favorite_status,

    upset_resistance_score,

    CASE
        WHEN upset_resistance_score IS NULL THEN 'Thin PIT Rating'
        WHEN upset_resistance_score >= 8 THEN 'High Resistance'
        WHEN upset_resistance_score >= 5 THEN 'Medium Resistance'
        WHEN upset_resistance_score >= 2 THEN 'Low Resistance'
        ELSE 'Minimal Resistance'
    END AS upset_resistance_tier,

    bayes_lane_alignment_label,

    bayes_overconfidence_warning_flag,
    bayes_possible_upset_signal_flag,
    lane_power_breaks_bayes_tie_flag,
    favorite_stomp_support_flag,

    CASE
        WHEN bayes_win_pct IS NULL OR actual_won_series IS NULL THEN NULL
        WHEN bayes_win_pct >= 0.50 AND actual_won_series = 1 THEN 1
        WHEN bayes_win_pct < 0.50 AND actual_won_series = 0 THEN 1
        ELSE 0
    END AS bayes_winner_correct_flag,

    CASE
        WHEN actual_won_series IS NULL THEN NULL
        WHEN lane_power_predicted_win_flag IS NULL THEN NULL
        WHEN lane_power_predicted_win_flag = actual_won_series THEN 1
        ELSE 0
    END AS lane_power_winner_correct_flag
FROM final_scored;
GO