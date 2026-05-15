/* ============================================================
   Populate dbo.lol_bayes_matchup_training

   Source:
     dbo.vw_lol_series_player_stats

   Target:
     dbo.lol_bayes_matchup_training
   ============================================================ */

SET NOCOUNT ON;

IF OBJECT_ID('dbo.vw_lol_series_player_stats', 'V') IS NULL
BEGIN
    RAISERROR('Missing source view: dbo.vw_lol_series_player_stats', 16, 1);
    RETURN;
END;

IF OBJECT_ID('dbo.lol_bayes_matchup_training', 'U') IS NULL
BEGIN
    RAISERROR('Missing target table: dbo.lol_bayes_matchup_training', 16, 1);
    RETURN;
END;

TRUNCATE TABLE dbo.lol_bayes_matchup_training;

WITH team_lane AS
(
    SELECT
        series_id,
        MIN(series_date) AS series_date,
        MAX(season) AS season,
        MAX(league) AS league,
        teamname,
        opponent_teamname,
        MAX(series_result) AS series_result,
        MAX(CAST(won_series AS INT)) AS won_series,
        MAX(games_played) AS games_played,

        SUM(CASE WHEN position = 'TOP' THEN kills END) AS top_kills,
        SUM(CASE WHEN position = 'JNG' THEN kills END) AS jng_kills,
        SUM(CASE WHEN position = 'MID' THEN kills END) AS mid_kills,
        SUM(CASE WHEN position = 'BOT' THEN kills END) AS bot_kills,
        SUM(CASE WHEN position = 'SUP' THEN kills END) AS sup_kills,

        SUM(CASE WHEN position = 'TOP' THEN assists END) AS top_assists,
        SUM(CASE WHEN position = 'JNG' THEN assists END) AS jng_assists,
        SUM(CASE WHEN position = 'MID' THEN assists END) AS mid_assists,
        SUM(CASE WHEN position = 'BOT' THEN assists END) AS bot_assists,
        SUM(CASE WHEN position = 'SUP' THEN assists END) AS sup_assists,

        SUM(CASE WHEN position = 'TOP' THEN deaths END) AS top_deaths,
        SUM(CASE WHEN position = 'JNG' THEN deaths END) AS jng_deaths,
        SUM(CASE WHEN position = 'MID' THEN deaths END) AS mid_deaths,
        SUM(CASE WHEN position = 'BOT' THEN deaths END) AS bot_deaths,
        SUM(CASE WHEN position = 'SUP' THEN deaths END) AS sup_deaths,

        SUM(CASE WHEN position = 'TOP' THEN dk_points END) AS top_dk,
        SUM(CASE WHEN position = 'JNG' THEN dk_points END) AS jng_dk,
        SUM(CASE WHEN position = 'MID' THEN dk_points END) AS mid_dk,
        SUM(CASE WHEN position = 'BOT' THEN dk_points END) AS bot_dk,
        SUM(CASE WHEN position = 'SUP' THEN dk_points END) AS sup_dk,

        SUM(kills) AS team_kills,
        SUM(assists) AS team_assists,
        SUM(deaths) AS team_deaths,
        SUM(dk_points) AS team_dk
    FROM dbo.vw_lol_series_player_stats
    WHERE league IN ('LPL', 'LCK')
      AND series_result IN ('2-0', '2-1', '1-2', '0-2')
      AND position IN ('TOP', 'JNG', 'MID', 'BOT', 'SUP')
    GROUP BY
        series_id,
        teamname,
        opponent_teamname
),

