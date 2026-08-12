USE lol_esports;
GO

CREATE OR ALTER VIEW dbo.vw_lol_matchup_lane_edge_summary_v1 AS
WITH lane_edges AS (
    SELECT
        model_version,
        game_id,
        game_date,
        league,
        season,
        split,
        team,
        opponent,
        lane,
        lane_power_edge,
        lane_power_tier,
        opponent_lane_power_tier,
        lane_edge_tier
    FROM dbo.vw_lol_matchup_lane_edges_v1
),
summary AS (
    SELECT
        model_version,
        game_id,
        game_date,
        league,
        season,
        split,
        team,
        opponent,

        MAX(CASE WHEN lane = 'TOP' THEN lane_power_edge END) AS top_lane_edge,
        MAX(CASE WHEN lane = 'JNG' THEN lane_power_edge END) AS jng_lane_edge,
        MAX(CASE WHEN lane = 'MID' THEN lane_power_edge END) AS mid_lane_edge,
        MAX(CASE WHEN lane = 'ADC' THEN lane_power_edge END) AS adc_lane_edge,
        MAX(CASE WHEN lane = 'SUP' THEN lane_power_edge END) AS sup_lane_edge,

        SUM(lane_power_edge) AS total_lane_edge,

        SUM(CASE 
                WHEN lane IN ('JNG', 'MID', 'ADC') 
                THEN lane_power_edge 
                ELSE 0 
            END) AS carry_lane_edge,

        SUM(CASE 
                WHEN lane IN ('MID', 'ADC') 
                THEN lane_power_edge 
                ELSE 0 
            END) AS main_carry_lane_edge,

        SUM(CASE 
                WHEN lane IN ('TOP', 'SUP') 
                THEN lane_power_edge 
                ELSE 0 
            END) AS secondary_lane_edge,

        SUM(CASE WHEN lane_power_edge >= 10 THEN 1 ELSE 0 END) AS clear_edge_lanes,
        SUM(CASE WHEN lane_power_edge <= -10 THEN 1 ELSE 0 END) AS clear_disadvantage_lanes,

        SUM(CASE WHEN lane_power_edge >= 3 THEN 1 ELSE 0 END) AS positive_edge_lanes,
        SUM(CASE WHEN lane_power_edge <= -3 THEN 1 ELSE 0 END) AS negative_edge_lanes,

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
            END) AS opponent_neutral_or_better_carry_lanes
    FROM lane_edges
    GROUP BY
        model_version,
        game_id,
        game_date,
        league,
        season,
        split,
        team,
        opponent
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

    ROUND(top_lane_edge, 4) AS top_lane_edge,
    ROUND(jng_lane_edge, 4) AS jng_lane_edge,
    ROUND(mid_lane_edge, 4) AS mid_lane_edge,
    ROUND(adc_lane_edge, 4) AS adc_lane_edge,
    ROUND(sup_lane_edge, 4) AS sup_lane_edge,

    ROUND(total_lane_edge, 4) AS total_lane_edge,
    ROUND(carry_lane_edge, 4) AS carry_lane_edge,
    ROUND(main_carry_lane_edge, 4) AS main_carry_lane_edge,
    ROUND(secondary_lane_edge, 4) AS secondary_lane_edge,

    clear_edge_lanes,
    clear_disadvantage_lanes,
    positive_edge_lanes,
    negative_edge_lanes,
    positive_carry_edge_lanes,
    negative_carry_edge_lanes,

    opponent_neutral_or_better_lanes,
    opponent_neutral_or_better_carry_lanes,

    CASE
        WHEN total_lane_edge >= 50 THEN 'Massive Overall Lane Edge'
        WHEN total_lane_edge >= 25 THEN 'Strong Overall Lane Edge'
        WHEN total_lane_edge >= 10 THEN 'Moderate Overall Lane Edge'
        WHEN total_lane_edge > -10 THEN 'Mostly Even Overall'
        WHEN total_lane_edge > -25 THEN 'Moderate Overall Lane Disadvantage'
        WHEN total_lane_edge > -50 THEN 'Strong Overall Lane Disadvantage'
        ELSE 'Massive Overall Lane Disadvantage'
    END AS total_lane_edge_tier,

    CASE
        WHEN carry_lane_edge >= 30 THEN 'Massive Carry Lane Edge'
        WHEN carry_lane_edge >= 15 THEN 'Strong Carry Lane Edge'
        WHEN carry_lane_edge >= 5 THEN 'Moderate Carry Lane Edge'
        WHEN carry_lane_edge > -5 THEN 'Mostly Even Carry Lanes'
        WHEN carry_lane_edge > -15 THEN 'Moderate Carry Lane Disadvantage'
        WHEN carry_lane_edge > -30 THEN 'Strong Carry Lane Disadvantage'
        ELSE 'Massive Carry Lane Disadvantage'
    END AS carry_lane_edge_tier
FROM summary;
GO