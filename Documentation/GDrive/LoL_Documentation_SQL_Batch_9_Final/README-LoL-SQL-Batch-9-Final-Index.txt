# LoL SQL Documentation Batch 9 Final Index

Folder target:
C:\DailyDFS\LoL\Documentation

Included documentation files:
1. SQL-42_create_vw_lol_team_overview_lane_power_signal_v1.txt
2. SQL-43_create_vw_lol_slate_lane_power_signal_live_v1.txt
3. SQL-bayesian_training_view.txt
4. SQL-league_bayesian_priors.txt
5. SQL-lol_bayes_matchup_training.txt
6. SQL-vw_lol_series_player_stats.txt

Batch 9 SQL flow map:

Team Overview historical/PIT lane-power display:
dbo.lol_bayes_lane_power_backtest_pit_snapshot
    -> dbo.vw_lol_team_overview_lane_power_signal_v1
    -> Team Overview Lane Power display

Live slate lane-power:
dbo.dk_lol_slate_player
dbo.lol_player_lane_ratings
dbo.vw_lol_player_lane_power_rating_v1
    -> dbo.vw_lol_slate_lane_power_signal_live_v1
    -> Team Overview / Command Center live slate lane-power review

Legacy Bayes physical-table flow:
dbo.lol_team_series_results
dbo.fact_lol_player_game
    -> dbo.vw_lol_series_player_stats
    -> lol_bayes_matchup_training.sql
    -> dbo.lol_bayes_matchup_training
    -> dbo.vw_lol_bayes_matchup_training
    -> dbo.vw_lol_bayes_league_priors

Important cleanup notes from this final batch:
1. vw_lol_series_player_stats appears to be the real implementation that should replace the earlier template 02_create_vw_lol_series_player_stats.sql.
2. The unnumbered Bayes files appear to be part of an older/legacy physical-table Bayes flow. Keep them only if still used; otherwise archive them separately.
3. 43_create_vw_lol_slate_lane_power_signal_live_v1.sql is the true live slate lane-power view, but it picks one player per team/lane by highest salary rather than using manual starters.
4. 43 has Bayes placeholder fields as NULL, so it is not yet a full live Bayes + Lane Power combined view.
5. 43 and several upstream lane-power files are hard-coded to season = 2026.
6. 42 reads the PIT backtest snapshot, so it can be stale if the snapshot refresh chain has not been run.
7. 42 is app-facing but historical/snapshot-based unless current-slate rows are represented in the snapshot.
8. Recommended cleanup:
   - Replace old 02 template with the real vw_lol_series_player_stats file.
   - Decide whether the legacy Bayes physical-table flow should remain active.
   - Update the live lane-power view to use manual starters or starter history instead of salary pick.
   - Create a live Bayes + Lane Power combined view with real bayes_win_pct and adjusted_win_pct.
