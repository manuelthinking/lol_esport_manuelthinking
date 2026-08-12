# LoL SQL Documentation Batch 8 Index

Folder target:
C:\DailyDFS\LoL\Documentation

Included documentation files:
1. SQL-36_create_lol_matchup_lane_edges_pit_snapshot.txt
2. SQL-37_refresh_lol_matchup_lane_edges_pit_snapshot.txt
3. SQL-39_create_lol_bayes_lane_power_backtest_pit_snapshot.txt
4. SQL-40_refresh_lol_bayes_lane_power_backtest_pit_snapshot.txt
5. SQL-41_index_lol_bayes_lane_power_backtest_pit_snapshot.txt

Batch 8 SQL flow map:

PIT lane-edge snapshot:
dbo.vw_lol_matchup_lane_edges_pit_v1
    -> SQL-36 creates dbo.lol_matchup_lane_edges_pit_snapshot
    -> SQL-37 refreshes dbo.lol_matchup_lane_edges_pit_snapshot
    -> likely missing SQL-38 index file for lane-edge snapshot

PIT Bayes/Lane Power backtest snapshot:
dbo.vw_lol_bayes_strength_matchups_point_in_time
dbo.lol_matchup_lane_edges_pit_snapshot
    -> SQL-39 creates dbo.lol_bayes_lane_power_backtest_pit_snapshot
    -> SQL-40 refreshes dbo.lol_bayes_lane_power_backtest_pit_snapshot
    -> SQL-41 indexes dbo.lol_bayes_lane_power_backtest_pit_snapshot

Important cleanup notes from this batch:
1. File 38 appears to be missing. After 36/37, there is likely supposed to be an index file for dbo.lol_matchup_lane_edges_pit_snapshot.
2. File 36 depends on dbo.vw_lol_matchup_lane_edges_pit_v1, which was also missing from the prior batch and likely should be file 32.
3. Files 36 and 37 use SELECT * from dbo.vw_lol_matchup_lane_edges_pit_v1, so source view schema drift can break the snapshot refresh.
4. File 37 truncates before insert. If insert fails, dbo.lol_matchup_lane_edges_pit_snapshot can be left empty.
5. File 40 depends on file 37 having been run first; otherwise the PIT backtest snapshot can be stale or missing lane edges.
6. File 40 is hard-coded to season = 2026.
7. File 40 uses team_smoothed_prior_series_win_rate as bayes_win_pct, not the fuller Bayes path probability table.
8. File 39/41 do not create a unique index on target_series_id/team/opponent, so duplicate protection is not enforced structurally.
9. Recommended operational order:
   a. Create PIT lane-edge view, likely missing file 32.
   b. Run 36 create lane-edge snapshot.
   c. Run 37 refresh lane-edge snapshot.
   d. Run missing 38 index lane-edge snapshot if available.
   e. Run 39 create PIT backtest snapshot.
   f. Run 40 refresh PIT backtest snapshot.
   g. Run 41 index PIT backtest snapshot.
