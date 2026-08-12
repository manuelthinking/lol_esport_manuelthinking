# LoL SQL Documentation Batch 1 Index

Folder target:
C:\DailyDFS\LoL\Documentation

Included documentation files:
1. SQL-01_create_lol_bayes_matchup_training.txt
2. SQL-02_create_vw_lol_series_player_stats.txt
3. SQL-04_create_vw_lol_team_strength_bucket.txt
4. SQL-05_create_vw_lol_team_strength_matchups.txt
5. SQL-06_create_vw_lol_lane_strength_bucket.txt

Batch 1 SQL flow map:

Historical team series flow:
dbo.lol_team_series_results
    -> dbo.vw_lol_team_strength_bucket
    -> dbo.vw_lol_team_strength_matchups
    -> later Bayes strength matchup views

Historical lane/player flow:
dbo.fact_lol_player_game
    -> dbo.vw_lol_lane_strength_bucket
    -> later Bayes lane matchup / lane power views

Bayes training table design:
dbo.vw_lol_series_player_stats
    -> population script needed
    -> dbo.lol_bayes_matchup_training

Important notes from this batch:
1. 02_create_vw_lol_series_player_stats.sql is a template and still references dbo.YOUR_RAW_SERIES_PLAYER_TABLE_HERE.
2. 05_create_vw_lol_team_strength_matchups.sql is hard-coded to year = 2026.
3. 06_create_vw_lol_lane_strength_bucket.sql is hard-coded to season = 2026.
4. 05 joins to team strength buckets without split even though 04 creates strength buckets by split.
5. 01 drops and recreates dbo.lol_bayes_matchup_training, so do not run it casually after the table is populated.
