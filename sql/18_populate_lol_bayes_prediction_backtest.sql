/* ============================================================
   Populate LoL Bayesian Prediction Backtest - Corrected Version

   Fix:
     Uses row_key so each team-side prediction is kept separate.

   Why:
     target_series_id has two rows:
       Team A vs Team B
       Team B vs Team A

     Grouping only by target_series_id averages both sides together
     and forces bayes_win_pct toward 50%.

   Target:
     dbo.lol_bayes_prediction_backtest

   Source:
     dbo.vw_lol_bayes_strength_matchups_point_in_time
   ============================================================ */

SET NOCOUNT ON;

DECLARE @prior_weight FLOAT = 10.0;


/* ============================================================
   Cleanup temp tables
   ============================================================ */

IF OBJECT_ID('tempdb..#base') IS NOT NULL DROP TABLE #base;
IF OBJECT_ID('tempdb..#league_prior') IS NOT NULL DROP TABLE #league_prior;
IF OBJECT_ID('tempdb..#strict_sample') IS NOT NULL DROP TABLE #strict_sample;
IF OBJECT_ID('tempdb..#mid_bot_sample') IS NOT NULL DROP TABLE #mid_bot_sample;
IF OBJECT_ID('tempdb..#strength_sample') IS NOT NULL DROP TABLE #strength_sample;
IF OBJECT_ID('tempdb..#chosen_sample') IS NOT NULL DROP TABLE #chosen_sample;
IF OBJECT_ID('tempdb..#smoothed') IS NOT NULL DROP TABLE #smoothed;
IF OBJECT_ID('tempdb..#output_rows') IS NOT NULL DROP TABLE #output_rows;


/* ============================================================
   1. Base historical point-in-time rows

   row_key is the unique team-side prediction key.
   ============================================================ */

SELECT
    CONCAT(
        CAST(target_series_id AS VARCHAR(100)),
        '|',
        LOWER(LTRIM(RTRIM(teamname))),
        '|',
        LOWER(LTRIM(RTRIM(opponent_teamname)))
    ) AS row_key,

    CAST(target_series_id AS VARCHAR(100)) AS target_series_id,
    league,
    season,
    CAST(target_series_date AS DATE) AS target_series_date,

    teamname,
    opponent_teamname,

    actual_series_result,
    CAST(actual_won_series AS INT) AS actual_won_series,
    actual_game_wins,
    actual_game_losses,

    team_strength_bucket,
    opponent_strength_bucket,
    strength_matchup_bucket,

    team_strength_sample_label,
    opponent_strength_sample_label,

    team_prior_series_count,
    opponent_prior_series_count,

    team_smoothed_prior_series_win_rate,
    opponent_smoothed_prior_series_win_rate,
    smoothed_strength_gap,

    mid_lane_matchup_bucket,
    bot_lane_matchup_bucket,
    sup_lane_matchup_bucket,
    top_lane_matchup_bucket,
    jng_lane_matchup_bucket,

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
    opponent_sup_dk_index
INTO #base
FROM dbo.vw_lol_bayes_strength_matchups_point_in_time
WHERE league IN ('LPL', 'LCK')
  AND season = 2026
  AND actual_series_result IN ('2-0', '2-1', '1-2', '0-2');


CREATE INDEX ix_base_row_key
ON #base(row_key);

CREATE INDEX ix_base_main
ON #base
(
    league,
    season,
    target_series_date,
    strength_matchup_bucket
);

CREATE INDEX ix_base_matchup
ON #base
(
    league,
    season,
    target_series_date,
    strength_matchup_bucket,
    mid_lane_matchup_bucket,
    bot_lane_matchup_bucket,
    sup_lane_matchup_bucket
);


/* ============================================================
   2. League priors before each target team-side row

   This can still be league/date based, but stored by row_key.
   ============================================================ */

SELECT
    t.row_key,

    COUNT(h.row_key) AS league_prior_sample,

    ISNULL(AVG(CAST(h.actual_won_series AS FLOAT)), 0.50) AS league_win_rate,

    ISNULL(AVG(CASE WHEN h.actual_series_result = '2-0' THEN 1.0 ELSE 0.0 END), 0.25) AS league_p_2_0,
    ISNULL(AVG(CASE WHEN h.actual_series_result = '2-1' THEN 1.0 ELSE 0.0 END), 0.25) AS league_p_2_1,
    ISNULL(AVG(CASE WHEN h.actual_series_result = '1-2' THEN 1.0 ELSE 0.0 END), 0.25) AS league_p_1_2,
    ISNULL(AVG(CASE WHEN h.actual_series_result = '0-2' THEN 1.0 ELSE 0.0 END), 0.25) AS league_p_0_2
