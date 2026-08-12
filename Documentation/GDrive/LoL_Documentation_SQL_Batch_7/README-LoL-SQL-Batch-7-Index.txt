# LoL SQL Documentation Batch 7 Index

Folder target:
C:\DailyDFS\LoL\Documentation

Included documentation files:
1. SQL-31_create_vw_lol_player_lane_power_rating_pit_v1.txt
2. SQL-33_create_vw_lol_matchup_lane_edge_summary_pit_v1.txt
3. SQL-34_create_vw_lol_bayes_lane_power_backtest_pit_v1.txt
4. SQL-35_create_vw_lol_bayes_lane_power_backtest_summary_pit_v1.txt

Batch 7 SQL flow map:

Point-in-time lane-power chain:
dbo.vw_lol_bayes_strength_matchups_point_in_time
dbo.fact_lol_player_game
    -> dbo.vw_lol_player_lane_power_rating_pit_v1
    -> dbo.vw_lol_matchup_lane_edges_pit_v1   MISSING FROM THIS BATCH, likely file 32
    -> dbo.vw_lol_matchup_lane_edge_summary_pit_v1
    -> dbo.vw_lol_bayes_lane_power_backtest_pit_v1
    -> dbo.vw_lol_bayes_lane_power_backtest_summary_pit_v1

Important cleanup notes from this batch:
1. File 32 appears to be missing. File 33 depends on dbo.vw_lol_matchup_lane_edges_pit_v1, which is likely created by 32_create_vw_lol_matchup_lane_edges_pit_v1.sql.
2. The PIT lane-power views are a better backtest design than the earlier historical/static lane-power views because they only use prior games.
3. 31 and 34 are hard-coded to season = 2026.
4. 31 requires at least 3 prior games, so early-season/new-player lanes can be missing or thin.
5. 34 uses team_smoothed_prior_series_win_rate as the Bayes win probability, not the fuller Bayes path probabilities from the backtest population table.
6. 34 and 35 are team-perspective views, not one row per match.
7. 35 does not group by league/date, so LPL and LCK behavior can be blended.
8. The PIT chain is historical/backtest-focused, not yet a live/upcoming-slate version.
