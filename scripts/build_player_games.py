import os
import json
import math
import numpy as np
import pandas as pd
import pyodbc
from dotenv import load_dotenv

load_dotenv()

DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")


def connect():
    conn_str = (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_DATABASE};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


def safe_int(v):
    try:
        if v is None or v == "" or pd.isna(v):
            return None
        return int(float(v))
    except Exception:
        return None


def safe_float(v):
    try:
        if v is None or v == "" or pd.isna(v):
            return None
        val = float(v)
        if math.isnan(val) or math.isinf(val):
            return None
        return val
    except Exception:
        return None


def clean_sql_value(v):
    if v is None:
        return None

    try:
        if pd.isna(v):
            return None
    except Exception:
        pass

    if isinstance(v, np.generic):
        v = v.item()

    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None

    return v


def calc_dk_points(row):
    """
    Simple starting LoL DK scoring placeholder:
    Kills = 3
    Assists = 2
    Deaths = -1

    We can expand this later for full DraftKings LoL scoring.
    """
    kills = row.get("kills") or 0
    deaths = row.get("deaths") or 0
    assists = row.get("assists") or 0

    return kills * 3 + assists * 2 - deaths


def main():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT DB_NAME()")
    print("Connected DB:", cursor.fetchone()[0])

    sql = """
        SELECT row_json
        FROM raw.oracle_elixir_match_data_staging
    """

    df = pd.read_sql(sql, conn)

    records = []

    for raw_json in df["row_json"]:
        row = json.loads(raw_json)

        position = str(row.get("position", "")).lower().strip()

        # Keep player rows only
        if position not in ["top", "jng", "mid", "bot", "sup"]:
            continue

        rec = {
            "game_id": row.get("gameid"),
            "league": row.get("league"),
            "season": safe_int(row.get("year")),
            "split": row.get("split"),
            "patch": row.get("patch"),

            "game_date": row.get("date"),
            "playoff_game": safe_int(row.get("playoffs")),

            "side": row.get("side"),
            "position": position,

            "player_name": row.get("playername"),
            "player_id": row.get("playerid"),

            "team_name": row.get("teamname"),
            "opponent_name": None,

            "champion": row.get("champion"),

            "result": safe_int(row.get("result")),

            "kills": safe_int(row.get("kills")),
            "deaths": safe_int(row.get("deaths")),
            "assists": safe_int(row.get("assists")),

            "cs": safe_int(row.get("total_cs")),
            "cspm": safe_float(row.get("cspm")),

            "total_gold": safe_int(row.get("totalgold")),
            "earned_gold": safe_int(row.get("earnedgold")),

            "dmg_to_champs": safe_int(row.get("damagetochampions")),
            "dpm": safe_float(row.get("dpm")),
            "damage_share": safe_float(row.get("damageshare")),

            "wards_placed": safe_int(row.get("wardsplaced")),
            "wards_killed": safe_int(row.get("wardskilled")),
            "vision_score": safe_float(row.get("visionscore")),

            "first_blood": safe_int(row.get("firstblood")),

            "gold_diff_10": safe_float(row.get("golddiffat10")),
            "xp_diff_10": safe_float(row.get("xpdiffat10")),
            "cs_diff_10": safe_float(row.get("csdiffat10")),

            "game_length_seconds": safe_int(row.get("gamelength")),
        }

        rec["dk_points"] = safe_float(calc_dk_points(rec))

        records.append(rec)

    player_df = pd.DataFrame(records)

    print(player_df.head())
    print(f"Player rows: {len(player_df):,}")

    if player_df.empty:
        print("No player rows found. Exiting.")
        cursor.close()
        conn.close()
        return

    insert_cols = [
        "game_id",
        "league",
        "season",
        "split",
        "patch",
        "game_date",
        "playoff_game",
        "side",
        "position",
        "player_name",
        "player_id",
        "team_name",
        "opponent_name",
        "champion",
        "result",
        "kills",
        "deaths",
        "assists",
        "cs",
        "cspm",
        "total_gold",
        "earned_gold",
        "dmg_to_champs",
        "dpm",
        "damage_share",
        "wards_placed",
        "wards_killed",
        "vision_score",
        "first_blood",
        "gold_diff_10",
        "xp_diff_10",
        "cs_diff_10",
        "game_length_seconds",
        "dk_points",
    ]

    player_df = player_df.replace([np.inf, -np.inf], np.nan)
    player_df = player_df.where(pd.notnull(player_df), None)

    rows = [
        tuple(clean_sql_value(v) for v in row)
        for row in player_df[insert_cols].itertuples(index=False, name=None)
    ]

    cursor.execute("TRUNCATE TABLE dbo.fact_lol_player_game")
    conn.commit()

    insert_sql = """
        INSERT INTO dbo.fact_lol_player_game (
            game_id,
            league,
            season,
            split,
            patch,
            game_date,
            playoff_game,
            side,
            position,
            player_name,
            player_id,
            team_name,
            opponent_name,
            champion,
            result,
            kills,
            deaths,
            assists,
            cs,
            cspm,
            total_gold,
            earned_gold,
            dmg_to_champs,
            dpm,
            damage_share,
            wards_placed,
            wards_killed,
            vision_score,
            first_blood,
            gold_diff_10,
            xp_diff_10,
            cs_diff_10,
            game_length_seconds,
            dk_points
        )
        VALUES (
            ?,?,?,?,?,?,?,?,?,?,
            ?,?,?,?,?,?,?,?,?,?,
            ?,?,?,?,?,?,?,?,?,?,
            ?,?,?,?
        )
    """

    cursor.fast_executemany = False
    cursor.executemany(insert_sql, rows)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM dbo.fact_lol_player_game")
    final_count = cursor.fetchone()[0]

    print(f"Inserted {len(rows):,} player game rows")
    print(f"SQL rows after insert: {final_count:,}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()