INTO #league_prior
FROM #base t
LEFT JOIN #base h
    ON t.league = h.league
    AND t.season = h.season
    AND h.target_series_date < t.target_series_date
GROUP BY
    t.row_key;

CREATE INDEX ix_league_prior_row_key
ON #league_prior(row_key);


/* ============================================================
   3. Strict sample:
      Strength + MID/BOT/SUP

   Stored by row_key so team-side rows do not blend together.
   ============================================================ */

SELECT
    t.row_key,

    COUNT(h.row_key) AS sample_size,
    SUM(CASE WHEN h.actual_won_series = 1 THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN h.actual_series_result = '2-0' THEN 1 ELSE 0 END) AS count_2_0,
    SUM(CASE WHEN h.actual_series_result = '2-1' THEN 1 ELSE 0 END) AS count_2_1,
    SUM(CASE WHEN h.actual_series_result = '1-2' THEN 1 ELSE 0 END) AS count_1_2,
    SUM(CASE WHEN h.actual_series_result = '0-2' THEN 1 ELSE 0 END) AS count_0_2
INTO #strict_sample
FROM #base t
LEFT JOIN #base h
    ON t.league = h.league
    AND t.season = h.season
    AND h.target_series_date < t.target_series_date
    AND h.strength_matchup_bucket = t.strength_matchup_bucket
    AND h.mid_lane_matchup_bucket = t.mid_lane_matchup_bucket
    AND h.bot_lane_matchup_bucket = t.bot_lane_matchup_bucket
    AND h.sup_lane_matchup_bucket = t.sup_lane_matchup_bucket
GROUP BY
    t.row_key;

CREATE INDEX ix_strict_row_key
ON #strict_sample(row_key);


/* ============================================================
   4. Mid/Bot sample:
      Strength + MID/BOT
   ============================================================ */

SELECT
    t.row_key,

    COUNT(h.row_key) AS sample_size,
    SUM(CASE WHEN h.actual_won_series = 1 THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN h.actual_series_result = '2-0' THEN 1 ELSE 0 END) AS count_2_0,
    SUM(CASE WHEN h.actual_series_result = '2-1' THEN 1 ELSE 0 END) AS count_2_1,
    SUM(CASE WHEN h.actual_series_result = '1-2' THEN 1 ELSE 0 END) AS count_1_2,
    SUM(CASE WHEN h.actual_series_result = '0-2' THEN 1 ELSE 0 END) AS count_0_2
INTO #mid_bot_sample
FROM #base t
LEFT JOIN #base h
    ON t.league = h.league
    AND t.season = h.season
    AND h.target_series_date < t.target_series_date
    AND h.strength_matchup_bucket = t.strength_matchup_bucket
    AND h.mid_lane_matchup_bucket = t.mid_lane_matchup_bucket
    AND h.bot_lane_matchup_bucket = t.bot_lane_matchup_bucket
GROUP BY
    t.row_key;

CREATE INDEX ix_mid_bot_row_key
ON #mid_bot_sample(row_key);


/* ============================================================
   5. Strength-only sample
   ============================================================ */

SELECT
    t.row_key,

    COUNT(h.row_key) AS sample_size,
    SUM(CASE WHEN h.actual_won_series = 1 THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN h.actual_series_result = '2-0' THEN 1 ELSE 0 END) AS count_2_0,
    SUM(CASE WHEN h.actual_series_result = '2-1' THEN 1 ELSE 0 END) AS count_2_1,
    SUM(CASE WHEN h.actual_series_result = '1-2' THEN 1 ELSE 0 END) AS count_1_2,
    SUM(CASE WHEN h.actual_series_result = '0-2' THEN 1 ELSE 0 END) AS count_0_2
INTO #strength_sample
FROM #base t
LEFT JOIN #base h
    ON t.league = h.league
    AND t.season = h.season
    AND h.target_series_date < t.target_series_date
    AND h.strength_matchup_bucket = t.strength_matchup_bucket
GROUP BY
    t.row_key;

CREATE INDEX ix_strength_row_key
ON #strength_sample(row_key);


/* ============================================================
   6. Choose fallback sample
   ============================================================ */