team_with_rating AS
(
    SELECT
        tl.*,
        AVG(CAST(r.rating_score AS FLOAT)) AS team_rating_score
    FROM team_lane tl
    LEFT JOIN dbo.lol_player_lane_ratings r
        ON LOWER(LTRIM(RTRIM(r.team_name))) = LOWER(LTRIM(RTRIM(tl.teamname)))
        AND r.season = tl.season
        AND LOWER(LTRIM(RTRIM(r.position))) IN ('top', 'jng', 'mid', 'bot', 'sup')
    GROUP BY
        tl.series_id,
        tl.series_date,
        tl.season,
        tl.league,
        tl.teamname,
        tl.opponent_teamname,
        tl.series_result,
        tl.won_series,
        tl.games_played,
        tl.top_kills,
        tl.jng_kills,
        tl.mid_kills,
        tl.bot_kills,
        tl.sup_kills,
        tl.top_assists,
        tl.jng_assists,
        tl.mid_assists,
        tl.bot_assists,
        tl.sup_assists,
        tl.top_deaths,
        tl.jng_deaths,
        tl.mid_deaths,
        tl.bot_deaths,
        tl.sup_deaths,
        tl.top_dk,
        tl.jng_dk,
        tl.mid_dk,
        tl.bot_dk,
        tl.sup_dk,
        tl.team_kills,
        tl.team_assists,
        tl.team_deaths,
        tl.team_dk
),

matched AS
(
    SELECT
        t.series_id,
        t.series_date,
        t.season,
        t.league,
        t.teamname,
        t.opponent_teamname,
        t.series_result,
        CAST(t.won_series AS BIT) AS won_series,
        t.games_played,

        t.top_kills AS team_top_kills,
        t.jng_kills AS team_jng_kills,
        t.mid_kills AS team_mid_kills,
        t.bot_kills AS team_bot_kills,
        t.sup_kills AS team_sup_kills,

        t.top_assists AS team_top_assists,
        t.jng_assists AS team_jng_assists,
        t.mid_assists AS team_mid_assists,
        t.bot_assists AS team_bot_assists,
        t.sup_assists AS team_sup_assists,

        t.top_deaths AS team_top_deaths,
        t.jng_deaths AS team_jng_deaths,
        t.mid_deaths AS team_mid_deaths,
        t.bot_deaths AS team_bot_deaths,
        t.sup_deaths AS team_sup_deaths,

        t.top_dk AS team_top_dk,
        t.jng_dk AS team_jng_dk,
        t.mid_dk AS team_mid_dk,
        t.bot_dk AS team_bot_dk,
        t.sup_dk AS team_sup_dk,

        o.top_kills AS opp_top_kills,
        o.jng_kills AS opp_jng_kills,
        o.mid_kills AS opp_mid_kills,
        o.bot_kills AS opp_bot_kills,
        o.sup_kills AS opp_sup_kills,

        o.top_assists AS opp_top_assists,
        o.jng_assists AS opp_jng_assists,
        o.mid_assists AS opp_mid_assists,
        o.bot_assists AS opp_bot_assists,
        o.sup_assists AS opp_sup_assists,

        o.top_deaths AS opp_top_deaths,
        o.jng_deaths AS opp_jng_deaths,
        o.mid_deaths AS opp_mid_deaths,
        o.bot_deaths AS opp_bot_deaths,
        o.sup_deaths AS opp_sup_deaths,

        o.top_dk AS opp_top_dk,
        o.jng_dk AS opp_jng_dk,
        o.mid_dk AS opp_mid_dk,
        o.bot_dk AS opp_bot_dk,
        o.sup_dk AS opp_sup_dk,

        t.top_kills - o.top_kills AS top_kill_edge,
        t.jng_kills - o.jng_kills AS jng_kill_edge,
        t.mid_kills - o.mid_kills AS mid_kill_edge,
        t.bot_kills - o.bot_kills AS bot_kill_edge,
        t.sup_kills - o.sup_kills AS sup_kill_edge,

        t.top_assists - o.top_assists AS top_assist_edge,
        t.jng_assists - o.jng_assists AS jng_assist_edge,
        t.mid_assists - o.mid_assists AS mid_assist_edge,
        t.bot_assists - o.bot_assists AS bot_assist_edge,
        t.sup_assists - o.sup_assists AS sup_assist_edge,

        t.top_deaths - o.top_deaths AS top_death_edge,
        t.jng_deaths - o.jng_deaths AS jng_death_edge,
        t.mid_deaths - o.mid_deaths AS mid_death_edge,
        t.bot_deaths - o.bot_deaths AS bot_death_edge,
        t.sup_deaths - o.sup_deaths AS sup_death_edge,

        t.top_dk - o.top_dk AS top_dk_edge,
        t.jng_dk - o.jng_dk AS jng_dk_edge,
        t.mid_dk - o.mid_dk AS mid_dk_edge,
        t.bot_dk - o.bot_dk AS bot_dk_edge,
        t.sup_dk - o.sup_dk AS sup_dk_edge,

        t.team_kills - o.team_kills AS team_kill_edge,
        t.team_assists - o.team_assists AS team_assist_edge,
        t.team_deaths - o.team_deaths AS team_death_edge,
        t.team_dk - o.team_dk AS team_dk_edge,

        t.team_rating_score,
        o.team_rating_score AS opp_rating_score,
        t.team_rating_score - o.team_rating_score AS team_rating_edge
    FROM team_with_rating t
    INNER JOIN team_with_rating o
        ON t.series_id = o.series_id
        AND LOWER(LTRIM(RTRIM(t.opponent_teamname))) = LOWER(LTRIM(RTRIM(o.teamname)))
        AND LOWER(LTRIM(RTRIM(t.teamname))) = LOWER(LTRIM(RTRIM(o.opponent_teamname)))
),

