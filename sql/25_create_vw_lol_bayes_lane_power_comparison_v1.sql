USE lol_esports;
GO

CREATE OR ALTER VIEW dbo.vw_lol_bayes_lane_power_comparison_v1 AS
WITH lane_signal AS (
    SELECT
        game_id,
        game_date,
        league,
        season,
        split,
        team,
        opponent,

        total_lane_edge,
        carry_lane_edge,
        main_carry_lane_edge,
        secondary_lane_edge,

        top_lane_edge,
        jng_lane_edge,
        mid_lane_edge,
        adc_lane_edge,
        sup_lane_edge,

        opponent_neutral_or_better_lanes,
        opponent_neutral_or_better_carry_lanes,

        lane_favorite_status,
        upset_resistance_score,
        upset_resistance_tier,
        upset_signal_label,

        favorite_stomp_warning_flag,
        underdog_live_flag,
        favorite_stomp_support_flag
    FROM dbo.vw_lol_upset_resistance_signal_v1
),
bayes AS (
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

        team_strength_bucket,
        opponent_strength_bucket,
        strength_matchup_bucket,

        team_strength_sample_label,
        opponent_strength_sample_label,

        team_prior_series_count,
        opponent_prior_series_count,

        team_prior_series_wins,
        team_prior_series_losses,
        opponent_prior_series_wins,
        opponent_prior_series_losses,

        team_raw_prior_series_win_rate,
        opponent_raw_prior_series_win_rate,
        team_smoothed_prior_series_win_rate,
        opponent_smoothed_prior_series_win_rate,
        smoothed_strength_gap,
        league_prior_rows,
        league_prior_win_rate,
        prior_weight,

        team_top_strength,
        team_jng_strength,
        team_mid_strength,
        team_bot_strength,
        team_sup_strength,

        opponent_top_strength,
        opponent_jng_strength,
        opponent_mid_strength,
        opponent_bot_strength,
        opponent_sup_strength,

        top_lane_matchup_bucket,
        jng_lane_matchup_bucket,
        mid_lane_matchup_bucket,
        bot_lane_matchup_bucket,
        sup_lane_matchup_bucket,

        team_top_dk_index,
        team_jng_dk_index,
        team_mid_dk_index,
        team_bot_dk_index,
        team_sup_dk_index,

        opponent_top_dk_index,
        opponent_jng_dk_index,
        opponent_mid_dk_index,
        opponent_bot_dk_index,
        opponent_sup_dk_index
    FROM dbo.vw_lol_bayes_strength_matchups_point_in_time
),
joined AS (
    SELECT
        ls.game_id,
        ls.game_date,
        ls.league,
        ls.season,
        ls.split,
        ls.team,
        ls.opponent,

        b.target_series_id,

        b.actual_series_result,
        b.actual_won_series,
        b.actual_game_wins,
        b.actual_game_losses,

        b.team_strength_bucket,
        b.opponent_strength_bucket,
        b.strength_matchup_bucket,

        b.team_strength_sample_label,
        b.opponent_strength_sample_label,

        b.team_prior_series_count,
        b.opponent_prior_series_count,

        b.team_prior_series_wins,
        b.team_prior_series_losses,
        b.opponent_prior_series_wins,
        b.opponent_prior_series_losses,

        b.team_raw_prior_series_win_rate,
        b.opponent_raw_prior_series_win_rate,

        b.team_smoothed_prior_series_win_rate AS bayes_win_pct,
        b.opponent_smoothed_prior_series_win_rate AS opponent_bayes_win_pct,
        b.smoothed_strength_gap,

        b.league_prior_rows,
        b.league_prior_win_rate,
        b.prior_weight,

        b.team_top_strength,
        b.team_jng_strength,
        b.team_mid_strength,
        b.team_bot_strength,
        b.team_sup_strength,

        b.opponent_top_strength,
        b.opponent_jng_strength,
        b.opponent_mid_strength,
        b.opponent_bot_strength,
        b.opponent_sup_strength,

        b.top_lane_matchup_bucket,
        b.jng_lane_matchup_bucket,
        b.mid_lane_matchup_bucket,
        b.bot_lane_matchup_bucket,
        b.sup_lane_matchup_bucket,

        b.team_top_dk_index,
        b.team_jng_dk_index,
        b.team_mid_dk_index,
        b.team_bot_dk_index,
        b.team_sup_dk_index,

        b.opponent_top_dk_index,
        b.opponent_jng_dk_index,
        b.opponent_mid_dk_index,
        b.opponent_bot_dk_index,
        b.opponent_sup_dk_index,

        ls.total_lane_edge,
        ls.carry_lane_edge,
        ls.main_carry_lane_edge,
        ls.secondary_lane_edge,

        ls.top_lane_edge,
        ls.jng_lane_edge,
        ls.mid_lane_edge,
        ls.adc_lane_edge,
        ls.sup_lane_edge,

        ls.opponent_neutral_or_better_lanes,
        ls.opponent_neutral_or_better_carry_lanes,

        ls.lane_favorite_status,
        ls.upset_resistance_score,
        ls.upset_resistance_tier,
        ls.upset_signal_label,

        ls.favorite_stomp_warning_flag,
        ls.underdog_live_flag,
        ls.favorite_stomp_support_flag
    FROM lane_signal ls
    LEFT JOIN bayes b
        ON ls.game_date = b.target_series_date
       AND ls.league = b.league
       AND ls.team = b.teamname
       AND ls.opponent = b.opponent_teamname
)
SELECT
    'bayes_vs_lane_power_v1' AS comparison_version,

    game_id,
    target_series_id,
    game_date,
    league,
    season,
    split,
    team,
    opponent,

    actual_series_result,
    actual_won_series,
    actual_game_wins,
    actual_game_losses,

    bayes_win_pct,
    opponent_bayes_win_pct,
    smoothed_strength_gap,

    team_strength_bucket,
    opponent_strength_bucket,
    strength_matchup_bucket,

    team_strength_sample_label,
    opponent_strength_sample_label,

    team_prior_series_count,
    opponent_prior_series_count,

    team_raw_prior_series_win_rate,
    opponent_raw_prior_series_win_rate,

    total_lane_edge,
    carry_lane_edge,
    main_carry_lane_edge,
    secondary_lane_edge,

    top_lane_edge,
    jng_lane_edge,
    mid_lane_edge,
    adc_lane_edge,
    sup_lane_edge,

    opponent_neutral_or_better_lanes,
    opponent_neutral_or_better_carry_lanes,

    lane_favorite_status,
    upset_resistance_score,
    upset_resistance_tier,
    upset_signal_label,

    favorite_stomp_warning_flag,
    underdog_live_flag,
    favorite_stomp_support_flag,

    CASE
        WHEN bayes_win_pct IS NULL THEN 'No Bayes Match'
        WHEN bayes_win_pct >= 0.65 THEN 'Bayes Strong Favorite'
        WHEN bayes_win_pct >= 0.55 THEN 'Bayes Lean Favorite'
        WHEN bayes_win_pct > 0.45 THEN 'Bayes Toss-Up'
        WHEN bayes_win_pct > 0.35 THEN 'Bayes Lean Underdog'
        ELSE 'Bayes Strong Underdog'
    END AS bayes_favorite_status,

    CASE
        WHEN bayes_win_pct IS NULL
            THEN 'Lane Signal Only'

        WHEN bayes_win_pct >= 0.65
         AND favorite_stomp_warning_flag = 1
            THEN 'Bayes Favorite / Lane Stomp Warning'

        WHEN bayes_win_pct >= 0.65
         AND favorite_stomp_support_flag = 1
            THEN 'Bayes Favorite / Lane Stomp Support'

        WHEN bayes_win_pct >= 0.55
         AND carry_lane_edge < 0
            THEN 'Bayes Favorite / Carry Lanes Questionable'

        WHEN bayes_win_pct <= 0.45
         AND underdog_live_flag = 1
            THEN 'Bayes Underdog / Lane Power Live'

        WHEN bayes_win_pct BETWEEN 0.45 AND 0.55
         AND ABS(carry_lane_edge) >= 10
            THEN 'Bayes Toss-Up / Lane Power Has Lean'

        ELSE 'Bayes and Lane Signal Aligned or Neutral'
    END AS bayes_lane_alignment_label,

    CASE
        WHEN bayes_win_pct >= 0.65
         AND favorite_stomp_warning_flag = 1
            THEN 1
        ELSE 0
    END AS bayes_overconfidence_warning_flag,

    CASE
        WHEN bayes_win_pct <= 0.45
         AND underdog_live_flag = 1
            THEN 1
        ELSE 0
    END AS bayes_possible_upset_signal_flag,

    CASE
        WHEN bayes_win_pct BETWEEN 0.45 AND 0.55
         AND ABS(carry_lane_edge) >= 10
            THEN 1
        ELSE 0
    END AS lane_power_breaks_bayes_tie_flag,

    CASE
        WHEN bayes_win_pct IS NULL THEN NULL
        WHEN bayes_win_pct >= 0.50 THEN 1
        ELSE 0
    END AS bayes_predicted_win_flag,

    CASE
        WHEN carry_lane_edge >= 5 THEN 1
        WHEN carry_lane_edge <= -5 THEN 0
        ELSE NULL
    END AS lane_power_predicted_win_flag,

    CASE
        WHEN bayes_win_pct IS NULL OR actual_won_series IS NULL THEN NULL
        WHEN bayes_win_pct >= 0.50 AND actual_won_series = 1 THEN 1
        WHEN bayes_win_pct < 0.50 AND actual_won_series = 0 THEN 1
        ELSE 0
    END AS bayes_winner_correct_flag,

    CASE
        WHEN actual_won_series IS NULL THEN NULL
        WHEN carry_lane_edge >= 5 AND actual_won_series = 1 THEN 1
        WHEN carry_lane_edge <= -5 AND actual_won_series = 0 THEN 1
        WHEN carry_lane_edge > -5 AND carry_lane_edge < 5 THEN NULL
        ELSE 0
    END AS lane_power_winner_correct_flag
FROM joined;
GO