SELECT
    b.*,

    lp.league_prior_sample,
    lp.league_win_rate,
    lp.league_p_2_0,
    lp.league_p_2_1,
    lp.league_p_1_2,
    lp.league_p_0_2,

    CASE
        WHEN ISNULL(ss.sample_size, 0) >= 5 THEN 'Strength + MID/BOT/SUP'
        WHEN ISNULL(mb.sample_size, 0) >= 5 THEN 'Strength + MID/BOT'
        WHEN ISNULL(st.sample_size, 0) >= 5 THEN 'Strength Only'
        ELSE 'League Prior Only'
    END AS sample_type,

    CASE
        WHEN ISNULL(ss.sample_size, 0) >= 5 THEN ss.sample_size
        WHEN ISNULL(mb.sample_size, 0) >= 5 THEN mb.sample_size
        WHEN ISNULL(st.sample_size, 0) >= 5 THEN st.sample_size
        ELSE 0
    END AS similar_sample,

    CASE
        WHEN ISNULL(ss.sample_size, 0) >= 5 THEN ss.wins
        WHEN ISNULL(mb.sample_size, 0) >= 5 THEN mb.wins
        WHEN ISNULL(st.sample_size, 0) >= 5 THEN st.wins
        ELSE 0
    END AS sample_wins,

    CASE
        WHEN ISNULL(ss.sample_size, 0) >= 5 THEN ss.count_2_0
        WHEN ISNULL(mb.sample_size, 0) >= 5 THEN mb.count_2_0
        WHEN ISNULL(st.sample_size, 0) >= 5 THEN st.count_2_0
        ELSE 0
    END AS sample_count_2_0,

    CASE
        WHEN ISNULL(ss.sample_size, 0) >= 5 THEN ss.count_2_1
        WHEN ISNULL(mb.sample_size, 0) >= 5 THEN mb.count_2_1
        WHEN ISNULL(st.sample_size, 0) >= 5 THEN st.count_2_1
        ELSE 0
    END AS sample_count_2_1,

    CASE
        WHEN ISNULL(ss.sample_size, 0) >= 5 THEN ss.count_1_2
        WHEN ISNULL(mb.sample_size, 0) >= 5 THEN mb.count_1_2
        WHEN ISNULL(st.sample_size, 0) >= 5 THEN st.count_1_2
        ELSE 0
    END AS sample_count_1_2,

    CASE
        WHEN ISNULL(ss.sample_size, 0) >= 5 THEN ss.count_0_2
        WHEN ISNULL(mb.sample_size, 0) >= 5 THEN mb.count_0_2
        WHEN ISNULL(st.sample_size, 0) >= 5 THEN st.count_0_2
        ELSE 0
    END AS sample_count_0_2
INTO #chosen_sample
FROM #base b
LEFT JOIN #league_prior lp
    ON b.row_key = lp.row_key
LEFT JOIN #strict_sample ss
    ON b.row_key = ss.row_key
LEFT JOIN #mid_bot_sample mb
    ON b.row_key = mb.row_key
LEFT JOIN #strength_sample st
    ON b.row_key = st.row_key;


/* ============================================================
   7. Smooth probabilities
   ============================================================ */

SELECT
    *,

    (
        ISNULL(sample_wins, 0)
        + (ISNULL(league_win_rate, 0.50) * @prior_weight)
    )
    /
    NULLIF(ISNULL(similar_sample, 0) + @prior_weight, 0) AS bayes_win_rate,

    (
        ISNULL(sample_count_2_0, 0)
        + (ISNULL(league_p_2_0, 0.25) * @prior_weight)
    )
    /
    NULLIF(ISNULL(similar_sample, 0) + @prior_weight, 0) AS raw_bayes_p_2_0,

    (
        ISNULL(sample_count_2_1, 0)
        + (ISNULL(league_p_2_1, 0.25) * @prior_weight)
    )
    /
    NULLIF(ISNULL(similar_sample, 0) + @prior_weight, 0) AS raw_bayes_p_2_1,

    (
        ISNULL(sample_count_1_2, 0)
        + (ISNULL(league_p_1_2, 0.25) * @prior_weight)
    )
    /
    NULLIF(ISNULL(similar_sample, 0) + @prior_weight, 0) AS raw_bayes_p_1_2,

    (
        ISNULL(sample_count_0_2, 0)
        + (ISNULL(league_p_0_2, 0.25) * @prior_weight)
    )
    /
    NULLIF(ISNULL(similar_sample, 0) + @prior_weight, 0) AS raw_bayes_p_0_2
INTO #smoothed
FROM #chosen_sample;


