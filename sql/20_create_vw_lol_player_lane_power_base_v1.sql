USE lol_esports;
GO

CREATE OR ALTER VIEW dbo.vw_lol_player_lane_power_base_v1 AS
WITH base AS (
    SELECT
        game_date,
        league,
        season,
        split,
        patch,
        side,

        team_name AS team,
        opponent_name AS opponent,

        player_name,
        player_id,

        CASE 
            WHEN LOWER(position) IN ('bot', 'adc') THEN 'ADC'
            WHEN LOWER(position) IN ('jng', 'jun', 'jungle') THEN 'JNG'
            ELSE UPPER(position)
        END AS lane,

        TRY_CONVERT(float, result) AS result,
        TRY_CONVERT(float, kills) AS kills,
        TRY_CONVERT(float, deaths) AS deaths,
        TRY_CONVERT(float, assists) AS assists,
        TRY_CONVERT(float, cs) AS cs,
        TRY_CONVERT(float, cspm) AS cspm,
        TRY_CONVERT(float, total_gold) AS total_gold,
        TRY_CONVERT(float, earned_gold) AS earned_gold,
        TRY_CONVERT(float, dmg_to_champs) AS dmg_to_champs,
        TRY_CONVERT(float, dpm) AS dpm,
        TRY_CONVERT(float, damage_share) AS damage_share,
        TRY_CONVERT(float, wards_placed) AS wards_placed,
        TRY_CONVERT(float, wards_killed) AS wards_killed,
        TRY_CONVERT(float, vision_score) AS vision_score,
        TRY_CONVERT(float, first_blood) AS first_blood,
        TRY_CONVERT(float, gold_diff_10) AS gold_diff_10,
        TRY_CONVERT(float, xp_diff_10) AS xp_diff_10,
        TRY_CONVERT(float, cs_diff_10) AS cs_diff_10,
        TRY_CONVERT(float, game_length_seconds) AS game_length_seconds,
        TRY_CONVERT(float, dk_points) AS dk_points
    FROM dbo.fact_lol_player_game
    WHERE league IN ('LPL', 'LCK')
      AND season = 2026
      AND position IS NOT NULL
      AND player_name IS NOT NULL
      AND team_name IS NOT NULL
),
agg AS (
    SELECT
        league,
        lane,
        team,
        player_name,
        player_id,

        COUNT(*) AS games_played,

        AVG(result) AS win_rate,

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
    FROM base
    WHERE lane IN ('TOP', 'JNG', 'MID', 'ADC', 'SUP')
    GROUP BY
        league,
        lane,
        team,
        player_name,
        player_id
)
SELECT
    'lane_power_v1' AS model_version,
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
    kda_proxy
FROM agg
WHERE games_played >= 3;
GO