/* ============================================================
   LoL Bayesian Prediction Tracking Table

   Purpose:
     Save the Bayesian model's pre-result prediction for each
     slate matchup so we can evaluate it later against actuals.

   Important:
     This table should be populated BEFORE results are known.
     That gives us clean tracking and avoids backfitting.

   Grain:
     one row per slate / matchup / team prediction

   Example:
     BLG vs TES creates two rows:
       BLG predicted path: 2-0 / 2-1 / 1-2 / 0-2
       TES predicted path: 2-0 / 2-1 / 1-2 / 0-2
   ============================================================ */

IF OBJECT_ID('dbo.lol_bayes_prediction_tracking', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.lol_bayes_prediction_tracking
    (
        bayes_prediction_id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,

        -- Slate context
        slate_date DATE NOT NULL,
        slate_name VARCHAR(100) NOT NULL,
        game_info VARCHAR(200) NULL,

        -- Team context
        league VARCHAR(20) NULL,
        team_abbrev VARCHAR(50) NULL,
        teamname VARCHAR(150) NULL,
        opponent_abbrev VARCHAR(50) NULL,
        opponent_teamname VARCHAR(150) NULL,

        -- Model structure/context
        team_strength_bucket VARCHAR(50) NULL,
        opponent_strength_bucket VARCHAR(50) NULL,
        strength_matchup_bucket VARCHAR(100) NULL,

        mid_lane_matchup_bucket VARCHAR(100) NULL,
        bot_lane_matchup_bucket VARCHAR(100) NULL,
        sup_lane_matchup_bucket VARCHAR(100) NULL,

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
        suggested_winner_abbrev VARCHAR(50) NULL,
        suggested_match_score VARCHAR(20) NULL,

        -- Human-readable model note
        dfs_note VARCHAR(500) NULL,
        scenario_note VARCHAR(500) NULL,

        -- Actual results, filled later
        actual_winner_teamname VARCHAR(150) NULL,
        actual_winner_abbrev VARCHAR(50) NULL,
        actual_series_result VARCHAR(20) NULL,
        actual_team_result VARCHAR(20) NULL,

        winner_correct BIT NULL,
        score_correct BIT NULL,
        path_correct BIT NULL,

        -- Tracking metadata
        prediction_source VARCHAR(100) NOT NULL DEFAULT 'streamlit_bayes_strength',
        locked_before_results BIT NOT NULL DEFAULT 1,
        notes VARCHAR(1000) NULL,

        created_at DATETIME2(0) NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2(0) NULL
    );
END;
GO


/* ============================================================
   Unique key:
     Prevent duplicate saves for the same slate/team prediction.
   ============================================================ */

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE name = 'ux_lol_bayes_prediction_tracking_slate_team'
      AND object_id = OBJECT_ID('dbo.lol_bayes_prediction_tracking')
)
BEGIN
    CREATE UNIQUE INDEX ux_lol_bayes_prediction_tracking_slate_team
    ON dbo.lol_bayes_prediction_tracking
    (
        slate_date,
        slate_name,
        game_info,
        teamname,
        opponent_teamname,
        prediction_source
    );
END;
GO


/* ============================================================
   Lookup index:
     For reviewing one slate quickly.
   ============================================================ */

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE name = 'ix_lol_bayes_prediction_tracking_slate'
      AND object_id = OBJECT_ID('dbo.lol_bayes_prediction_tracking')
)
BEGIN
    CREATE INDEX ix_lol_bayes_prediction_tracking_slate
    ON dbo.lol_bayes_prediction_tracking
    (
        slate_date,
        slate_name,
        game_info
    );
END;
GO


/* ============================================================
   Accuracy review index:
     For later tracking dashboard queries.
   ============================================================ */

IF NOT EXISTS
(
    SELECT 1
    FROM sys.indexes
    WHERE name = 'ix_lol_bayes_prediction_tracking_accuracy'
      AND object_id = OBJECT_ID('dbo.lol_bayes_prediction_tracking')
)
BEGIN
    CREATE INDEX ix_lol_bayes_prediction_tracking_accuracy
    ON dbo.lol_bayes_prediction_tracking
    (
        slate_date,
        winner_correct,
        score_correct,
        sample_type
    );
END;
GO