/* ============================================================
   8. Build output rows
   ============================================================ */

SELECT
    s.row_key,
    s.target_series_id,
    s.league,
    s.season,
    s.target_series_date,

    s.teamname,
    s.opponent_teamname,

    s.actual_series_result,
    CAST(s.actual_won_series AS BIT) AS actual_won_series,
    s.actual_game_wins,
    s.actual_game_losses,

    s.team_strength_bucket,
    s.opponent_strength_bucket,
    s.strength_matchup_bucket,

    s.team_strength_sample_label,
    s.opponent_strength_sample_label,

    s.team_prior_series_count,
    s.opponent_prior_series_count,

    s.team_smoothed_prior_series_win_rate,
    s.opponent_smoothed_prior_series_win_rate,
    s.smoothed_strength_gap,

    s.mid_lane_matchup_bucket,
    s.bot_lane_matchup_bucket,
    s.sup_lane_matchup_bucket,
    s.top_lane_matchup_bucket,
    s.jng_lane_matchup_bucket,

    s.team_mid_strength,
    s.opponent_mid_strength,
    s.team_bot_strength,
    s.opponent_bot_strength,
    s.team_sup_strength,
    s.opponent_sup_strength,

    s.team_mid_dk_index,
    s.opponent_mid_dk_index,
    s.team_bot_dk_index,
    s.opponent_bot_dk_index,
    s.team_sup_dk_index,
    s.opponent_sup_dk_index,

    s.sample_type,
    s.similar_sample,

    s.bayes_win_rate * 100.0 AS bayes_win_pct,

    CASE 
        WHEN path_total.path_prob_total > 0 THEN s.raw_bayes_p_2_0 / path_total.path_prob_total * 100.0
        ELSE 25.0
    END AS bayes_p_2_0,

    CASE 
        WHEN path_total.path_prob_total > 0 THEN s.raw_bayes_p_2_1 / path_total.path_prob_total * 100.0
        ELSE 25.0
    END AS bayes_p_2_1,

    CASE 
        WHEN path_total.path_prob_total > 0 THEN s.raw_bayes_p_1_2 / path_total.path_prob_total * 100.0
        ELSE 25.0
    END AS bayes_p_1_2,

    CASE 
        WHEN path_total.path_prob_total > 0 THEN s.raw_bayes_p_0_2 / path_total.path_prob_total * 100.0
        ELSE 25.0
    END AS bayes_p_0_2,

    CAST(NULL AS VARCHAR(20)) AS suggested_path,
    CAST(NULL AS VARCHAR(150)) AS suggested_winner_teamname,
    CAST(NULL AS VARCHAR(20)) AS suggested_match_score,

    CAST(NULL AS BIT) AS winner_correct,
    CAST(NULL AS BIT) AS score_correct,
    CAST(NULL AS BIT) AS path_correct,

    CAST(NULL AS VARCHAR(500)) AS dfs_note,

    @prior_weight AS prior_weight
INTO #output_rows
FROM #smoothed s
CROSS APPLY
(
    SELECT
        ISNULL(s.raw_bayes_p_2_0, 0)
        + ISNULL(s.raw_bayes_p_2_1, 0)
        + ISNULL(s.raw_bayes_p_1_2, 0)
        + ISNULL(s.raw_bayes_p_0_2, 0) AS path_prob_total
) path_total;


/* ============================================================
   9. Suggested path
   ============================================================ */

UPDATE #output_rows
SET suggested_path =
    CASE
        WHEN bayes_p_2_0 >= bayes_p_2_1
         AND bayes_p_2_0 >= bayes_p_1_2
         AND bayes_p_2_0 >= bayes_p_0_2
            THEN '2-0'

        WHEN bayes_p_2_1 >= bayes_p_2_0
         AND bayes_p_2_1 >= bayes_p_1_2
         AND bayes_p_2_1 >= bayes_p_0_2
            THEN '2-1'

        WHEN bayes_p_1_2 >= bayes_p_2_0
         AND bayes_p_1_2 >= bayes_p_2_1
         AND bayes_p_1_2 >= bayes_p_0_2
            THEN '1-2'

        ELSE '0-2'
    END;


/* ============================================================
   10. Winner / score / accuracy
   ============================================================ */

UPDATE #output_rows
SET
    suggested_winner_teamname =
        CASE
            WHEN suggested_path IN ('2-0', '2-1') THEN teamname
            ELSE opponent_teamname
        END,

    suggested_match_score =
        CASE
            WHEN suggested_path IN ('2-0', '0-2') THEN '2-0'
            ELSE '2-1'
        END;


