/* ============================================================
   League Bayesian Priors
   This gives baseline rates by league.
   ============================================================ */

IF OBJECT_ID('dbo.vw_lol_bayes_league_priors', 'V') IS NOT NULL
BEGIN
    DROP VIEW dbo.vw_lol_bayes_league_priors;
END;
GO

CREATE VIEW dbo.vw_lol_bayes_league_priors AS
SELECT
    league,
    COUNT(*) AS team_series_rows,
    AVG(CAST(won_series AS FLOAT)) AS league_win_rate,

    AVG(CASE WHEN series_result = '2-0' THEN 1.0 ELSE 0.0 END) AS league_p_2_0,
    AVG(CASE WHEN series_result = '2-1' THEN 1.0 ELSE 0.0 END) AS league_p_2_1,
    AVG(CASE WHEN series_result = '1-2' THEN 1.0 ELSE 0.0 END) AS league_p_1_2,
    AVG(CASE WHEN series_result = '0-2' THEN 1.0 ELSE 0.0 END) AS league_p_0_2
FROM dbo.lol_bayes_matchup_training
GROUP BY league;
GO