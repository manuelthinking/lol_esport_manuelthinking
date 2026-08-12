USE lol_esports;
GO

CREATE OR ALTER VIEW dbo.vw_lol_team_overview_lane_power_signal_v1 AS
SELECT
    'team_overview_lane_power_v1' AS signal_version,

    target_series_id,
    game_date,
    league,
    season,
    team,
    opponent,

    actual_series_result,
    actual_won_series,

    bayes_win_pct,
    opponent_bayes_win_pct,
    smoothed_strength_gap,

    team_strength_bucket,
    opponent_strength_bucket,
    strength_matchup_bucket,

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

    opponent_neutral_or_better_lanes,
    opponent_neutral_or_better_carry_lanes,

    total_lane_edge_tier,
    carry_lane_edge_tier,

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
        WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN 0.00

        WHEN bayes_win_pct >= 0.55
         AND carry_lane_edge >= 20
            THEN 0.05

        WHEN bayes_win_pct >= 0.55
         AND carry_lane_edge <= -15
            THEN -0.10

        WHEN bayes_win_pct BETWEEN 0.45 AND 0.55
         AND carry_lane_edge >= 20
            THEN 0.05

        WHEN bayes_win_pct BETWEEN 0.45 AND 0.55
         AND carry_lane_edge <= -20
            THEN -0.05

        ELSE 0.00
    END AS lane_power_win_pct_modifier,

    CASE
        WHEN bayes_win_pct IS NULL THEN NULL
        ELSE
            CASE
                WHEN bayes_win_pct
                    + CASE
                        WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN 0.00

                        WHEN bayes_win_pct >= 0.55
                         AND carry_lane_edge >= 20
                            THEN 0.05

                        WHEN bayes_win_pct >= 0.55
                         AND carry_lane_edge <= -15
                            THEN -0.10

                        WHEN bayes_win_pct BETWEEN 0.45 AND 0.55
                         AND carry_lane_edge >= 20
                            THEN 0.05

                        WHEN bayes_win_pct BETWEEN 0.45 AND 0.55
                         AND carry_lane_edge <= -20
                            THEN -0.05

                        ELSE 0.00
                    END > 0.95 THEN 0.95

                WHEN bayes_win_pct
                    + CASE
                        WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN 0.00

                        WHEN bayes_win_pct >= 0.55
                         AND carry_lane_edge >= 20
                            THEN 0.05

                        WHEN bayes_win_pct >= 0.55
                         AND carry_lane_edge <= -15
                            THEN -0.10

                        WHEN bayes_win_pct BETWEEN 0.45 AND 0.55
                         AND carry_lane_edge >= 20
                            THEN 0.05

                        WHEN bayes_win_pct BETWEEN 0.45 AND 0.55
                         AND carry_lane_edge <= -20
                            THEN -0.05

                        ELSE 0.00
                    END < 0.05 THEN 0.05

                ELSE bayes_win_pct
                    + CASE
                        WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL THEN 0.00

                        WHEN bayes_win_pct >= 0.55
                         AND carry_lane_edge >= 20
                            THEN 0.05

                        WHEN bayes_win_pct >= 0.55
                         AND carry_lane_edge <= -15
                            THEN -0.10

                        WHEN bayes_win_pct BETWEEN 0.45 AND 0.55
                         AND carry_lane_edge >= 20
                            THEN 0.05

                        WHEN bayes_win_pct BETWEEN 0.45 AND 0.55
                         AND carry_lane_edge <= -20
                            THEN -0.05

                        ELSE 0.00
                    END
            END
    END AS adjusted_win_pct,

    CASE
        WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL
            THEN 'Thin PIT Data'

        WHEN bayes_win_pct >= 0.55
         AND carry_lane_edge >= 20
            THEN 'Bayes Favorite + Strong Carry Support'

        WHEN bayes_win_pct >= 0.55
         AND carry_lane_edge <= -15
            THEN 'Bayes Favorite + Major Carry Concern'

        WHEN bayes_win_pct BETWEEN 0.45 AND 0.55
         AND carry_lane_edge >= 20
            THEN 'Toss-Up + Lane Power Lean'

        WHEN bayes_win_pct BETWEEN 0.45 AND 0.55
         AND carry_lane_edge <= -20
            THEN 'Toss-Up + Lane Power Fade'

        WHEN bayes_win_pct <= 0.45
         AND carry_lane_edge >= -5
            THEN 'Underdog Has Resistance'

        ELSE 'Standard Bayes Read'
    END AS dfs_lane_power_signal,

    CASE
        WHEN rated_lane_rows < 3 OR rated_lane_rows IS NULL
            THEN 'Do not adjust Bayes much. Not enough prior lane data.'

        WHEN bayes_win_pct >= 0.55
         AND carry_lane_edge >= 20
            THEN 'Upgrade favorite confidence. 2-0 or strong win path is more believable.'

        WHEN bayes_win_pct >= 0.55
         AND carry_lane_edge <= -15
            THEN 'Downgrade favorite confidence. Carry lanes are a real concern. Avoid blindly assuming a stomp.'

        WHEN bayes_win_pct BETWEEN 0.45 AND 0.55
         AND ABS(carry_lane_edge) >= 20
            THEN 'Bayes is close to neutral, but lane power gives a meaningful lean.'

        WHEN bayes_win_pct <= 0.45
         AND carry_lane_edge >= -5
            THEN 'Underdog is not dead. Consider 2-1 risk or GPP leverage.'

        ELSE 'No major lane-power adjustment.'
    END AS dfs_lane_power_note
FROM dbo.lol_bayes_lane_power_backtest_pit_snapshot;
GO