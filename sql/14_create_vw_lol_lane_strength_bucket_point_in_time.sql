/* ============================================================
   LoL Lane Strength Bucket - Point In Time

   Purpose:
     Calculate each team's lane strength as of BEFORE each
     historical series date.

   This avoids future-data leakage when backtesting.

   Source:
     dbo.lol_team_series_results
     dbo.fact_lol_player_game

   Grain:
     one row per target series / team / position

   Positions:
     TOP, JNG, MID, BOT, SUP

   Strength logic:
     - Compare team lane avg DK before the series
       against league-position avg DK before the series.
     - strong  = lane_dk_index >= 1.05
     - weak    = lane_dk_index <= 0.95
     - neutral = between
     - fewer than 5 lane games = neutral
   ============================================================ */

IF OBJECT_ID('dbo.vw_lol_lane_strength_bucket_point_in_time', 'V') IS NOT NULL
BEGIN
    DROP VIEW dbo.vw_lol_lane_strength_bucket_point_in_time;
END;
GO

CREATE VIEW dbo.vw_lol_lane_strength_bucket_point_in_time AS

WITH target_series AS
(
    SELECT
        r.series_id AS target_series_id,
        r.league,
        r.[year] AS season,
        r.series_start_date AS target_series_date,
        r.teamname,
        r.opponent AS opponent_teamname,
        r.series_result AS actual_series_result,
        CAST(r.is_series_win AS INT) AS actual_won_series,
        r.wins AS actual_game_wins,
        r.losses AS actual_game_losses
    FROM dbo.lol_team_series_results r
    WHERE r.league IN ('LPL', 'LCK')
      AND r.[year] = 2026
      AND r.series_result IN ('2-0', '2-1', '1-2', '0-2')
      AND r.teamname IS NOT NULL
      AND r.opponent IS NOT NULL
      AND r.series_start_date IS NOT NULL
),

player_games_clean AS
(
    SELECT
        game_id,
        league,
        season,
        CAST(game_date AS DATE) AS game_date,
        team_name AS teamname,
        player_name AS playername,

        CASE
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('top') THEN 'TOP'
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('jng', 'jungle') THEN 'JNG'
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('mid') THEN 'MID'
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('bot', 'adc') THEN 'BOT'
            WHEN LOWER(LTRIM(RTRIM(position))) IN ('sup', 'support') THEN 'SUP'
            ELSE UPPER(LTRIM(RTRIM(position)))
        END AS position,

        CAST(ISNULL(dk_points, 0) AS FLOAT) AS dk_points,
        CAST(ISNULL(kills, 0) AS FLOAT) AS kills,
        CAST(ISNULL(deaths, 0) AS FLOAT) AS deaths,
        CAST(ISNULL(assists, 0) AS FLOAT) AS assists,
        CAST(ISNULL(dpm, 0) AS FLOAT) AS dpm,
        CAST(ISNULL(damage_share, 0) AS FLOAT) AS damage_share,
        CAST(ISNULL(vision_score, 0) AS FLOAT) AS vision_score,
        CAST(ISNULL(gold_diff_10, 0) AS FLOAT) AS gold_diff_10,
        CAST(ISNULL(xp_diff_10, 0) AS FLOAT) AS xp_diff_10,
        CAST(ISNULL(cs_diff_10, 0) AS FLOAT) AS cs_diff_10
    FROM dbo.fact_lol_player_game
    WHERE league IN ('LPL', 'LCK')
      AND season = 2026
      AND game_date IS NOT NULL
      AND team_name IS NOT NULL
      AND player_name IS NOT NULL
      AND position IS NOT NULL
),

team_lane_before_series AS
(
    SELECT
        t.target_series_id,
        t.league,
        t.season,
        t.target_series_date,
        t.teamname,
        t.opponent_teamname,
        t.actual_series_result,
        t.actual_won_series,
        t.actual_game_wins,
        t.actual_game_losses,

        pg.position,

        COUNT(*) AS lane_games,
        COUNT(DISTINCT pg.playername) AS lane_players_used,

        AVG(pg.dk_points) AS lane_avg_dk,
        AVG(pg.kills) AS lane_avg_kills,
        AVG(pg.deaths) AS lane_avg_deaths,
        AVG(pg.assists) AS lane_avg_assists,
        AVG(pg.dpm) AS lane_avg_dpm,
        AVG(pg.damage_share) AS lane_avg_damage_share,
        AVG(pg.vision_score) AS lane_avg_vision_score,
        AVG(pg.gold_diff_10) AS lane_avg_gold_diff_10,
        AVG(pg.xp_diff_10) AS lane_avg_xp_diff_10,
        AVG(pg.cs_diff_10) AS lane_avg_cs_diff_10,

        MIN(pg.game_date) AS first_prior_game_date,
        MAX(pg.game_date) AS last_prior_game_date
    FROM target_series t
    LEFT JOIN player_games_clean pg
        ON t.league = pg.league
        AND t.season = pg.season
        AND LOWER(LTRIM(RTRIM(t.teamname))) = LOWER(LTRIM(RTRIM(pg.teamname)))
        AND pg.game_date < t.target_series_date
        AND pg.position IN ('TOP', 'JNG', 'MID', 'BOT', 'SUP')
    GROUP BY
        t.target_series_id,
        t.league,
        t.season,
        t.target_series_date,
        t.teamname,
        t.opponent_teamname,
        t.actual_series_result,
        t.actual_won_series,
        t.actual_game_wins,
        t.actual_game_losses,
        pg.position
),

