# LoL SQL Documentation Batch 4 Index

Folder target:
C:\DailyDFS\LoL\Documentation

Included documentation files:
1. SQL-17_create_lol_bayes_prediction_backtest.txt
2. SQL-18_populate_lol_bayes_prediction_backtest.txt
3. SQL-19_create_vw_lol_bayes_prediction_backtest_match_level.txt
4. SQL-20_create_vw_lol_ownership_training.txt
5. SQL-21_create_vw_lol_player_lane_power_base_v1.txt

Batch 4 SQL flow map:

Point-in-time Bayes backtest:
dbo.vw_lol_bayes_strength_matchups_point_in_time
    -> 18_populate_lol_bayes_prediction_backtest.sql
    -> dbo.lol_bayes_prediction_backtest
    -> dbo.vw_lol_bayes_prediction_backtest_match_level
    -> Bayes model accuracy review / confidence calibration

Ownership training:
raw.dk_lol_player_ownership
dbo.dk_lol_slate_player
dbo.lol_player_lane_ratings
dbo.lol_manual_starters_history
dbo.lol_team_name_map
dbo.lol_bayes_prediction_backtest
    -> dbo.vw_lol_ownership_training
    -> ownership modeling / Command Center ownership review

Lane power base:
dbo.fact_lol_player_game
    -> dbo.vw_lol_player_lane_power_base_v1
    -> downstream lane-power signal views
    -> Team Overview Lane Power section

Important cleanup notes from this batch:
1. There are two uploaded files numbered 20. Recommend renaming 20_create_vw_lol_player_lane_power_base_v1.sql to 21_create_vw_lol_player_lane_power_base_v1.sql.
2. 18_populate_lol_bayes_prediction_backtest.sql is hard-coded to season = 2026.
3. 20_create_vw_lol_ownership_training.sql depends on lol_manual_starters_history columns that were missing from the original 09 table creation file.
4. 20_create_vw_lol_ownership_training.sql depends heavily on dbo.lol_team_name_map for Bayes matching.
5. 20_create_vw_lol_ownership_training.sql joins Bayes by slate_date = target_series_date, which can miss rows if DK slate date differs from actual match date.
6. 20_create_vw_lol_player_lane_power_base_v1.sql is hard-coded to season = 2026 and depends on fact_lol_player_game dk_points quality.
7. The Bayes backtest population chooses the max probability path; it does not yet apply the more cautious 2-0 vs 2-1 logic from the Streamlit scenario rules.
