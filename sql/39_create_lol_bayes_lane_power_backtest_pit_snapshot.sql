USE lol_esports;
GO

IF OBJECT_ID('dbo.lol_bayes_lane_power_backtest_pit_snapshot', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.lol_bayes_lane_power_backtest_pit_snapshot (
        backtest_version varchar(50) NOT NULL,
        target_series_id nvarchar(255) NULL,
        game_date date NULL,
        league nvarchar(50) NULL,
        season int NULL,
        team nvarchar(255) NULL,
        opponent nvarchar(255) NULL,

        actual_series_result nvarchar(50) NULL,
        actual_won_series int NULL,
        actual_game_wins int NULL,
        actual_game_losses int NULL,

        bayes_win_pct float NULL,
        opponent_bayes_win_pct float NULL,
        smoothed_strength_gap float NULL,

        team_strength_bucket varchar(50) NULL,
        opponent_strength_bucket varchar(50) NULL,
        strength_matchup_bucket varchar(100) NULL,

        team_prior_series_count int NULL,
        opponent_prior_series_count int NULL,

        lane_rows int NULL,
        rated_lane_rows int NULL,

        top_lane_edge float NULL,
        jng_lane_edge float NULL,
        mid_lane_edge float NULL,
        adc_lane_edge float NULL,
        sup_lane_edge float NULL,

        total_lane_edge float NULL,
        carry_lane_edge float NULL,
        main_carry_lane_edge float NULL,
        secondary_lane_edge float NULL,

        positive_carry_edge_lanes int NULL,
        negative_carry_edge_lanes int NULL,

        opponent_neutral_or_better_lanes int NULL,
        opponent_neutral_or_better_carry_lanes int NULL,

        min_team_prior_games int NULL,
        min_opponent_prior_games int NULL,
        avg_team_prior_games float NULL,
        avg_opponent_prior_games float NULL,

        total_lane_edge_tier varchar(100) NULL,
        carry_lane_edge_tier varchar(100) NULL,

        bayes_predicted_win_flag int NULL,
        lane_power_predicted_win_flag int NULL,

        bayes_favorite_status varchar(100) NULL,
        lane_favorite_status varchar(100) NULL,

        upset_resistance_score int NULL,
        upset_resistance_tier varchar(100) NULL,

        bayes_lane_alignment_label varchar(150) NULL,

        bayes_overconfidence_warning_flag int NULL,
        bayes_possible_upset_signal_flag int NULL,
        lane_power_breaks_bayes_tie_flag int NULL,
        favorite_stomp_support_flag int NULL,

        bayes_winner_correct_flag int NULL,
        lane_power_winner_correct_flag int NULL,

        refreshed_at datetime2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
GO