UPDATE #output_rows
SET
    winner_correct =
        CASE
            WHEN suggested_path IN ('2-0', '2-1') AND actual_won_series = 1 THEN CAST(1 AS BIT)
            WHEN suggested_path IN ('1-2', '0-2') AND actual_won_series = 0 THEN CAST(1 AS BIT)
            ELSE CAST(0 AS BIT)
        END,

    score_correct =
        CASE
            WHEN 
                CASE
                    WHEN suggested_path IN ('2-0', '0-2') THEN '2-0'
                    ELSE '2-1'
                END
                =
                CASE
                    WHEN actual_series_result IN ('2-0', '0-2') THEN '2-0'
                    ELSE '2-1'
                END
            THEN CAST(1 AS BIT)
            ELSE CAST(0 AS BIT)
        END,

    path_correct =
        CASE
            WHEN suggested_path = actual_series_result THEN CAST(1 AS BIT)
            ELSE CAST(0 AS BIT)
        END;


UPDATE #output_rows
SET dfs_note =
    CASE
        WHEN sample_type = 'League Prior Only'
            THEN 'Not enough similar history. Treat as low confidence.'
        WHEN similar_sample < 8
            THEN 'Thin sample. Use as directional only.'
        WHEN suggested_path = '2-0'
            THEN 'Sweep path supported. Strong 4-stack candidate if projections agree.'
        WHEN suggested_path = '2-1'
            THEN 'Win path supported, but more likely extended series.'
        WHEN suggested_path = '1-2'
            THEN 'Competitive loss profile. Consider one-off or small secondary exposure.'
        ELSE 'Weak path. Avoid heavy stacks unless ownership/projection creates leverage.'
    END;


/* ============================================================
   11. Merge into backtest table
   ============================================================ */

MERGE dbo.lol_bayes_prediction_backtest AS tgt
USING #output_rows AS src
    ON tgt.target_series_id = src.target_series_id
    AND LOWER(LTRIM(RTRIM(tgt.teamname))) = LOWER(LTRIM(RTRIM(src.teamname)))
    AND LOWER(LTRIM(RTRIM(tgt.opponent_teamname))) = LOWER(LTRIM(RTRIM(src.opponent_teamname)))
    AND tgt.prediction_source = 'historical_point_in_time_bayes'
    AND tgt.prior_weight = src.prior_weight

WHEN MATCHED THEN
    UPDATE SET
        tgt.league = src.league,
        tgt.season = src.season,
        tgt.target_series_date = src.target_series_date,

        tgt.actual_series_result = src.actual_series_result,
        tgt.actual_won_series = src.actual_won_series,
        tgt.actual_game_wins = src.actual_game_wins,
        tgt.actual_game_losses = src.actual_game_losses,

        tgt.team_strength_bucket = src.team_strength_bucket,
        tgt.opponent_strength_bucket = src.opponent_strength_bucket,
        tgt.strength_matchup_bucket = src.strength_matchup_bucket,

        tgt.team_strength_sample_label = src.team_strength_sample_label,
        tgt.opponent_strength_sample_label = src.opponent_strength_sample_label,

        tgt.team_prior_series_count = src.team_prior_series_count,
        tgt.opponent_prior_series_count = src.opponent_prior_series_count,

        tgt.team_smoothed_prior_series_win_rate = src.team_smoothed_prior_series_win_rate,
        tgt.opponent_smoothed_prior_series_win_rate = src.opponent_smoothed_prior_series_win_rate,
        tgt.smoothed_strength_gap = src.smoothed_strength_gap,

        tgt.mid_lane_matchup_bucket = src.mid_lane_matchup_bucket,
        tgt.bot_lane_matchup_bucket = src.bot_lane_matchup_bucket,
        tgt.sup_lane_matchup_bucket = src.sup_lane_matchup_bucket,
        tgt.top_lane_matchup_bucket = src.top_lane_matchup_bucket,
        tgt.jng_lane_matchup_bucket = src.jng_lane_matchup_bucket,

        tgt.team_mid_strength = src.team_mid_strength,
        tgt.opponent_mid_strength = src.opponent_mid_strength,
        tgt.team_bot_strength = src.team_bot_strength,
        tgt.opponent_bot_strength = src.opponent_bot_strength,
        tgt.team_sup_strength = src.team_sup_strength,
        tgt.opponent_sup_strength = src.opponent_sup_strength,

        tgt.team_mid_dk_index = src.team_mid_dk_index,
        tgt.opponent_mid_dk_index = src.opponent_mid_dk_index,
        tgt.team_bot_dk_index = src.team_bot_dk_index,
        tgt.opponent_bot_dk_index = src.opponent_bot_dk_index,
        tgt.team_sup_dk_index = src.team_sup_dk_index,
        tgt.opponent_sup_dk_index = src.opponent_sup_dk_index,

        tgt.sample_type = src.sample_type,
        tgt.similar_sample = src.similar_sample,

        tgt.bayes_win_pct = src.bayes_win_pct,
        tgt.bayes_p_2_0 = src.bayes_p_2_0,
        tgt.bayes_p_2_1 = src.bayes_p_2_1,
        tgt.bayes_p_1_2 = src.bayes_p_1_2,
        tgt.bayes_p_0_2 = src.bayes_p_0_2,

        tgt.suggested_path = src.suggested_path,
        tgt.suggested_winner_teamname = src.suggested_winner_teamname,
        tgt.suggested_match_score = src.suggested_match_score,

        tgt.winner_correct = src.winner_correct,
        tgt.score_correct = src.score_correct,
        tgt.path_correct = src.path_correct,

        tgt.dfs_note = src.dfs_note,

        tgt.updated_at = SYSUTCDATETIME()

