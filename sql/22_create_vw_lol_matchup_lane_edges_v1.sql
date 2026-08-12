USE lol_esports;
GO

CREATE OR ALTER VIEW dbo.vw_lol_matchup_lane_edges_v1 AS
WITH game_players AS (
    SELECT
        f.game_id,
        f.game_date,
        f.league,
        f.season,
        f.split,
        f.team_name AS team,
        f.player_name,
        f.player_id,
        CASE 
            WHEN LOWER(f.position) IN ('bot', 'adc') THEN 'ADC'
            WHEN LOWER(f.position) IN ('jng', 'jun', 'jungle') THEN 'JNG'
            ELSE UPPER(f.position)
        END AS lane
    FROM dbo.fact_lol_player_game f
    WHERE f.league IN ('LPL', 'LCK')
      AND f.season = 2026
      AND f.team_name IS NOT NULL
      AND f.player_name IS NOT NULL
      AND f.position IS NOT NULL
      AND LOWER(f.position) IN ('top', 'jng', 'jun', 'jungle', 'mid', 'bot', 'adc', 'sup')
),
team_lanes AS (
    SELECT
        gp.game_id,
        gp.game_date,
        gp.league,
        gp.season,
        gp.split,
        gp.team,
        gp.lane,
        gp.player_name,
        gp.player_id,

        r.games_played,
        r.lane_power_score,
        r.lane_power_rank,
        r.lane_power_tier,
        r.avg_dk_points,
        r.kills_per_game,
        r.deaths_per_game,
        r.assists_per_game,
        r.dpm,
        r.avg_damage_share,
        r.avg_gold_diff_10,
        r.avg_xp_diff_10,
        r.avg_cs_diff_10
    FROM game_players gp
    INNER JOIN dbo.vw_lol_player_lane_power_rating_v1 r
        ON gp.league = r.league
       AND gp.lane = r.lane
       AND gp.team = r.team
       AND gp.player_name = r.player_name
),
lane_edges AS (
    SELECT
        tl.game_id,
        tl.game_date,
        tl.league,
        tl.season,
        tl.split,
        tl.team,
        ol.team AS opponent,
        tl.lane,

        tl.player_name,
        tl.player_id,
        tl.games_played,
        tl.lane_power_score,
        tl.lane_power_rank,
        tl.lane_power_tier,

        ol.player_name AS opponent_player_name,
        ol.player_id AS opponent_player_id,
        ol.games_played AS opponent_games_played,
        ol.lane_power_score AS opponent_lane_power_score,
        ol.lane_power_rank AS opponent_lane_power_rank,
        ol.lane_power_tier AS opponent_lane_power_tier,

        tl.avg_dk_points,
        ol.avg_dk_points AS opponent_avg_dk_points,

        tl.kills_per_game,
        ol.kills_per_game AS opponent_kills_per_game,

        tl.deaths_per_game,
        ol.deaths_per_game AS opponent_deaths_per_game,

        tl.assists_per_game,
        ol.assists_per_game AS opponent_assists_per_game,

        tl.dpm,
        ol.dpm AS opponent_dpm,

        tl.avg_damage_share,
        ol.avg_damage_share AS opponent_avg_damage_share,

        tl.avg_gold_diff_10,
        ol.avg_gold_diff_10 AS opponent_avg_gold_diff_10,

        tl.avg_xp_diff_10,
        ol.avg_xp_diff_10 AS opponent_avg_xp_diff_10,

        tl.avg_cs_diff_10,
        ol.avg_cs_diff_10 AS opponent_avg_cs_diff_10,

        tl.lane_power_score - ol.lane_power_score AS lane_power_edge,

        tl.avg_dk_points - ol.avg_dk_points AS avg_dk_points_edge,
        tl.kills_per_game - ol.kills_per_game AS kills_per_game_edge,
        tl.assists_per_game - ol.assists_per_game AS assists_per_game_edge,
        tl.dpm - ol.dpm AS dpm_edge,
        tl.avg_damage_share - ol.avg_damage_share AS damage_share_edge,
        tl.avg_gold_diff_10 - ol.avg_gold_diff_10 AS gold_diff_10_edge,
        tl.avg_xp_diff_10 - ol.avg_xp_diff_10 AS xp_diff_10_edge,
        tl.avg_cs_diff_10 - ol.avg_cs_diff_10 AS cs_diff_10_edge
    FROM team_lanes tl
    INNER JOIN team_lanes ol
        ON tl.game_id = ol.game_id
       AND tl.league = ol.league
       AND tl.lane = ol.lane
       AND tl.team <> ol.team
)
SELECT
    'lane_power_v1' AS model_version,
    game_id,
    game_date,
    league,
    season,
    split,
    team,
    opponent,
    lane,

    player_name,
    player_id,
    games_played,
    ROUND(lane_power_score, 4) AS lane_power_score,
    lane_power_rank,
    lane_power_tier,

    opponent_player_name,
    opponent_player_id,
    opponent_games_played,
    ROUND(opponent_lane_power_score, 4) AS opponent_lane_power_score,
    opponent_lane_power_rank,
    opponent_lane_power_tier,

    ROUND(lane_power_edge, 4) AS lane_power_edge,

    CASE
        WHEN lane_power_edge >= 20 THEN 'Major Edge'
        WHEN lane_power_edge >= 10 THEN 'Clear Edge'
        WHEN lane_power_edge >= 3 THEN 'Small Edge'
        WHEN lane_power_edge > -3 THEN 'Even'
        WHEN lane_power_edge > -10 THEN 'Small Disadvantage'
        WHEN lane_power_edge > -20 THEN 'Clear Disadvantage'
        ELSE 'Major Disadvantage'
    END AS lane_edge_tier,

    ROUND(avg_dk_points, 4) AS avg_dk_points,
    ROUND(opponent_avg_dk_points, 4) AS opponent_avg_dk_points,
    ROUND(avg_dk_points_edge, 4) AS avg_dk_points_edge,

    ROUND(kills_per_game, 4) AS kills_per_game,
    ROUND(opponent_kills_per_game, 4) AS opponent_kills_per_game,
    ROUND(kills_per_game_edge, 4) AS kills_per_game_edge,

    ROUND(assists_per_game, 4) AS assists_per_game,
    ROUND(opponent_assists_per_game, 4) AS opponent_assists_per_game,
    ROUND(assists_per_game_edge, 4) AS assists_per_game_edge,

    ROUND(dpm, 4) AS dpm,
    ROUND(opponent_dpm, 4) AS opponent_dpm,
    ROUND(dpm_edge, 4) AS dpm_edge,

    ROUND(avg_damage_share, 4) AS avg_damage_share,
    ROUND(opponent_avg_damage_share, 4) AS opponent_avg_damage_share,
    ROUND(damage_share_edge, 4) AS damage_share_edge,

    ROUND(avg_gold_diff_10, 4) AS avg_gold_diff_10,
    ROUND(opponent_avg_gold_diff_10, 4) AS opponent_avg_gold_diff_10,
    ROUND(gold_diff_10_edge, 4) AS gold_diff_10_edge,

    ROUND(avg_xp_diff_10, 4) AS avg_xp_diff_10,
    ROUND(opponent_avg_xp_diff_10, 4) AS opponent_avg_xp_diff_10,
    ROUND(xp_diff_10_edge, 4) AS xp_diff_10_edge,

    ROUND(avg_cs_diff_10, 4) AS avg_cs_diff_10,
    ROUND(opponent_avg_cs_diff_10, 4) AS opponent_avg_cs_diff_10,
    ROUND(cs_diff_10_edge, 4) AS cs_diff_10_edge
FROM lane_edges;
GO