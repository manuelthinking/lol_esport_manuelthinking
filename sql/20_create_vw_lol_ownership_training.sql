/* ============================================================
   LoL Ownership Training View - Slot-Aware Version

   Fixes:
     - Prevents FLEX ownership from joining to CPT salary rows.
     - Adds dk_slot_type and ownership_slot_type.
     - Keeps Bayes join, but Bayes will only populate if
       dbo.lol_bayes_prediction_backtest has that slate/date/team.

   Grain:
     one row per slate / player / ownership slot type
   ============================================================ */

IF OBJECT_ID('dbo.vw_lol_ownership_training', 'V') IS NOT NULL
BEGIN
    DROP VIEW dbo.vw_lol_ownership_training;
END;
GO

CREATE VIEW dbo.vw_lol_ownership_training AS

WITH ownership AS
(
    SELECT
        o.slate_date,
        o.slate_name,
        LTRIM(RTRIM(o.player_name)) AS player_name,
        LTRIM(RTRIM(o.roster_position)) AS roster_position,

        CASE
            WHEN UPPER(LTRIM(RTRIM(ISNULL(o.roster_position, '')))) IN ('CPT', 'CAPTAIN') THEN 'captain'
            WHEN UPPER(LTRIM(RTRIM(ISNULL(o.roster_position, '')))) = 'TEAM' THEN 'team'
            ELSE 'flex'
        END AS ownership_slot_type,

        COUNT(*) AS ownership_rows,
        AVG(CAST(o.ownership_pct AS FLOAT)) AS ownership_pct,
        AVG(CAST(o.actual_fp AS FLOAT)) AS actual_fp,

        MIN(o.contest_id) AS sample_contest_id,
        COUNT(DISTINCT o.contest_id) AS contest_count
    FROM raw.dk_lol_player_ownership o
    WHERE o.ownership_pct IS NOT NULL
      AND o.player_name IS NOT NULL
    GROUP BY
        o.slate_date,
        o.slate_name,
        LTRIM(RTRIM(o.player_name)),
        LTRIM(RTRIM(o.roster_position)),
        CASE
            WHEN UPPER(LTRIM(RTRIM(ISNULL(o.roster_position, '')))) IN ('CPT', 'CAPTAIN') THEN 'captain'
            WHEN UPPER(LTRIM(RTRIM(ISNULL(o.roster_position, '')))) = 'TEAM' THEN 'team'
            ELSE 'flex'
        END
),

dk AS
(
    SELECT
        d.slate_date,
        d.slate_name,
        d.source_file,
        d.dk_position,
        d.name_id,
        LTRIM(RTRIM(d.player_name)) AS player_name,
        d.dk_player_id,
        d.roster_position AS dk_roster_position,
        d.salary,
        d.game_info,
        d.team_abbrev,
        d.avg_points_per_game,

        CASE
            WHEN UPPER(LTRIM(RTRIM(ISNULL(d.dk_position, '')))) IN ('CPT', 'CAPTAIN') THEN 'captain'
            WHEN UPPER(LTRIM(RTRIM(ISNULL(d.roster_position, '')))) LIKE '%CPT%' THEN 'captain'
            WHEN UPPER(LTRIM(RTRIM(ISNULL(d.dk_position, '')))) = 'TEAM' THEN 'team'
            WHEN UPPER(LTRIM(RTRIM(ISNULL(d.roster_position, '')))) = 'TEAM' THEN 'team'
            ELSE 'flex'
        END AS dk_slot_type,

        CASE
            WHEN d.game_info LIKE '%@%' THEN
                LEFT(d.game_info, CHARINDEX('@', d.game_info) - 1)
            ELSE NULL
        END AS away_team_abbrev,

        CASE
            WHEN d.game_info LIKE '%@%' THEN
                LTRIM(RTRIM(
                    LEFT(
                        SUBSTRING(d.game_info, CHARINDEX('@', d.game_info) + 1, 200),
                        CASE
                            WHEN CHARINDEX(' ', SUBSTRING(d.game_info, CHARINDEX('@', d.game_info) + 1, 200)) > 0
                            THEN CHARINDEX(' ', SUBSTRING(d.game_info, CHARINDEX('@', d.game_info) + 1, 200)) - 1
                            ELSE LEN(SUBSTRING(d.game_info, CHARINDEX('@', d.game_info) + 1, 200))
                        END
                    )
                ))
            ELSE NULL
        END AS home_team_abbrev
    FROM dbo.dk_lol_slate_player d
),

