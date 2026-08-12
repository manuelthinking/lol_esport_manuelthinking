# LoL Documentation Remaining Scripts Index

Folder target:
C:\DailyDFS\LoL\Documentation

Included documentation files:
1. Script-build_lane_matchups.txt
2. Script-build_player_games.txt
3. Script-ingest_oracle_elixir.txt

Updated historical Oracle flow:
Oracle Elixir Google Drive CSV or manual CSV
    -> Script-ingest_oracle_elixir
    -> raw.oracle_elixir_match_data_staging
    -> raw.oracle_elixir_latest_starters
    -> Script-build_player_games
    -> dbo.fact_lol_player_game
    -> Script-build_lane_matchups
    -> dbo.fact_lol_lane_matchup

Related richer team/series profile flow:
Oracle Elixir CSV
    -> Script-build_lol_team_game_stats
    -> dbo.lol_team_game_stats
    -> Script-build_lol_team_series_results
    -> dbo.lol_team_series_results
    -> Script-build_lol_team_series_profiles
    -> dbo.lol_team_series_profiles
    -> Script-build_lol_top_lineups

Important note:
There are currently two Oracle-derived historical chains:
1. raw staging JSON -> player game -> lane matchup
2. Oracle CSV -> team game stats -> team series results -> team series profiles

Both are useful, but later documentation should clarify whether both are required daily or whether one becomes the primary canonical pipeline.