bucketed AS
(
    SELECT
        *,
        CASE
            WHEN top_kill_edge >= 2 THEN 'strong_plus'
            WHEN top_kill_edge >= 0.5 THEN 'plus'
            WHEN top_kill_edge > -0.5 THEN 'neutral'
            WHEN top_kill_edge > -2 THEN 'minus'
            ELSE 'strong_minus'
        END AS top_kill_bucket,

        CASE
            WHEN jng_kill_edge >= 2 THEN 'strong_plus'
            WHEN jng_kill_edge >= 0.5 THEN 'plus'
            WHEN jng_kill_edge > -0.5 THEN 'neutral'
            WHEN jng_kill_edge > -2 THEN 'minus'
            ELSE 'strong_minus'
        END AS jng_kill_bucket,

        CASE
            WHEN mid_kill_edge >= 2 THEN 'strong_plus'
            WHEN mid_kill_edge >= 0.5 THEN 'plus'
            WHEN mid_kill_edge > -0.5 THEN 'neutral'
            WHEN mid_kill_edge > -2 THEN 'minus'
            ELSE 'strong_minus'
        END AS mid_kill_bucket,

        CASE
            WHEN bot_kill_edge >= 2 THEN 'strong_plus'
            WHEN bot_kill_edge >= 0.5 THEN 'plus'
            WHEN bot_kill_edge > -0.5 THEN 'neutral'
            WHEN bot_kill_edge > -2 THEN 'minus'
            ELSE 'strong_minus'
        END AS bot_kill_bucket,

        CASE
            WHEN sup_assist_edge >= 5 THEN 'strong_plus'
            WHEN sup_assist_edge >= 1.5 THEN 'plus'
            WHEN sup_assist_edge > -1.5 THEN 'neutral'
            WHEN sup_assist_edge > -5 THEN 'minus'
            ELSE 'strong_minus'
        END AS sup_assist_bucket,

        CASE
            WHEN bot_dk_edge >= 20 THEN 'strong_plus'
            WHEN bot_dk_edge >= 7 THEN 'plus'
            WHEN bot_dk_edge > -7 THEN 'neutral'
            WHEN bot_dk_edge > -20 THEN 'minus'
            ELSE 'strong_minus'
        END AS bot_dk_bucket,

        CASE
            WHEN team_rating_edge >= 0.40 THEN 'strong_plus'
            WHEN team_rating_edge >= 0.15 THEN 'plus'
            WHEN team_rating_edge > -0.15 THEN 'neutral'
            WHEN team_rating_edge > -0.40 THEN 'minus'
            ELSE 'strong_minus'
        END AS team_rating_bucket
    FROM matched
)

