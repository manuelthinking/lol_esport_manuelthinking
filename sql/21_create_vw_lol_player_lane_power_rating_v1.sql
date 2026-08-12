USE lol_esports;
GO

CREATE OR ALTER VIEW dbo.vw_lol_player_lane_power_rating_v1 AS
WITH base AS (
    SELECT
        *,

        PERCENT_RANK() OVER (
            PARTITION BY league, lane 
            ORDER BY avg_dk_points
        ) AS dk_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, lane 
            ORDER BY kills_per_game
        ) AS kill_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, lane 
            ORDER BY assists_per_game
        ) AS assist_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, lane 
            ORDER BY cs_per_min
        ) AS cs_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, lane 
            ORDER BY dpm
        ) AS dpm_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, lane 
            ORDER BY avg_damage_share
        ) AS damage_share_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, lane 
            ORDER BY avg_gold_diff_10
        ) AS gold10_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, lane 
            ORDER BY avg_xp_diff_10
        ) AS xp10_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, lane 
            ORDER BY avg_cs_diff_10
        ) AS cs10_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, lane 
            ORDER BY avg_vision_score
        ) AS vision_score_rank,

        PERCENT_RANK() OVER (
            PARTITION BY league, lane 
            ORDER BY wards_placed_per_game
        ) AS wards_placed_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, lane 
            ORDER BY wards_killed_per_game
        ) AS wards_killed_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, lane 
            ORDER BY first_blood_rate
        ) AS first_blood_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, lane 
            ORDER BY win_rate
        ) AS win_rate_score,

        -- Lower deaths are better.
        PERCENT_RANK() OVER (
            PARTITION BY league, lane 
            ORDER BY deaths_per_game DESC
        ) AS death_control_score
    FROM dbo.vw_lol_player_lane_power_base_v1
),
scored AS (
    SELECT
        model_version,
        league,
        lane,
        team,
        player_name,
        player_id,
        games_played,

        win_rate,
        avg_dk_points,
        kills_per_game,
        deaths_per_game,
        assists_per_game,
        cs_per_min,
        dpm,
        avg_damage_share,
        avg_total_gold,
        avg_earned_gold,
        avg_gold_diff_10,
        avg_xp_diff_10,
        avg_cs_diff_10,
        avg_vision_score,
        wards_placed_per_game,
        wards_killed_per_game,
        first_blood_rate,
        kill_assist_per_game,
        kda_proxy,

        CASE
            WHEN lane IN ('MID', 'ADC') THEN
                100.0 * (
                    0.25 * dk_score +
                    0.20 * dpm_score +
                    0.15 * damage_share_score +
                    0.12 * kill_score +
                    0.08 * assist_score +
                    0.08 * cs_score +
                    0.05 * gold10_score +
                    0.03 * xp10_score +
                    0.04 * death_control_score
                )

            WHEN lane = 'JNG' THEN
                100.0 * (
                    0.23 * dk_score +
                    0.18 * assist_score +
                    0.14 * kill_score +
                    0.12 * dpm_score +
                    0.10 * first_blood_score +
                    0.08 * gold10_score +
                    0.05 * xp10_score +
                    0.10 * death_control_score
                )

            WHEN lane = 'TOP' THEN
                100.0 * (
                    0.23 * dk_score +
                    0.18 * dpm_score +
                    0.15 * cs_score +
                    0.14 * gold10_score +
                    0.10 * xp10_score +
                    0.08 * damage_share_score +
                    0.04 * kill_score +
                    0.08 * death_control_score
                )

            WHEN lane = 'SUP' THEN
                100.0 * (
                    0.25 * dk_score +
                    0.25 * assist_score +
                    0.20 * vision_score_rank +
                    0.10 * death_control_score +
                    0.08 * wards_placed_score +
                    0.07 * wards_killed_score +
                    0.05 * dpm_score
                )

            ELSE
                100.0 * (
                    0.30 * dk_score +
                    0.20 * dpm_score +
                    0.15 * kill_score +
                    0.15 * assist_score +
                    0.10 * cs_score +
                    0.10 * death_control_score
                )
        END AS lane_power_score
    FROM base
),
ranked AS (
    SELECT
        *,
        RANK() OVER (
            PARTITION BY league, lane 
            ORDER BY lane_power_score DESC
        ) AS lane_power_rank,

        COUNT(*) OVER (
            PARTITION BY league, lane
        ) AS lane_player_pool_count
    FROM scored
)
SELECT
    *,
    CASE
        WHEN lane_power_score >= 85 THEN 'Elite'
        WHEN lane_power_score >= 70 THEN 'Strong'
        WHEN lane_power_score >= 50 THEN 'Neutral'
        WHEN lane_power_score >= 35 THEN 'Weak'
        ELSE 'Poor'
    END AS lane_power_tier
FROM ranked;
GO