WHEN NOT MATCHED THEN
    INSERT
    (
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

        team_strength_bucket,
        opponent_strength_bucket,
        strength_matchup_bucket,

        team_strength_sample_label,
        opponent_strength_sample_label,

        team_prior_series_count,
        opponent_prior_series_count,

        team_smoothed_prior_series_win_rate,
        opponent_smoothed_prior_series_win_rate,
        smoothed_strength_gap,

        mid_lane_matchup_bucket,
        bot_lane_matchup_bucket,
        sup_lane_matchup_bucket,
        top_lane_matchup_bucket,
        jng_lane_matchup_bucket,

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

        sample_type,
        similar_sample,

        bayes_win_pct,
        bayes_p_2_0,
        bayes_p_2_1,
        bayes_p_1_2,
        bayes_p_0_2,

        suggested_path,
        suggested_winner_teamname,
        suggested_match_score,

        winner_correct,
        score_correct,
        path_correct,

        dfs_note,

        prediction_source,
        prior_weight
    )
    VALUES
    (
        src.target_series_id,
        src.league,
        src.season,
        src.target_series_date,

        src.teamname,
        src.opponent_teamname,

        src.actual_series_result,
        src.actual_won_series,
        src.actual_game_wins,
        src.actual_game_losses,

        src.team_strength_bucket,
        src.opponent_strength_bucket,
        src.strength_matchup_bucket,

        src.team_strength_sample_label,
        src.opponent_strength_sample_label,

        src.team_prior_series_count,
        src.opponent_prior_series_count,

        src.team_smoothed_prior_series_win_rate,
        src.opponent_smoothed_prior_series_win_rate,
        src.smoothed_strength_gap,

        src.mid_lane_matchup_bucket,
        src.bot_lane_matchup_bucket,
        src.sup_lane_matchup_bucket,
        src.top_lane_matchup_bucket,
        src.jng_lane_matchup_bucket,

        src.team_mid_strength,
        src.opponent_mid_strength,
        src.team_bot_strength,
        src.opponent_bot_strength,
        src.team_sup_strength,
        src.opponent_sup_strength,

        src.team_mid_dk_index,
        src.opponent_mid_dk_index,
        src.team_bot_dk_index,
        src.opponent_bot_dk_index,
        src.team_sup_dk_index,
        src.opponent_sup_dk_index,

        src.sample_type,
        src.similar_sample,

        src.bayes_win_pct,
        src.bayes_p_2_0,
        src.bayes_p_2_1,
        src.bayes_p_1_2,
        src.bayes_p_0_2,

        src.suggested_path,
        src.suggested_winner_teamname,
        src.suggested_match_score,

        src.winner_correct,
        src.score_correct,
        src.path_correct,

        src.dfs_note,

        'historical_point_in_time_bayes',
        src.prior_weight
    );


/* ============================================================
   12. Quick output
   ============================================================ */

SELECT
    COUNT(*) AS backtest_rows,
    MIN(target_series_date) AS first_date,
    MAX(target_series_date) AS last_date
FROM dbo.lol_bayes_prediction_backtest
WHERE prediction_source = 'historical_point_in_time_bayes';