# LoL SQL Documentation Batch 5 Index

Folder target:
C:\DailyDFS\LoL\Documentation

Included documentation files:
1. SQL-21_create_vw_lol_player_lane_power_rating_v1.txt
2. SQL-22_create_vw_lol_matchup_lane_edges_v1.txt
3. SQL-23_create_vw_lol_matchup_lane_edge_summary_v1.txt
4. SQL-24_create_vw_lol_upset_resistance_signal_v1.txt
5. SQL-25_create_vw_lol_bayes_lane_power_comparison_v1.txt

Batch 5 SQL flow map:

Lane-power scoring chain:
dbo.fact_lol_player_game
    -> dbo.vw_lol_player_lane_power_base_v1
    -> dbo.vw_lol_player_lane_power_rating_v1
    -> dbo.vw_lol_matchup_lane_edges_v1
    -> dbo.vw_lol_matchup_lane_edge_summary_v1
    -> dbo.vw_lol_upset_resistance_signal_v1

Bayes vs lane-power comparison:
dbo.vw_lol_upset_resistance_signal_v1
dbo.vw_lol_bayes_strength_matchups_point_in_time
    -> dbo.vw_lol_bayes_lane_power_comparison_v1
    -> Team Overview Lane Power / Bayes comparison
    -> scenario decision support

Important cleanup notes from this batch:
1. Numbering still needs cleanup. The lane-power base file was previously also numbered 20, while ownership training is 20 and this rating file is 21. A clean sequence would be:
   - 20_create_vw_lol_ownership_training.sql
   - 21_create_vw_lol_player_lane_power_base_v1.sql
   - 22_create_vw_lol_player_lane_power_rating_v1.sql
   - 23_create_vw_lol_matchup_lane_edges_v1.sql
   - 24_create_vw_lol_matchup_lane_edge_summary_v1.sql
   - 25_create_vw_lol_upset_resistance_signal_v1.sql
   - 26_create_vw_lol_bayes_lane_power_comparison_v1.sql
2. 22_create_vw_lol_matchup_lane_edges_v1.sql is hard-coded to season = 2026.
3. The lane-power chain is currently historical/actual-game based, not a true upcoming-slate live signal chain.
4. The Bayes comparison join depends on exact game_date/team/opponent matching.
5. The Bayes comparison logic assumes bayes_win_pct is stored as a decimal from 0 to 1.
6. The lane-power winner flag uses carry_lane_edge only, not total lane edge. That should be backtested.
7. A live-slate version using DK slate teams and manual starters would make this more directly useful pre-lock.
