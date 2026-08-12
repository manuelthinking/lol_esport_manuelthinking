USE lol_esports;
GO

IF OBJECT_ID('dbo.lol_matchup_lane_edges_pit_snapshot', 'U') IS NULL
BEGIN
    SELECT TOP 0
        *
    INTO dbo.lol_matchup_lane_edges_pit_snapshot
    FROM dbo.vw_lol_matchup_lane_edges_pit_v1;
END;
GO