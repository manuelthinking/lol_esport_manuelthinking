# LoL SQL Documentation Batch 3 Index

Folder target:
C:\DailyDFS\LoL\Documentation

Included documentation files:
1. SQL-12_create_vw_lol_team_strength_bucket_point_in_time.txt
2. SQL-13_create_vw_lol_team_strength_matchups_point_in_time.txt
3. SQL-14_create_vw_lol_lane_strength_bucket_point_in_time.txt
4. SQL-15_create_vw_lol_lane_strength_matchups_point_in_time.txt
5. SQL-16_create_vw_lol_bayes_strength_matchups_point_in_time.txt

Batch 3 SQL flow map:

Point-in-time team strength flow:
dbo.lol_team_series_results
    -> dbo.vw_lol_team_strength_bucket_point_in_time
    -> dbo.vw_lol_team_strength_matchups_point_in_time

Point-in-time lane strength flow:
dbo.lol_team_series_results + dbo.fact_lol_player_game
    -> dbo.vw_lol_lane_strength_bucket_point_in_time
    -> dbo.vw_lol_lane_strength_matchups_point_in_time

Combined point-in-time Bayes flow:
dbo.vw_lol_team_strength_matchups_point_in_time
dbo.vw_lol_lane_strength_matchups_point_in_time
    -> dbo.vw_lol_bayes_strength_matchups_point_in_time
    -> Bayes backtesting / confidence calibration

Important cleanup notes from this batch:
1. These files are a major improvement over the earlier non-point-in-time views because they avoid future-data leakage.
2. All core PIT views are still hard-coded to 2026.
3. The logic uses prior dates only, so earlier same-day series are excluded.
4. Lane strength still depends on dbo.fact_lol_player_game dk_points quality. If that table uses placeholder DK scoring, lane DK indexes may be imperfect.
5. The combined PIT Bayes view is a historical backtest source, not automatically a live/current-slate source.
6. A future live-slate PIT equivalent would help apply the same logic to upcoming slates.
