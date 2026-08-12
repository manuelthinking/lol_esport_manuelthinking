USE lol_esports;
GO

CREATE OR ALTER VIEW dbo.vw_lol_slate_lane_power_signal_live_v1 AS
WITH latest_rating AS (
    SELECT
        r.*,
        ROW_NUMBER() OVER (
            PARTITION BY 
                LOWER(LTRIM(RTRIM(r.player_name))),
                LOWER(LTRIM(RTRIM(r.position)))
            ORDER BY 
                r.season DESC,
                r.games DESC,
                r.rating_score DESC
        ) AS rn
    FROM dbo.lol_player_lane_ratings r
    WHERE r.season = 2026
),
latest_lane_power AS (
    SELECT
        r.*,
        ROW_NUMBER() OVER (
            PARTITION BY
                r.league,
                LOWER(LTRIM(RTRIM(r.player_name))),
                r.lane
            ORDER BY
                r.games_played DESC,
                r.lane_power_score DESC
        ) AS rn
    FROM dbo.vw_lol_player_lane_power_rating_v1 r
),
slate_players_raw AS (
    SELECT
        dk.slate_date,
        dk.slate_name,
        dk.game_info,
        dk.team_abbrev,
        dk.player_name AS dk_player_name,
        dk.salary,

        lr.league,
        lr.team_name AS rating_team_name,
        lr.player_name AS rating_player_name,

        CASE
            WHEN LOWER(LTRIM(RTRIM(ISNULL(dk.dk_position, '')))) IN ('bot', 'adc') THEN 'ADC'
            WHEN LOWER(LTRIM(RTRIM(ISNULL(dk.dk_position, '')))) IN ('jng', 'jun', 'jungle') THEN 'JNG'
            ELSE UPPER(LTRIM(RTRIM(ISNULL(dk.dk_position, ''))))
        END AS lane
    FROM dbo.dk_lol_slate_player dk
    LEFT JOIN latest_rating lr
        ON LOWER(LTRIM(RTRIM(dk.player_name))) = LOWER(LTRIM(RTRIM(lr.player_name)))
       AND LOWER(LTRIM(RTRIM(ISNULL(dk.dk_position, '')))) =
           CASE
                WHEN LOWER(LTRIM(RTRIM(lr.position))) = 'bot' THEN 'adc'
                WHEN LOWER(LTRIM(RTRIM(lr.position))) = 'jng' THEN 'jng'
                ELSE LOWER(LTRIM(RTRIM(lr.position)))
           END
       AND lr.rn = 1
    WHERE UPPER(LTRIM(RTRIM(ISNULL(dk.dk_position, '')))) NOT IN ('CPT', 'CAPTAIN', 'TEAM')
      AND UPPER(LTRIM(RTRIM(ISNULL(dk.roster_position, '')))) NOT IN ('CPT', 'CAPTAIN')
      AND dk.team_abbrev IS NOT NULL
      AND dk.game_info IS NOT NULL
),
picked_players AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY slate_date, slate_name, game_info, team_abbrev, lane
            ORDER BY salary DESC, dk_player_name
        ) AS player_pick_rank
    FROM slate_players_raw
    WHERE lane IN ('TOP', 'JNG', 'MID', 'ADC', 'SUP')
),
team_lanes AS (
    SELECT
        p.slate_date,
        p.slate_name,
        p.game_info,
        p.team_abbrev,
        p.rating_team_name,
        p.league,
        p.lane,
        p.dk_player_name,
        p.salary,

        r.team AS historical_team_name,
        r.lane_power_score,
        r.lane_power_rank,
        r.lane_power_tier,
        r.games_played,
        r.avg_dk_points,
        r.kills_per_game,
        r.deaths_per_game,
        r.assists_per_game,
        r.dpm
    FROM picked_players p
    LEFT JOIN latest_lane_power r
        ON p.league = r.league
       AND p.lane = r.lane
       AND LOWER(LTRIM(RTRIM(p.dk_player_name))) = LOWER(LTRIM(RTRIM(r.player_name)))
       AND r.rn = 1
    WHERE p.player_pick_rank = 1
),
lane_edges AS (
    SELECT
        tl.slate_date,
        tl.slate_name,
        tl.game_info,
        tl.league,

        tl.team_abbrev AS team,
        ol.team_abbrev AS opponent,

        COALESCE(tl.rating_team_name, tl.historical_team_name, tl.team_abbrev) AS team_full_name,
        COALESCE(ol.rating_team_name, ol.historical_team_name, ol.team_abbrev) AS opponent_full_name,

        tl.lane,

        tl.dk_player_name AS player_name,
        ol.dk_player_name AS opponent_player_name,

        tl.lane_power_score,
        ol.lane_power_score AS opponent_lane_power_score,

        tl.lane_power_rank,
        ol.lane_power_rank AS opponent_lane_power_rank,

        tl.lane_power_tier,
        ol.lane_power_tier AS opponent_lane_power_tier,

        CASE
            WHEN tl.lane_power_score IS NULL OR ol.lane_power_score IS NULL THEN NULL
            ELSE tl.lane_power_score - ol.lane_power_score
        END AS lane_power_edge
    FROM team_lanes tl
    INNER JOIN team_lanes ol
        ON tl.slate_date = ol.slate_date
       AND tl.slate_name = ol.slate_name
       AND tl.game_info = ol.game_info
       AND tl.lane = ol.lane
       AND tl.team_abbrev <> ol.team_abbrev
),
summary AS (
    SELECT
        slate_date AS game_date,
        slate_name,
        game_info,
        league,
        team,
        opponent,
        team_full_name,
        opponent_full_name,

        COUNT(*) AS lane_rows,
        SUM(CASE WHEN lane_power_edge IS NOT NULL THEN 1 ELSE 0 END) AS rated_lane_rows,

        MAX(CASE WHEN lane = 'TOP' THEN lane_power_edge END) AS top_lane_edge,
        MAX(CASE WHEN lane = 'JNG' THEN lane_power_edge END) AS jng_lane_edge,
        MAX(CASE WHEN lane = 'MID' THEN lane_power_edge END) AS mid_lane_edge,
        MAX(CASE WHEN lane = 'ADC' THEN lane_power_edge END) AS adc_lane_edge,
        MAX(CASE WHEN lane = 'SUP' THEN lane_power_edge END) AS sup_lane_edge,

        SUM(CASE WHEN lane_power_edge IS NOT NULL THEN lane_power_edge ELSE 0 END) AS total_lane_edge,

        SUM(CASE
                WHEN lane IN ('JNG', 'MID', 'ADC') AND lane_power_edge IS NOT NULL
                THEN lane_power_edge
                ELSE 0
            END) AS carry_lane_edge,

        SUM(CASE
                WHEN lane IN ('MID', 'ADC') AND lane_power_edge IS NOT NULL
                THEN lane_power_edge
                ELSE 0
            END) AS main_carry_lane_edge,

        SUM(CASE
                WHEN lane IN ('TOP', 'SUP') AND lane_power_edge IS NOT NULL
                THEN lane_power_edge
                ELSE 0
            END) AS secondary_lane_edge,

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
        slate_date,
        slate_name,
        game_info,
        league,
        team,
        opponent,
        team_full_name,
        opponent_full_name
)
SELECT
    'slate_lane_power_live_v1' AS signal_version,

    game_date,
    slate_name,
    game_info,
    league,
    team,
    opponent,
    team_full_name,
    opponent_full_name,

    CAST(NULL AS float) AS bayes_win_pct,
    CAST(NULL AS float) AS adjusted_win_pct,

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

    -- Backward-compatible aliases used by the Streamlit command center.
    opponent_neutral_or_better_lanes AS opponent_neutralized_lanes,
    opponent_neutral_or_better_carry_lanes AS opponent_neutral_high_edges,

    CASE
        WHEN rated_lane_rows < 3 THEN 'Thin Live Rating'
        WHEN total_lane_edge >= 50 THEN 'Massive Overall Lane Edge'
        WHEN total_lane_edge >= 25 THEN 'Strong Overall Lane Edge'
        WHEN total_lane_edge >= 10 THEN 'Moderate Overall Lane Edge'
        WHEN total_lane_edge > -10 THEN 'Mostly Even Overall'
        WHEN total_lane_edge > -25 THEN 'Moderate Overall Lane Disadvantage'
        WHEN total_lane_edge > -50 THEN 'Strong Overall Lane Disadvantage'
        ELSE 'Massive Overall Lane Disadvantage'
    END AS total_lane_edge_tier,

    CASE
        WHEN rated_lane_rows < 3 THEN 'Thin Live Rating'
        WHEN carry_lane_edge >= 30 THEN 'Massive Carry Lane Edge'
        WHEN carry_lane_edge >= 20 THEN 'Strong Carry Lane Edge'
        WHEN carry_lane_edge >= 5 THEN 'Moderate Carry Lane Edge'
        WHEN carry_lane_edge > -5 THEN 'Mostly Even Carry Lanes'
        WHEN carry_lane_edge > -15 THEN 'Carry Lane Concern'
        ELSE 'Major Carry Lane Concern'
    END AS carry_lane_edge_tier,

    CASE
        WHEN rated_lane_rows < 3 THEN 0.00
        WHEN carry_lane_edge >= 20 THEN 0.05
        WHEN carry_lane_edge <= -15 THEN -0.10
        ELSE 0.00
    END AS lane_power_win_pct_modifier,

    -- Backward-compatible name used by the current Streamlit app.
    CASE
        WHEN rated_lane_rows < 3 THEN 0.00
        WHEN carry_lane_edge >= 20 THEN 0.05
        WHEN carry_lane_edge <= -15 THEN -0.10
        ELSE 0.00
    END AS lane_power_win_pct,

    CASE
        WHEN rated_lane_rows < 3 THEN 'Thin Live Data'
        WHEN carry_lane_edge >= 20 THEN 'Strong Carry Support'
        WHEN carry_lane_edge <= -15 THEN 'Major Carry Concern'
        WHEN carry_lane_edge >= 5 THEN 'Moderate Carry Support'
        WHEN carry_lane_edge > -5 THEN 'Carry Neutral'
        ELSE 'Carry Concern'
    END AS dfs_lane_power_signal,

    CASE
        WHEN rated_lane_rows < 3
            THEN 'Not enough matched lane ratings. Do not adjust the Bayes read much.'

        WHEN carry_lane_edge >= 20
            THEN 'Lane power supports this team. Upgrade confidence if Bayes/projections also agree.'

        WHEN carry_lane_edge <= -15
            THEN 'Carry lanes are a real concern. Downgrade favorite confidence and avoid blindly assuming a stomp.'

        WHEN carry_lane_edge >= 5
            THEN 'Mild lane support. Useful as a tie-breaker, not a full upgrade.'

        WHEN carry_lane_edge > -5
            THEN 'Carry lanes are close to neutral. No major lane-power adjustment.'

        ELSE 'Some carry-lane concern. Be careful with heavy favorite stacks.'
    END AS dfs_lane_power_note
FROM summary;
GO