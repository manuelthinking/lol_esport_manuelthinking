USE lol_esports;
GO

TRUNCATE TABLE dbo.lol_matchup_lane_edges_pit_snapshot;

INSERT INTO dbo.lol_matchup_lane_edges_pit_snapshot
SELECT *
FROM dbo.vw_lol_matchup_lane_edges_pit_v1;
GO