league_position_before_series AS
(
    SELECT
        t.target_series_id,
        t.league,
        t.season,
        t.target_series_date,
        pg.position,

        COUNT(*) AS league_position_games,
        AVG(pg.dk_points) AS league_position_avg_dk,
        AVG(pg.kills) AS league_position_avg_kills,
        AVG(pg.deaths) AS league_position_avg_deaths,
        AVG(pg.assists) AS league_position_avg_assists,
        AVG(pg.dpm) AS league_position_avg_dpm,
        AVG(pg.damage_share) AS league_position_avg_damage_share,
        AVG(pg.vision_score) AS league_position_avg_vision_score
    FROM target_series t
    LEFT JOIN player_games_clean pg
        ON t.league = pg.league
        AND t.season = pg.season
        AND pg.game_date < t.target_series_date
        AND pg.position IN ('TOP', 'JNG', 'MID', 'BOT', 'SUP')
    GROUP BY
        t.target_series_id,
        t.league,
        t.season,
        t.target_series_date,
        pg.position
),

joined AS
(
    SELECT
        tl.target_series_id,
        tl.league,
        tl.season,
        tl.target_series_date,
        tl.teamname,
        tl.opponent_teamname,
        tl.actual_series_result,
        tl.actual_won_series,
        tl.actual_game_wins,
        tl.actual_game_losses,

        tl.position,

        ISNULL(tl.lane_games, 0) AS lane_games,
        ISNULL(tl.lane_players_used, 0) AS lane_players_used,

        tl.first_prior_game_date,
        tl.last_prior_game_date,

        tl.lane_avg_dk,
        tl.lane_avg_kills,
        tl.lane_avg_deaths,
        tl.lane_avg_assists,
        tl.lane_avg_dpm,
        tl.lane_avg_damage_share,
        tl.lane_avg_vision_score,
        tl.lane_avg_gold_diff_10,
        tl.lane_avg_xp_diff_10,
        tl.lane_avg_cs_diff_10,

        lp.league_position_games,
        lp.league_position_avg_dk,
        lp.league_position_avg_kills,
        lp.league_position_avg_deaths,
        lp.league_position_avg_assists,
        lp.league_position_avg_dpm,
        lp.league_position_avg_damage_share,
        lp.league_position_avg_vision_score,

        CASE
            WHEN lp.league_position_avg_dk IS NULL OR lp.league_position_avg_dk = 0 THEN NULL
            ELSE tl.lane_avg_dk / lp.league_position_avg_dk
        END AS lane_dk_index,

        CASE
            WHEN lp.league_position_avg_kills IS NULL OR lp.league_position_avg_kills = 0 THEN NULL
            ELSE tl.lane_avg_kills / lp.league_position_avg_kills
        END AS lane_kill_index,

        CASE
            WHEN lp.league_position_avg_assists IS NULL OR lp.league_position_avg_assists = 0 THEN NULL
            ELSE tl.lane_avg_assists / lp.league_position_avg_assists
        END AS lane_assist_index,

        CASE
            WHEN lp.league_position_avg_dpm IS NULL OR lp.league_position_avg_dpm = 0 THEN NULL
            ELSE tl.lane_avg_dpm / lp.league_position_avg_dpm
        END AS lane_dpm_index,

        CASE
            WHEN lp.league_position_avg_vision_score IS NULL OR lp.league_position_avg_vision_score = 0 THEN NULL
            ELSE tl.lane_avg_vision_score / lp.league_position_avg_vision_score
        END AS lane_vision_index
    FROM team_lane_before_series tl
    LEFT JOIN league_position_before_series lp
        ON tl.target_series_id = lp.target_series_id
        AND tl.league = lp.league
        AND tl.season = lp.season
        AND tl.position = lp.position
)

SELECT
    target_series_id,
    league,
    season,
    target_series_date,
    teamname,
    opponent_teamname,

    actual_series_result,
    actual_won_series,
    actual_game_wins,
    actual_game_losses,

    position,

    lane_games,
    lane_players_used,

    first_prior_game_date,
    last_prior_game_date,

    lane_avg_dk,
    league_position_avg_dk,
    lane_dk_index,

    lane_avg_kills,
    league_position_avg_kills,
    lane_kill_index,

    lane_avg_deaths,
    league_position_avg_deaths,

    lane_avg_assists,
    league_position_avg_assists,
    lane_assist_index,

    lane_avg_dpm,
    league_position_avg_dpm,
    lane_dpm_index,

    lane_avg_damage_share,
    league_position_avg_damage_share,

    lane_avg_vision_score,
    league_position_avg_vision_score,
    lane_vision_index,

    lane_avg_gold_diff_10,
    lane_avg_xp_diff_10,
    lane_avg_cs_diff_10,

    league_position_games,

    CASE
        WHEN position IS NULL THEN 'unknown'
        WHEN ISNULL(lane_games, 0) < 5 THEN 'neutral'
        WHEN lane_dk_index >= 1.05 THEN 'strong'
        WHEN lane_dk_index <= 0.95 THEN 'weak'
        ELSE 'neutral'
    END AS lane_strength_bucket_point_in_time,

    CASE
        WHEN position IS NULL THEN 'no_prior_data'
        WHEN ISNULL(lane_games, 0) < 5 THEN 'low_sample'
        WHEN ISNULL(lane_games, 0) BETWEEN 5 AND 9 THEN 'medium_sample'
        ELSE 'solid_sample'
    END AS lane_strength_sample_label_point_in_time
FROM joined
WHERE position IS NOT NULL;
GO