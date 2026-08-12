# LoL SQL Documentation Batch 2 Index

Folder target:
C:\DailyDFS\LoL\Documentation

Included documentation files:
1. SQL-07_create_vw_lol_lane_strength_matchups.txt
2. SQL-08_create_vw_lol_bayes_strength_matchups.txt
3. SQL-09_create_lol_manual_starters_history.txt
4. SQL-10_backfill_actual_starters_history.txt
5. SQL-11_create_lol_bayes_prediction_tracking.txt

Batch 2 SQL flow map:

Lane/Bayes strength flow:
dbo.fact_lol_player_game
    -> dbo.vw_lol_lane_strength_bucket
    -> dbo.vw_lol_lane_strength_matchups

dbo.lol_team_series_results
    -> dbo.vw_lol_team_strength_bucket
    -> dbo.vw_lol_team_strength_matchups

combined:
    -> dbo.vw_lol_bayes_strength_matchups
    -> app_lol_team_overview Bayesian Matchup Read
    -> scenario decisions / lineup builder inputs

Starter history flow:
manual_starters.csv
    -> starter snapshot save script still needed
    -> dbo.lol_manual_starters_history

dbo.fact_lol_player_game
    -> 10_backfill_actual_starters_history.sql
    -> dbo.lol_manual_starters_history actual_games records

Bayes prediction tracking flow:
app_lol_team_overview Bayesian Matchup Read
    -> save predictions before lock process still needed
    -> dbo.lol_bayes_prediction_tracking
    -> update actuals after results process still needed
    -> prediction accuracy review

Important cleanup notes from this batch:
1. 07_create_vw_lol_lane_strength_matchups.sql is hard-coded to year = 2026.
2. 07 depends on 06, which is also hard-coded to season = 2026.
3. 08 inherits season limitations and possible point-in-time leakage from upstream views.
4. 09_create_lol_manual_starters_history.sql does not create the extra columns that 10_backfill_actual_starters_history.sql expects.
5. 10_backfill_actual_starters_history.sql is hard-coded to season = 2026.
6. 10 sets is_starter = 1 for both starters and subs, using starter_role to distinguish them. This may confuse downstream logic.
7. 11_create_lol_bayes_prediction_tracking.sql creates a useful table, but save/update workflows are still needed.