dk_with_opp AS
(
    SELECT
        *,
        CASE
            WHEN team_abbrev = away_team_abbrev THEN home_team_abbrev
            WHEN team_abbrev = home_team_abbrev THEN away_team_abbrev
            ELSE NULL
        END AS opponent_abbrev
    FROM dk
),

latest_rating AS
(
    SELECT
        r.*,
        ROW_NUMBER() OVER (
            PARTITION BY
                LOWER(LTRIM(RTRIM(r.player_name))),
                LOWER(LTRIM(RTRIM(r.position))),
                r.season
            ORDER BY
                r.games DESC,
                r.rating_score DESC
        ) AS rn
    FROM dbo.lol_player_lane_ratings r
),

joined AS
(
    SELECT
        o.slate_date,
        o.slate_name,

        o.player_name AS ownership_player_name,
        o.roster_position AS ownership_roster_position,
        o.ownership_slot_type,

        o.ownership_pct,
        o.actual_fp,
        o.ownership_rows,
        o.contest_count,
        o.sample_contest_id,

        d.source_file,
        d.dk_position,
        d.name_id,
        d.player_name AS dk_player_name,
        d.dk_player_id,
        d.dk_roster_position,
        d.dk_slot_type,
        d.salary,
        d.game_info,
        d.team_abbrev,
        d.opponent_abbrev,
        d.avg_points_per_game,

        r.league,
        r.team_name AS rating_team_name,
        r.player_name AS rating_player_name,
        r.position,
        r.games,
        r.win_rate,
        r.avg_dk,
        r.avg_dk_edge,
        r.avg_kills,
        r.avg_deaths,
        r.avg_assists,
        r.avg_kill_edge,
        r.avg_death_edge,
        r.avg_assist_edge,
        r.avg_gold_diff_10_edge,
        r.avg_xp_diff_10_edge,
        r.avg_cs_diff_10_edge,
        r.avg_dpm_edge,
        r.rating_score,

        CASE
            WHEN d.salary > 0 THEN r.avg_dk / (d.salary / 1000.0)
            ELSE NULL
        END AS dk_value,

        CASE
            WHEN d.salary > 0 THEN r.rating_score / (d.salary / 1000.0)
            ELSE NULL
        END AS rating_value
    FROM ownership o
    INNER JOIN dk_with_opp d
        ON o.slate_date = d.slate_date
        AND o.slate_name = d.slate_name
        AND LOWER(LTRIM(RTRIM(o.player_name))) = LOWER(LTRIM(RTRIM(d.player_name)))
        AND o.ownership_slot_type = d.dk_slot_type
    LEFT JOIN latest_rating r
        ON LOWER(LTRIM(RTRIM(d.player_name))) = LOWER(LTRIM(RTRIM(r.player_name)))
        AND r.season = YEAR(o.slate_date)
        AND r.rn = 1
),

with_starters AS
(
    SELECT
        j.*,

        h.starter_role,
        h.is_starter,
        h.games_played AS historical_starter_games_played,
        h.total_dk_points AS historical_starter_total_dk_points,
        h.avg_dk_points AS historical_starter_avg_dk_points,

        CASE
            WHEN h.starter_role = 'starter' THEN 1
            WHEN h.starter_role = 'sub' THEN 0
            ELSE NULL
        END AS actual_starter_flag
    FROM joined j
    LEFT JOIN dbo.lol_manual_starters_history h
        ON j.slate_date = h.slate_date
        AND LOWER(LTRIM(RTRIM(ISNULL(j.rating_team_name, j.team_abbrev)))) = LOWER(LTRIM(RTRIM(h.teamname)))
        AND LOWER(LTRIM(RTRIM(j.position))) = LOWER(LTRIM(RTRIM(h.position)))
        AND LOWER(LTRIM(RTRIM(j.dk_player_name))) = LOWER(LTRIM(RTRIM(h.playername)))
),

