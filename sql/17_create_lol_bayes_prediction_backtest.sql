/* ============================================================
   LoL Bayesian Prediction Backtest Table

   Purpose:
     Store historical point-in-time Bayesian predictions.

   This table answers:
     "What would the model have predicted before this match,
      using only data available before that match?"

   Source for population:
     dbo.vw_lol_bayes_strength_matchups_point_in_time

   Grain:
     one row per historical series / team prediction

   Example:
     BLG vs TES creates two rows:
       BLG prediction row
       TES prediction row

   Important:
     This is a historical backtest table.
     Upcoming slate predictions are tracked separately in:
       dbo.lol_bayes_prediction_tracking
   ============================================================ */

IF OBJECT_ID('dbo.lol_bayes_prediction_backtest', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.lol_bayes_prediction_backtest
    (
        backtest_id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,

        -- Historical target series
        target_series_id VARCHAR(100) NOT NULL,
        league VARCHAR(20) NULL,
        season INT NULL,
        target_series_date DATE NOT NULL,

        -- Team context
        teamname VARCHAR(150) NOT NULL,
        opponent_teamname VARCHAR(150) NOT NULL,

        -- Actual result from this team's perspective
        actual_series_result VARCHAR(20) NULL,
        actual_won_series BIT NULL,
        actual_game_wins INT NULL,
        actual_game_losses INT NULL,

        -- Point-in-time team strength context
        team_strength_bucket VARCHAR(50) NULL,
        opponent_strength_bucket VARCHAR(50) NULL,
        strength_matchup_bucket VARCHAR(100) NULL,

        team_strength_sample_label VARCHAR(50) NULL,
        opponent_strength_sample_label VARCHAR(50) NULL,

        team_prior_series_count INT NULL,
        opponent_prior_series_count INT NULL,

        team_smoothed_prior_series_win_rate FLOAT NULL,
        opponent_smoothed_prior_series_win_rate FLOAT NULL,
        smoothed_strength_gap FLOAT NULL,

        -- Point-in-time lane context
        mid_lane_matchup_bucket VARCHAR(100) NULL,
        bot_lane_matchup_bucket VARCHAR(100) NULL,
        sup_lane_matchup_bucket VARCHAR(100) NULL,

        top_lane_matchup_bucket VARCHAR(100) NULL,
        jng_lane_matchup_bucket VARCHAR(100) NULL,

        team_mid_strength VARCHAR(50) NULL,
        opponent_mid_strength VARCHAR(50) NULL,
        team_bot_strength VARCHAR(50) NULL,
        opponent_bot_strength VARCHAR(50) NULL,
        team_sup_strength VARCHAR(50) NULL,
        opponent_sup_strength VARCHAR(50) NULL,

        team_mid_dk_index FLOAT NULL,
        opponent_mid_dk_index FLOAT NULL,
        team_bot_dk_index FLOAT NULL,
        opponent_bot_dk_index FLOAT NULL,
        team_sup_dk_index FLOAT NULL,
        opponent_sup_dk_index FLOAT NULL,

        -- Bayesian sample selection
        sample_type VARCHAR(100) NULL,
        similar_sample INT NULL,

        -- Bayesian probabilities
        bayes_win_pct FLOAT NULL,
        bayes_p_2_0 FLOAT NULL,
        bayes_p_2_1 FLOAT NULL,
        bayes_p_1_2 FLOAT NULL,
        bayes_p_0_2 FLOAT NULL,

        -- Suggested prediction
        suggested_path VARCHAR(20) NULL,
        suggested_winner_teamname VARCHAR(150) NULL,
        suggested_match_score VARCHAR(20) NULL,

        -- Accuracy fields
        winner_correct BIT NULL,
        score_correct BIT NULL,
        path_correct BIT NULL,

        -- Helpful notes
        dfs_note VARCHAR(500) NULL,

        -- Metadata
        prediction_source VARCHAR(100) NOT NULL DEFAULT 'historical_point_in_time_bayes',
        prior_weight FLOAT NOT NULL DEFAULT 10,

        created_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2(0) NULL
    );
END;
GO


/* ============================================================
   Unique key:
     Prevent duplicate backtest rows if the population script
     is rerun.
   ============================================================ */

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE name = 'ux_lol_bayes_prediction_backtest_series_team'
      AND object_id = OBJECT_ID('dbo.lol_bayes_prediction_backtest')
)
BEGIN
    CREATE UNIQUE INDEX ux_lol_bayes_prediction_backtest_series_team
    ON dbo.lol_bayes_prediction_backtest
    (
        target_series_id,
        teamname,
        opponent_teamname,
        prediction_source,
        prior_weight
    );
END;
GO


/* ============================================================
   Lookup index:
     Review historical predictions by date/league.
   ============================================================ */

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE name = 'ix_lol_bayes_prediction_backtest_date'
      AND object_id = OBJECT_ID('dbo.lol_bayes_prediction_backtest')
)
BEGIN
    CREATE INDEX ix_lol_bayes_prediction_backtest_date
    ON dbo.lol_bayes_prediction_backtest
    (
        target_series_date,
        league,
        season
    );
END;
GO


/* ============================================================
   Accuracy index:
     Used for backtest dashboard and accuracy reviews.
   ============================================================ */

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE name = 'ix_lol_bayes_prediction_backtest_accuracy'
      AND object_id = OBJECT_ID('dbo.lol_bayes_prediction_backtest')
)
BEGIN
    CREATE INDEX ix_lol_bayes_prediction_backtest_accuracy
    ON dbo.lol_bayes_prediction_backtest
    (
        league,
        season,
        sample_type,
        winner_correct,
        score_correct,
        suggested_path
    );
END;
GO