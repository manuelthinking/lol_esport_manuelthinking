USE lol_esports;
GO

CREATE OR ALTER VIEW dbo.vw_lol_upset_resistance_signal_v1 AS
WITH base AS (
    SELECT
        model_version,
        game_id,
        game_date,
        league,
        season,
        split,
        team,
        opponent,

        top_lane_edge,
        jng_lane_edge,
        mid_lane_edge,
        adc_lane_edge,
        sup_lane_edge,

        total_lane_edge,
        carry_lane_edge,
        main_carry_lane_edge,
        secondary_lane_edge,

        clear_edge_lanes,
        clear_disadvantage_lanes,
        positive_edge_lanes,
        negative_edge_lanes,
        positive_carry_edge_lanes,
        negative_carry_edge_lanes,

        opponent_neutral_or_better_lanes,
        opponent_neutral_or_better_carry_lanes,

        total_lane_edge_tier,
        carry_lane_edge_tier
    FROM dbo.vw_lol_matchup_lane_edge_summary_v1
),
scored AS (
    SELECT
        *,

        CASE
            WHEN total_lane_edge >= 25 THEN 'Lane Favorite'
            WHEN total_lane_edge <= -25 THEN 'Lane Underdog'
            WHEN total_lane_edge >= 10 THEN 'Small Lane Favorite'
            WHEN total_lane_edge <= -10 THEN 'Small Lane Underdog'
            ELSE 'Lane Neutral'
        END AS lane_favorite_status,

        CASE
            WHEN opponent_neutral_or_better_carry_lanes >= 3 THEN 3
            WHEN opponent_neutral_or_better_carry_lanes = 2 THEN 2
            WHEN opponent_neutral_or_better_carry_lanes = 1 THEN 1
            ELSE 0
        END AS opponent_carry_resistance_level,

        CASE
            WHEN opponent_neutral_or_better_lanes >= 4 THEN 3
            WHEN opponent_neutral_or_better_lanes = 3 THEN 2
            WHEN opponent_neutral_or_better_lanes = 2 THEN 1
            ELSE 0
        END AS opponent_overall_resistance_level,

        CASE
            WHEN carry_lane_edge <= -15 THEN 3
            WHEN carry_lane_edge <= -5 THEN 2
            WHEN carry_lane_edge < 5 THEN 1
            ELSE 0
        END AS carry_lane_risk_level,

        CASE
            WHEN negative_carry_edge_lanes >= 3 THEN 3
            WHEN negative_carry_edge_lanes = 2 THEN 2
            WHEN negative_carry_edge_lanes = 1 THEN 1
            ELSE 0
        END AS negative_carry_lane_count_level
    FROM base
),
final_scored AS (
    SELECT
        *,

        (
            opponent_carry_resistance_level * 2
            + opponent_overall_resistance_level
            + carry_lane_risk_level * 2
            + negative_carry_lane_count_level
        ) AS upset_resistance_score,

        CASE
            WHEN total_lane_edge >= 25
             AND carry_lane_edge >= 15
             AND opponent_neutral_or_better_carry_lanes <= 1
             AND negative_carry_edge_lanes = 0
                THEN 'Favorite Stomp Support'

            WHEN total_lane_edge >= 25
             AND opponent_neutral_or_better_carry_lanes >= 2
                THEN 'Favorite Stomp Warning'

            WHEN total_lane_edge >= 10
             AND carry_lane_edge < 5
                THEN 'Favorite Carry-Lane Warning'

            WHEN total_lane_edge <= -25
             AND opponent_neutral_or_better_carry_lanes >= 2
                THEN 'Underdog Resistance'

            WHEN total_lane_edge <= -10
             AND carry_lane_edge >= -5
                THEN 'Underdog Live'

            WHEN ABS(total_lane_edge) < 10
             AND ABS(carry_lane_edge) < 5
                THEN 'Neutral / Thin Signal'

            ELSE 'Standard Lane Signal'
        END AS upset_signal_label,

        CASE
            WHEN (
                opponent_carry_resistance_level * 2
                + opponent_overall_resistance_level
                + carry_lane_risk_level * 2
                + negative_carry_lane_count_level
            ) >= 8 THEN 'High Resistance'
            
            WHEN (
                opponent_carry_resistance_level * 2
                + opponent_overall_resistance_level
                + carry_lane_risk_level * 2
                + negative_carry_lane_count_level
            ) >= 5 THEN 'Medium Resistance'

            WHEN (
                opponent_carry_resistance_level * 2
                + opponent_overall_resistance_level
                + carry_lane_risk_level * 2
                + negative_carry_lane_count_level
            ) >= 2 THEN 'Low Resistance'

            ELSE 'Minimal Resistance'
        END AS upset_resistance_tier,

        CASE
            WHEN total_lane_edge >= 25
             AND opponent_neutral_or_better_carry_lanes >= 2
                THEN 1

            WHEN total_lane_edge >= 10
             AND carry_lane_edge < 5
                THEN 1

            ELSE 0
        END AS favorite_stomp_warning_flag,

        CASE
            WHEN total_lane_edge <= -25
             AND opponent_neutral_or_better_carry_lanes >= 2
                THEN 1

            WHEN total_lane_edge <= -10
             AND carry_lane_edge >= -5
                THEN 1

            ELSE 0
        END AS underdog_live_flag,

        CASE
            WHEN total_lane_edge >= 25
             AND carry_lane_edge >= 15
             AND opponent_neutral_or_better_carry_lanes <= 1
             AND negative_carry_edge_lanes = 0
                THEN 1
            ELSE 0
        END AS favorite_stomp_support_flag
    FROM scored
)
SELECT
    model_version,
    game_id,
    game_date,
    league,
    season,
    split,
    team,
    opponent,

    top_lane_edge,
    jng_lane_edge,
    mid_lane_edge,
    adc_lane_edge,
    sup_lane_edge,

    total_lane_edge,
    carry_lane_edge,
    main_carry_lane_edge,
    secondary_lane_edge,

    clear_edge_lanes,
    clear_disadvantage_lanes,
    positive_edge_lanes,
    negative_edge_lanes,
    positive_carry_edge_lanes,
    negative_carry_edge_lanes,

    opponent_neutral_or_better_lanes,
    opponent_neutral_or_better_carry_lanes,

    total_lane_edge_tier,
    carry_lane_edge_tier,

    lane_favorite_status,

    upset_resistance_score,
    upset_resistance_tier,
    upset_signal_label,

    favorite_stomp_warning_flag,
    underdog_live_flag,
    favorite_stomp_support_flag
FROM final_scored;
GO