with_bayes AS
(
    SELECT
        ws.*,

        bt.sample_type AS bayes_sample_type,
        bt.similar_sample AS bayes_similar_sample,

        bt.bayes_win_pct,
        bt.bayes_p_2_0,
        bt.bayes_p_2_1,
        bt.bayes_p_1_2,
        bt.bayes_p_0_2,

        bt.suggested_path AS bayes_suggested_path,
        bt.suggested_winner_teamname,
        bt.suggested_match_score,

        bt.team_strength_bucket,
        bt.opponent_strength_bucket,
        bt.strength_matchup_bucket,

        bt.mid_lane_matchup_bucket,
        bt.bot_lane_matchup_bucket,
        bt.sup_lane_matchup_bucket,

        bt.team_mid_strength,
        bt.opponent_mid_strength,
        bt.team_bot_strength,
        bt.opponent_bot_strength,
        bt.team_sup_strength,
        bt.opponent_sup_strength,

        bt.team_mid_dk_index,
        bt.opponent_mid_dk_index,
        bt.team_bot_dk_index,
        bt.opponent_bot_dk_index,
        bt.team_sup_dk_index,
        bt.opponent_sup_dk_index
    FROM with_starters ws

    LEFT JOIN dbo.lol_team_name_map tm
        ON UPPER(LTRIM(RTRIM(ws.team_abbrev))) = UPPER(LTRIM(RTRIM(tm.dk_team_abbrev)))

    LEFT JOIN dbo.lol_team_name_map om
        ON UPPER(LTRIM(RTRIM(ws.opponent_abbrev))) = UPPER(LTRIM(RTRIM(om.dk_team_abbrev)))

    LEFT JOIN dbo.lol_bayes_prediction_backtest bt
        ON ws.slate_date = bt.target_series_date
        AND LOWER(LTRIM(RTRIM(COALESCE(tm.oracle_teamname, ws.rating_team_name)))) = LOWER(LTRIM(RTRIM(bt.teamname)))
        AND (
            om.oracle_teamname IS NULL
            OR LOWER(LTRIM(RTRIM(om.oracle_teamname))) = LOWER(LTRIM(RTRIM(bt.opponent_teamname)))
        )
        AND (
            tm.league IS NULL
            OR LOWER(LTRIM(RTRIM(tm.league))) = LOWER(LTRIM(RTRIM(bt.league)))
        )
        AND bt.prediction_source = 'historical_point_in_time_bayes'
)

SELECT
    slate_date,
    slate_name,

    ownership_player_name,
    dk_player_name,
    dk_player_id,

    ownership_roster_position,
    ownership_slot_type,
    dk_position,
    dk_roster_position,
    dk_slot_type,

    team_abbrev,
    opponent_abbrev,
    rating_team_name,
    league,
    game_info,

    position,
    salary,
    avg_points_per_game,

    ownership_pct,
    actual_fp,
    ownership_rows,
    contest_count,
    sample_contest_id,

    games,
    win_rate,
    avg_dk,
    avg_dk_edge,
    avg_kills,
    avg_deaths,
    avg_assists,
    avg_kill_edge,
    avg_death_edge,
    avg_assist_edge,
    avg_gold_diff_10_edge,
    avg_xp_diff_10_edge,
    avg_cs_diff_10_edge,
    avg_dpm_edge,
    rating_score,
    dk_value,
    rating_value,

    starter_role,
    is_starter,
    actual_starter_flag,
    historical_starter_games_played,
    historical_starter_total_dk_points,
    historical_starter_avg_dk_points,

    bayes_sample_type,
    bayes_similar_sample,
    bayes_win_pct,
    bayes_p_2_0,
    bayes_p_2_1,
    bayes_p_1_2,
    bayes_p_0_2,
    bayes_suggested_path,
    suggested_winner_teamname,
    suggested_match_score,

    team_strength_bucket,
    opponent_strength_bucket,
    strength_matchup_bucket,

    mid_lane_matchup_bucket,
    bot_lane_matchup_bucket,
    sup_lane_matchup_bucket,

    team_mid_strength,
    opponent_mid_strength,
    team_bot_strength,
    opponent_bot_strength,
    team_sup_strength,
    opponent_sup_strength,

    team_mid_dk_index,
    opponent_mid_dk_index,
    team_bot_dk_index,
    opponent_bot_dk_index,
    team_sup_dk_index,
    opponent_sup_dk_index,

    CASE
        WHEN salary >= 7600 THEN 'premium'
        WHEN salary >= 6200 THEN 'upper_mid'
        WHEN salary >= 4800 THEN 'mid'
        WHEN salary >= 3600 THEN 'value'
        ELSE 'punt'
    END AS salary_tier,

    CASE
        WHEN bayes_suggested_path IN ('2-0', '2-1') THEN 1
        WHEN bayes_suggested_path IN ('1-2', '0-2') THEN 0
        ELSE NULL
    END AS bayes_team_win_flag,

    CASE
        WHEN bayes_suggested_path IN ('2-0', '0-2') THEN 1
        WHEN bayes_suggested_path IN ('2-1', '1-2') THEN 0
        ELSE NULL
    END AS bayes_sweep_flag

FROM with_bayes;
GO