INSERT INTO dbo.lol_bayes_matchup_training
(
    series_id,
    series_date,
    season,
    league,
    teamname,
    opponent_teamname,
    series_result,
    won_series,
    games_played,

    team_top_kills,
    team_jng_kills,
    team_mid_kills,
    team_bot_kills,
    team_sup_kills,

    team_top_assists,
    team_jng_assists,
    team_mid_assists,
    team_bot_assists,
    team_sup_assists,

    team_top_deaths,
    team_jng_deaths,
    team_mid_deaths,
    team_bot_deaths,
    team_sup_deaths,

    team_top_dk,
    team_jng_dk,
    team_mid_dk,
    team_bot_dk,
    team_sup_dk,

    opp_top_kills,
    opp_jng_kills,
    opp_mid_kills,
    opp_bot_kills,
    opp_sup_kills,

    opp_top_assists,
    opp_jng_assists,
    opp_mid_assists,
    opp_bot_assists,
    opp_sup_assists,

    opp_top_deaths,
    opp_jng_deaths,
    opp_mid_deaths,
    opp_bot_deaths,
    opp_sup_deaths,

    opp_top_dk,
    opp_jng_dk,
    opp_mid_dk,
    opp_bot_dk,
    opp_sup_dk,

    top_kill_edge,
    jng_kill_edge,
    mid_kill_edge,
    bot_kill_edge,
    sup_kill_edge,

    top_assist_edge,
    jng_assist_edge,
    mid_assist_edge,
    bot_assist_edge,
    sup_assist_edge,

    top_death_edge,
    jng_death_edge,
    mid_death_edge,
    bot_death_edge,
    sup_death_edge,

    top_dk_edge,
    jng_dk_edge,
    mid_dk_edge,
    bot_dk_edge,
    sup_dk_edge,

    team_kill_edge,
    team_assist_edge,
    team_death_edge,
    team_dk_edge,

    team_rating_score,
    opp_rating_score,
    team_rating_edge,

    top_kill_bucket,
    jng_kill_bucket,
    mid_kill_bucket,
    bot_kill_bucket,
    sup_assist_bucket,
    bot_dk_bucket,
    team_rating_bucket
)
SELECT
    series_id,
    series_date,
    season,
    league,
    teamname,
    opponent_teamname,
    series_result,
    won_series,
    games_played,

    team_top_kills,
    team_jng_kills,
    team_mid_kills,
    team_bot_kills,
    team_sup_kills,

    team_top_assists,
    team_jng_assists,
    team_mid_assists,
    team_bot_assists,
    team_sup_assists,

    team_top_deaths,
    team_jng_deaths,
    team_mid_deaths,
    team_bot_deaths,
    team_sup_deaths,

    team_top_dk,
    team_jng_dk,
    team_mid_dk,
    team_bot_dk,
    team_sup_dk,

    opp_top_kills,
    opp_jng_kills,
    opp_mid_kills,
    opp_bot_kills,
    opp_sup_kills,

    opp_top_assists,
    opp_jng_assists,
    opp_mid_assists,
    opp_bot_assists,
    opp_sup_assists,

    opp_top_deaths,
    opp_jng_deaths,
    opp_mid_deaths,
    opp_bot_deaths,
    opp_sup_deaths,

    opp_top_dk,
    opp_jng_dk,
    opp_mid_dk,
    opp_bot_dk,
    opp_sup_dk,

    top_kill_edge,
    jng_kill_edge,
    mid_kill_edge,
    bot_kill_edge,
    sup_kill_edge,

    top_assist_edge,
    jng_assist_edge,
    mid_assist_edge,
    bot_assist_edge,
    sup_assist_edge,

    top_death_edge,
    jng_death_edge,
    mid_death_edge,
    bot_death_edge,
    sup_death_edge,

    top_dk_edge,
    jng_dk_edge,
    mid_dk_edge,
    bot_dk_edge,
    sup_dk_edge,

    team_kill_edge,
    team_assist_edge,
    team_death_edge,
    team_dk_edge,

    team_rating_score,
    opp_rating_score,
    team_rating_edge,

    top_kill_bucket,
    jng_kill_bucket,
    mid_kill_bucket,
    bot_kill_bucket,
    sup_assist_bucket,
    bot_dk_bucket,
    team_rating_bucket
FROM bucketed
WHERE teamname IS NOT NULL
  AND opponent_teamname IS NOT NULL
  AND teamname <> opponent_teamname;
GO