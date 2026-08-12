USE lol_esports;
GO

CREATE OR ALTER VIEW dbo.vw_lol_player_lane_power_rating_pit_v1 AS
WITH target_dates AS (
    SELECT DISTINCT
        league,
        season,
        target_series_date
    FROM dbo.vw_lol_bayes_strength_matchups_point_in_time
    WHERE league IN ('LPL', 'LCK')
      AND season = 2026
),
prior_games AS (
    SELECT
        td.league,
        td.season,
        td.target_series_date,

        f.team_name AS team,
        f.player_name,
        f.player_id,

        CASE 
            WHEN LOWER(f.position) IN ('bot', 'adc') THEN 'ADC'
            WHEN LOWER(f.position) IN ('jng', 'jun', 'jungle') THEN 'JNG'
            ELSE UPPER(f.position)
        END AS lane,

        TRY_CONVERT(float, f.result) AS result,
        TRY_CONVERT(float, f.kills) AS kills,
        TRY_CONVERT(float, f.deaths) AS deaths,
        TRY_CONVERT(float, f.assists) AS assists,
        TRY_CONVERT(float, f.cspm) AS cspm,
        TRY_CONVERT(float, f.dpm) AS dpm,
        TRY_CONVERT(float, f.damage_share) AS damage_share,
        TRY_CONVERT(float, f.total_gold) AS total_gold,
        TRY_CONVERT(float, f.earned_gold) AS earned_gold,
        TRY_CONVERT(float, f.gold_diff_10) AS gold_diff_10,
        TRY_CONVERT(float, f.xp_diff_10) AS xp_diff_10,
        TRY_CONVERT(float, f.cs_diff_10) AS cs_diff_10,
        TRY_CONVERT(float, f.vision_score) AS vision_score,
        TRY_CONVERT(float, f.wards_placed) AS wards_placed,
        TRY_CONVERT(float, f.wards_killed) AS wards_killed,
        TRY_CONVERT(float, f.first_blood) AS first_blood,
        TRY_CONVERT(float, f.dk_points) AS dk_points
    FROM target_dates td
    INNER JOIN dbo.fact_lol_player_game f
        ON f.league = td.league
       AND f.season = td.season
       AND f.game_date < td.target_series_date
    WHERE f.league IN ('LPL', 'LCK')
      AND f.season = 2026
      AND f.team_name IS NOT NULL
      AND f.player_name IS NOT NULL
      AND f.position IS NOT NULL
      AND LOWER(f.position) IN ('top', 'jng', 'jun', 'jungle', 'mid', 'bot', 'adc', 'sup')
),
agg AS (
    SELECT
        league,
        season,
        target_series_date,
        lane,
        team,
        player_name,
        player_id,

        COUNT(*) AS prior_games_played,

        AVG(result) AS prior_win_rate,
        AVG(dk_points) AS avg_dk_points,
        AVG(kills) AS kills_per_game,
        AVG(deaths) AS deaths_per_game,
        AVG(assists) AS assists_per_game,
        AVG(cspm) AS cs_per_min,
        AVG(dpm) AS dpm,
        AVG(damage_share) AS avg_damage_share,
        AVG(total_gold) AS avg_total_gold,
        AVG(earned_gold) AS avg_earned_gold,
        AVG(gold_diff_10) AS avg_gold_diff_10,
        AVG(xp_diff_10) AS avg_xp_diff_10,
        AVG(cs_diff_10) AS avg_cs_diff_10,
        AVG(vision_score) AS avg_vision_score,
        AVG(wards_placed) AS wards_placed_per_game,
        AVG(wards_killed) AS wards_killed_per_game,
        AVG(first_blood) AS first_blood_rate,

        AVG(kills + assists) AS kill_assist_per_game,

        AVG(
            CASE
                WHEN deaths IS NULL THEN NULL
                WHEN deaths = 0 THEN kills + assists
                ELSE (kills + assists) / NULLIF(deaths, 0)
            END
        ) AS kda_proxy
    FROM prior_games
    GROUP BY
        league,
        season,
        target_series_date,
        lane,
        team,
        player_name,
        player_id
    HAVING COUNT(*) >= 3
),
rank_base AS (
    SELECT
        *,

        PERCENT_RANK() OVER (
            PARTITION BY league, season, target_series_date, lane
            ORDER BY avg_dk_points
        ) AS dk_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, season, target_series_date, lane
            ORDER BY kills_per_game
        ) AS kill_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, season, target_series_date, lane
            ORDER BY assists_per_game
        ) AS assist_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, season, target_series_date, lane
            ORDER BY cs_per_min
        ) AS cs_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, season, target_series_date, lane
            ORDER BY dpm
        ) AS dpm_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, season, target_series_date, lane
            ORDER BY avg_damage_share
        ) AS damage_share_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, season, target_series_date, lane
            ORDER BY avg_gold_diff_10
        ) AS gold10_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, season, target_series_date, lane
            ORDER BY avg_xp_diff_10
        ) AS xp10_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, season, target_series_date, lane
            ORDER BY avg_vision_score
        ) AS vision_score_rank,

        PERCENT_RANK() OVER (
            PARTITION BY league, season, target_series_date, lane
            ORDER BY wards_placed_per_game
        ) AS wards_placed_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, season, target_series_date, lane
            ORDER BY wards_killed_per_game
        ) AS wards_killed_score,

        PERCENT_RANK() OVER (
            PARTITION BY league, season, target_series_date, lane
            ORDER BY first_blood_rate
        ) AS first_blood_score,

        -- Lower deaths are better.
        PERCENT_RANK() OVER (
            PARTITION BY league, season, target_series_date, lane
            ORDER BY deaths_per_game DESC
        ) AS death_control_score
    FROM agg
),
scored AS (
    SELECT
        'lane_power_pit_v1' AS model_version,

        league,
        season,
        target_series_date,
        lane,
        team,
        player_name,
        player_id,
        prior_games_played,

        prior_win_rate,
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
    FROM rank_base
),
ranked AS (
    SELECT
        *,
        RANK() OVER (
            PARTITION BY league, season, target_series_date, lane
            ORDER BY lane_power_score DESC
        ) AS lane_power_rank,

        COUNT(*) OVER (
            PARTITION BY league, season, target_series_date, lane
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