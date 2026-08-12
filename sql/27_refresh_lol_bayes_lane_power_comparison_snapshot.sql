USE lol_esports;
GO

TRUNCATE TABLE dbo.lol_bayes_lane_power_comparison_snapshot;

INSERT INTO dbo.lol_bayes_lane_power_comparison_snapshot
SELECT *
FROM dbo.vw_lol_bayes_lane_power_comparison_v1;
GO