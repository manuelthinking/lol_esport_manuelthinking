# LoL SQL Documentation Batch 6 Index

Folder target:
C:\DailyDFS\LoL\Documentation

Included documentation files:
1. SQL-26_create_lol_bayes_lane_power_comparison_snapshot.txt
2. SQL-27_refresh_lol_bayes_lane_power_comparison_snapshot.txt
3. SQL-28_index_lol_bayes_lane_power_comparison_snapshot.txt
4. SQL-29_create_vw_lol_bayes_lane_power_backtest_summary_v1.txt
5. SQL-30_create_vw_lol_lane_power_warning_backtest_v1.txt

Batch 6 SQL flow map:

Bayes vs Lane Power comparison snapshot:
dbo.vw_lol_bayes_lane_power_comparison_v1
    -> 26_create_lol_bayes_lane_power_comparison_snapshot.sql
    -> dbo.lol_bayes_lane_power_comparison_snapshot
    -> 27_refresh_lol_bayes_lane_power_comparison_snapshot.sql
    -> 28_index_lol_bayes_lane_power_comparison_snapshot.sql

Backtest summaries:
dbo.lol_bayes_lane_power_comparison_snapshot
    -> dbo.vw_lol_bayes_lane_power_backtest_summary_v1
    -> dbo.vw_lol_lane_power_warning_backtest_v1

Important cleanup notes from this batch:
1. Refresh order matters: create snapshot table first, refresh it second, index it third, then query summary views.
2. 27_refresh_lol_bayes_lane_power_comparison_snapshot.sql truncates before insert. If the insert fails, the snapshot table can be left empty.
3. 26 and 27 use SELECT * from the source view. If the source view schema changes, the snapshot table can drift or refresh can fail.
4. Summary views read the snapshot table, not the live comparison view. If 27 is not run after upstream updates, the summaries are stale.
5. 29 summarizes team-perspective rows, not necessarily one row per match.
6. 30 assigns one priority warning type per row. Rows with multiple flags are bucketed by the first matching CASE branch.
7. Neither 29 nor 30 currently groups by league/date, so LPL and LCK behavior may be blended.
