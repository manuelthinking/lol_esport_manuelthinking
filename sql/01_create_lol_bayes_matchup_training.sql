/* ============================================================
   LoL Bayesian Matchup Training Table
   Purpose:
     One row per team per historical series.

   This table will power:
     - Prior win rate
     - Similar matchup win rate
     - Bayesian-smoothed win probability
     - Later: P 2-0 / P 2-1 / P 1-2 / P 0-2

   Run in:
     lol_esports database
   ============================================================ */

SET NOCOUNT ON;

IF OBJECT_ID('dbo.lol_bayes_matchup_training', 'U') IS NOT NULL
BEGIN
    DROP TABLE dbo.lol_bayes_matchup_training;
END;
GO

CREATE TABLE dbo.lol_bayes_matchup_training
(
    bayes_matchup_id BIGINT IDENTITY(1,1) NOT NULL
        CONSTRAINT PK_lol_bayes_matchup_training PRIMARY KEY,

    -- Series identity
    series_id NVARCHAR(200) NOT NULL,
    series_date DATE NULL,
    season INT NULL,
    league NVARCHAR(50) NULL,

    -- Team side
    teamname NVARCHAR(100) NOT NULL,
    opponent_teamname NVARCHAR(100) NOT NULL,

    -- Result from this team's perspective
    series_result NVARCHAR(10) NOT NULL,
    won_series BIT NOT NULL,
    games_played INT NOT NULL,

    -- Team lane stats
    team_top_kills FLOAT NULL,
    team_jng_kills FLOAT NULL,
    team_mid_kills FLOAT NULL,
    team_bot_kills FLOAT NULL,
    team_sup_kills FLOAT NULL,

    team_top_assists FLOAT NULL,
    team_jng_assists FLOAT NULL,
    team_mid_assists FLOAT NULL,
    team_bot_assists FLOAT NULL,
    team_sup_assists FLOAT NULL,

    team_top_deaths FLOAT NULL,
    team_jng_deaths FLOAT NULL,
    team_mid_deaths FLOAT NULL,
    team_bot_deaths FLOAT NULL,
    team_sup_deaths FLOAT NULL,

    team_top_dk FLOAT NULL,
    team_jng_dk FLOAT NULL,
    team_mid_dk FLOAT NULL,
    team_bot_dk FLOAT NULL,
    team_sup_dk FLOAT NULL,

    -- Opponent lane stats
    opp_top_kills FLOAT NULL,
    opp_jng_kills FLOAT NULL,
    opp_mid_kills FLOAT NULL,
    opp_bot_kills FLOAT NULL,
    opp_sup_kills FLOAT NULL,

    opp_top_assists FLOAT NULL,
    opp_jng_assists FLOAT NULL,
    opp_mid_assists FLOAT NULL,
    opp_bot_assists FLOAT NULL,
    opp_sup_assists FLOAT NULL,

    opp_top_deaths FLOAT NULL,
    opp_jng_deaths FLOAT NULL,
    opp_mid_deaths FLOAT NULL,
    opp_bot_deaths FLOAT NULL,
    opp_sup_deaths FLOAT NULL,

    opp_top_dk FLOAT NULL,
    opp_jng_dk FLOAT NULL,
    opp_mid_dk FLOAT NULL,
    opp_bot_dk FLOAT NULL,
    opp_sup_dk FLOAT NULL,

    -- Lane edges: team minus opponent
    top_kill_edge FLOAT NULL,
    jng_kill_edge FLOAT NULL,
    mid_kill_edge FLOAT NULL,
    bot_kill_edge FLOAT NULL,
    sup_kill_edge FLOAT NULL,

    top_assist_edge FLOAT NULL,
    jng_assist_edge FLOAT NULL,
    mid_assist_edge FLOAT NULL,
    bot_assist_edge FLOAT NULL,
    sup_assist_edge FLOAT NULL,

    top_death_edge FLOAT NULL,
    jng_death_edge FLOAT NULL,
    mid_death_edge FLOAT NULL,
    bot_death_edge FLOAT NULL,
    sup_death_edge FLOAT NULL,

    top_dk_edge FLOAT NULL,
    jng_dk_edge FLOAT NULL,
    mid_dk_edge FLOAT NULL,
    bot_dk_edge FLOAT NULL,
    sup_dk_edge FLOAT NULL,

    -- Team-level summary edges
    team_kill_edge FLOAT NULL,
    team_assist_edge FLOAT NULL,
    team_death_edge FLOAT NULL,
    team_dk_edge FLOAT NULL,

    -- Optional later fields
    team_rating_score FLOAT NULL,
    opp_rating_score FLOAT NULL,
    team_rating_edge FLOAT NULL,

    -- Bucket fields for easier Bayesian grouping
    top_kill_bucket NVARCHAR(20) NULL,
    jng_kill_bucket NVARCHAR(20) NULL,
    mid_kill_bucket NVARCHAR(20) NULL,
    bot_kill_bucket NVARCHAR(20) NULL,
    sup_assist_bucket NVARCHAR(20) NULL,
    bot_dk_bucket NVARCHAR(20) NULL,
    team_rating_bucket NVARCHAR(20) NULL,

    created_at DATETIME2 NOT NULL
        CONSTRAINT DF_lol_bayes_matchup_training_created_at DEFAULT SYSUTCDATETIME()
);
GO

CREATE UNIQUE INDEX UX_lol_bayes_matchup_training_series_team
ON dbo.lol_bayes_matchup_training(series_id, teamname);
GO

CREATE INDEX IX_lol_bayes_matchup_training_league_team
ON dbo.lol_bayes_matchup_training(league, teamname, series_date);
GO

CREATE INDEX IX_lol_bayes_matchup_training_team_opp
ON dbo.lol_bayes_matchup_training(teamname, opponent_teamname, series_date);
GO

CREATE INDEX IX_lol_bayes_matchup_training_result
ON dbo.lol_bayes_matchup_training(league, series_result, won_series);
GO

CREATE INDEX IX_lol_bayes_matchup_training_edges
ON dbo.lol_bayes_matchup_training
(
    league,
    top_kill_bucket,
    mid_kill_bucket,
    bot_kill_bucket,
    sup_assist_bucket,
    bot_dk_bucket
);
GO