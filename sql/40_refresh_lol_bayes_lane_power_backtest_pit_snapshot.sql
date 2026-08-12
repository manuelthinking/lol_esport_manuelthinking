USE lol_esports;
GO

TRUNCATE TABLE dbo.lol_bayes_lane_power_backtest_pit_snapshot;

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
lane_summary AS (
    SELECT
        target_series_id,
        game_date,
        league,
        season,
        team,
        opponent,

        COUNT(*) AS lane_rows,
        SUM(CASE WHEN lane_power_edge IS NOT NULL THEN 1 ELSE 0 END) AS rated_lane_rows,

        MAX(CASE WHEN lane = 'TOP' THEN lane_power_edge END) AS top_lane_edge,
        MAX(CASE WHEN lane = 'JNG' THEN lane_power_edge END) AS jng_lane_edge,
        MAX(CASE WHEN lane = 'MID' THEN lane_power_edge END) AS mid_lane_edge,
        MAX(CASE WHEN lane = 'ADC' THEN lane_power_edge END) AS adc_lane_edge,
        MAX(CASE WHEN lane = 'SUP' THEN lane_power_edge END) AS sup_lane_edge,

        SUM(CASE WHEN lane_power_edge IS NOT NULL THEN lane_power_edge ELSE 0 END) AS total_lane_edge,

        SUM(CASE 
                WHEN lane IN ('JNG', 'MID', 'ADC') AND lane_power_edge IS NOT NULL
                THEN lane_power_edge ELSE 0 
            END) AS carry_lane_edge,

        SUM(CASE 
                WHEN lane IN ('MID', 'ADC') AND lane_power_edge IS NOT NULL
                THEN lane_power_edge ELSE 0 
            END) AS main_carry_lane_edge,

        SUM(CASE 
                WHEN lane IN ('TOP', 'SUP') AND lane_power_edge IS NOT NULL
                THEN lane_power_edge ELSE 0 
            END) AS secondary_lane_edge,

        SUM(CASE 
                WHEN lane IN ('JNG', 'MID', 'ADC') 
                 AND lane_power_edge >= 3 
                THEN 1 ELSE 0 
            END) AS positive_carry_edge_lanes,

        SUM(CASE 
                WHEN lane IN ('JNG', 'MID', 'ADC') 
                 AND lane_power_edge <= -3 
                THEN 1 ELSE 0 
            END) AS negative_carry_edge_lanes,

        SUM(CASE 
                WHEN opponent_lane_power_tier IN ('Elite', 'Strong', 'Neutral')
                THEN 1 ELSE 0 
            END) AS opponent_neutral_or_better_lanes,

        SUM(CASE 
                WHEN lane IN ('JNG', 'MID', 'ADC')
                 AND opponent_lane_power_tier IN ('Elite', 'Strong', 'Neutral')
                THEN 1 ELSE 0 
            END) AS opponent_neutral_or_better_carry_lanes,

        MIN(prior_games_played) AS min_team_prior_games,
        MIN(opponent_prior_games_played) AS min_opponent_prior_games,

        AVG(CAST(prior_games_played AS float)) AS avg_team_prior_games,
        AVG(CAST(opponent_prior_games_played AS float)) AS avg_opponent_prior_games
    FROM dbo.lol_matchup_lane_edges_pit_snapshot
    GROUP BY
        target_series_id,
        game_date,
        league,
        season,
        team,
        opponent
),
joined AS (
    SELECT
        b.*,

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

        l.positive_carry_edge_lanes,
        l.negative_carry_edge_lanes,

        l.opponent_neutral_or_better_lanes,
        l.opponent_neutral_or_better_carry_lanes,

        l.min_team_prior_games,
        l.min_opponent_prior_games,
        l.avg_team_prior_games,
        l.avg_opponent_prior_games
    FROM bayes b
    LEFT JOIN lane_summary l
        ON b.target_series_id = l.target_series_id
       AND b.team = l.team
       AND b.opponent = l.opponent
),
scored AS (
    SELECT
        *,

        CASE
            WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN 'Thin PIT Rating'
            WHEN total_lane_edge >= 50 THEN 'Massive Overall Lane Edge'
            WHEN total_lane_edge >= 25 THEN 'Strong Overall Lane Edge'
            WHEN total_lane_edge >= 10 THEN 'Moderate Overall Lane Edge'
            WHEN total_lane_edge > -10 THEN 'Mostly Even Overall'
            WHEN total_lane_edge > -25 THEN 'Moderate Overall Lane Disadvantage'
            WHEN total_lane_edge > -50 THEN 'Strong Overall Lane Disadvantage'
            ELSE 'Massive Overall Lane Disadvantage'
        END AS total_lane_edge_tier,

        CASE
            WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN 'Thin PIT Rating'
            WHEN carry_lane_edge >= 30 THEN 'Massive Carry Lane Edge'
            WHEN carry_lane_edge >= 15 THEN 'Strong Carry Lane Edge'
            WHEN carry_lane_edge >= 5 THEN 'Moderate Carry Lane Edge'
            WHEN carry_lane_edge > -5 THEN 'Mostly Even Carry Lanes'
            WHEN carry_lane_edge > -15 THEN 'Moderate Carry Lane Disadvantage'
            WHEN carry_lane_edge > -30 THEN 'Strong Carry Lane Disadvantage'
            ELSE 'Massive Carry Lane Disadvantage'
        END AS carry_lane_edge_tier,

        CASE
            WHEN bayes_win_pct IS NULL THEN NULL
            WHEN bayes_win_pct >= 0.50 THEN 1
            ELSE 0
        END AS bayes_predicted_win_flag,

        CASE
            WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN NULL
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
            WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN 'Thin PIT Rating'
            WHEN total_lane_edge >= 25 THEN 'Lane Favorite'
            WHEN total_lane_edge <= -25 THEN 'Lane Underdog'
            WHEN total_lane_edge >= 10 THEN 'Small Lane Favorite'
            WHEN total_lane_edge <= -10 THEN 'Small Lane Underdog'
            ELSE 'Lane Neutral'
        END AS lane_favorite_status,

        CASE
            WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN NULL
            ELSE
                (
                    CASE
                        WHEN opponent_neutral_or_better_carry_lanes >= 3 THEN 3
                        WHEN opponent_neutral_or_better_carry_lanes = 2 THEN 2
                        WHEN opponent_neutral_or_better_carry_lanes = 1 THEN 1
                        ELSE 0
                    END * 2
                    +
                    CASE
                        WHEN carry_lane_edge <= -15 THEN 3
                        WHEN carry_lane_edge <= -5 THEN 2
                        WHEN carry_lane_edge < 5 THEN 1
                        ELSE 0
                    END * 2
                    +
                    CASE
                        WHEN negative_carry_edge_lanes >= 3 THEN 3
                        WHEN negative_carry_edge_lanes = 2 THEN 2
                        WHEN negative_carry_edge_lanes = 1 THEN 1
                        ELSE 0
                    END
                )
        END AS upset_resistance_score
    FROM joined
),
final_scored AS (
    SELECT
        *,

        CASE
            WHEN upset_resistance_score IS NULL THEN 'Thin PIT Rating'
            WHEN upset_resistance_score >= 8 THEN 'High Resistance'
            WHEN upset_resistance_score >= 5 THEN 'Medium Resistance'
            WHEN upset_resistance_score >= 2 THEN 'Low Resistance'
            ELSE 'Minimal Resistance'
        END AS upset_resistance_tier,

        CASE
            WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL
                THEN 'Thin PIT Rating'

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
            WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN 0
            WHEN bayes_win_pct >= 0.65
             AND total_lane_edge >= 25
             AND opponent_neutral_or_better_carry_lanes >= 2
                THEN 1
            ELSE 0
        END AS bayes_overconfidence_warning_flag,

        CASE
            WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN 0
            WHEN bayes_win_pct <= 0.45
             AND carry_lane_edge >= -5
                THEN 1
            ELSE 0
        END AS bayes_possible_upset_signal_flag,

        CASE
            WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN 0
            WHEN bayes_win_pct BETWEEN 0.45 AND 0.55
             AND ABS(carry_lane_edge) >= 10
                THEN 1
            ELSE 0
        END AS lane_power_breaks_bayes_tie_flag,

        CASE
            WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN 0
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
INSERT INTO dbo.lol_bayes_lane_power_backtest_pit_snapshot (
    backtest_version,
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
    upset_resistance_tier,

    bayes_lane_alignment_label,

    bayes_overconfidence_warning_flag,
    bayes_possible_upset_signal_flag,
    lane_power_breaks_bayes_tie_flag,
    favorite_stomp_support_flag,

    bayes_winner_correct_flag,
    lane_power_winner_correct_flag
)
SELECT
    'bayes_lane_power_pit_v1' AS backtest_version,
    target_series_id,
    target_series_date AS game_date,
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
    upset_resistance_tier,

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