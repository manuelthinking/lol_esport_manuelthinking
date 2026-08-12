# LoL Documentation App Scripts Index

Folder target:
C:\DailyDFS\LoL\Documentation

Included documentation files:
1. App-app_lol_command_center.txt
2. App-app_lol_lineup_builder.txt
3. App-app_lol_playbook.txt
4. App-app_lol_player_matchups.txt
5. App-app_lol_slate_review.txt
6. App-app_lol_team_overview.txt

App-level workflow map:

Daily pre-lock control flow:
app_lol_command_center
    -> Data Health / Exceptions / Starter Review
    -> app_lol_team_overview
    -> suggested scenarios / team stack reads
    -> app_lol_lineup_builder
    -> lineup CSVs

Optional playbook CSV review:
build_lol_playbook.py
    -> lol_playbook.csv
    -> app_lol_playbook

Optional matchup research:
dbo.fact_lol_player_lane_matchup
    -> app_lol_player_matchups
    -> manual lane/player decisions

Post-contest review:
ingest_dk_lol_contest_standings.py
    -> transform_dk_lol_lineups.py
    -> enrich_dk_lol_lineups_from_slate.py
    -> app_lol_slate_review
    -> app_lol_command_center Contest Review / Top 1% Lineups

Important app dependency notes:
- app_lol_command_center depends on engine.jobs for Daily Commands.
- app_lol_lineup_builder imports functions from scripts.build_lol_top_lineups.
- app_lol_team_overview has many SQL view dependencies and some season-specific logic.
- app_lol_player_matchups reads dbo.fact_lol_player_lane_matchup, which should be connected to a documented source script/view.
