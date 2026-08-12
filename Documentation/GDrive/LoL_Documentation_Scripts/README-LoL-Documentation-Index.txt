# LoL Documentation Index

Folder target:
C:\DailyDFS\LoL\Documentation

Included documentation files:
1. Script-build_lol_top_lineups.txt
2. Script-build_lol_team_series_profiles.txt
3. Script-build_lol_team_series_results.txt
4. Script-build_lol_team_game_stats.txt
5. Script-enrich_dk_lol_lineups_from_slate.txt
6. Script-transform_dk_lol_lineups.txt
7. Script-ingest_dk_lol_contest_standings.txt
8. Script-build_manual_starters_from_dk.txt

Current connected flow:

Pre-lock slate workflow:
DK slate CSV
    -> Script-build_manual_starters_from_dk
    -> manual_starters.csv
    -> manual starter review
    -> Script-build_lol_top_lineups
    -> lineup CSVs

Historical profile workflow:
Oracle Elixir CSV
    -> Script-build_lol_team_game_stats
    -> dbo.lol_team_game_stats
    -> Script-build_lol_team_series_results
    -> dbo.lol_team_series_results
    -> Script-build_lol_team_series_profiles
    -> dbo.lol_team_series_profiles
    -> Script-build_lol_top_lineups

Post-contest results workflow:
DK contest standings ZIP
    -> Script-ingest_dk_lol_contest_standings
    -> raw.dk_lol_contest_standings
    -> raw.dk_lol_player_ownership
    -> Script-transform_dk_lol_lineups
    -> lol.fact_lineup_result
    -> lol.fact_lineup_player
    -> Script-enrich_dk_lol_lineups_from_slate
    -> contest backtesting / ownership / stack analysis
