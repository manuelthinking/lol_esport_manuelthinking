USE lol_esports;
GO

IF OBJECT_ID('dbo.lol_bayes_lane_power_comparison_snapshot', 'U') IS NULL
BEGIN
    SELECT TOP 0
        *
    INTO dbo.lol_bayes_lane_power_comparison_snapshot
    FROM dbo.vw_lol_bayes_lane_power_comparison_v1;
END;
GO