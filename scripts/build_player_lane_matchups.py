import os
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


def main():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT DB_NAME()")
    print("Connected DB:", cursor.fetchone()[0])

    sql = """
        SELECT *
        FROM dbo.fact_lol_lane_matchup
    """

    df = pd.read_sql(sql, conn)

    print(f"Lane matchup rows loaded: {len(df):,}")

    if df.empty:
        print("No lane matchup rows found. Exiting.")
        cursor.close()
        conn.close()
        return

    records = []

    for _, row in df.iterrows():
        base = {
            "game_id": row["game_id"],
            "league": row["league"],
            "season": row["season"],
            "split": row["split"],
            "patch": row["patch"],
            "game_date": row["game_date"],
            "position": row["position"],
            "game_length_seconds": row["game_length_seconds"],
        }

        blue_rec = {
            **base,
            "side": "blue",
            "player_name": row["blue_player"],
            "player_id": row["blue_player_id"],
            "team_name": row["blue_team"],
            "champion": row["blue_champion"],

            "opponent_player": row["red_player"],
            "opponent_player_id": row["red_player_id"],
            "opponent_team": row["red_team"],
            "opponent_champion": row["red_champion"],

            "result": row["blue_result"],

            "kills": row["blue_kills"],
            "deaths": row["blue_deaths"],
            "assists": row["blue_assists"],
            "dk_points": row["blue_dk"],

            "cs": row["blue_cs"],
            "cspm": row["blue_cspm"],

            "gold_diff_10": row["blue_gold_diff_10"],
            "xp_diff_10": row["blue_xp_diff_10"],
            "cs_diff_10": row["blue_cs_diff_10"],

            "dpm": row["blue_dpm"],
            "damage_share": row["blue_damage_share"],
            "vision_score": row["blue_vision_score"],

            "dk_edge": row["dk_diff"],
            "kill_edge": row["kill_diff"],
            "death_edge": row["death_diff"],
            "assist_edge": row["assist_diff"],
            "cs_edge": row["cs_diff"],
            "cspm_edge": row["cspm_diff"],
            "gold_diff_10_edge": row["gold_diff_10_diff"],
            "xp_diff_10_edge": row["xp_diff_10_diff"],
            "cs_diff_10_edge": row["cs_diff_10_diff"],
            "dpm_edge": row["dpm_diff"],
            "damage_share_edge": row["damage_share_diff"],
            "vision_score_edge": row["vision_score_diff"],
        }

        red_rec = {
            **base,
            "side": "red",
            "player_name": row["red_player"],
            "player_id": row["red_player_id"],
            "team_name": row["red_team"],
            "champion": row["red_champion"],

            "opponent_player": row["blue_player"],
            "opponent_player_id": row["blue_player_id"],
            "opponent_team": row["blue_team"],
            "opponent_champion": row["blue_champion"],

            "result": row["red_result"],

            "kills": row["red_kills"],
            "deaths": row["red_deaths"],
            "assists": row["red_assists"],
            "dk_points": row["red_dk"],

            "cs": row["red_cs"],
            "cspm": row["red_cspm"],

            "gold_diff_10": row["red_gold_diff_10"],
            "xp_diff_10": row["red_xp_diff_10"],
            "cs_diff_10": row["red_cs_diff_10"],

            "dpm": row["red_dpm"],
            "damage_share": row["red_damage_share"],
            "vision_score": row["red_vision_score"],

            "dk_edge": -1 * row["dk_diff"] if row["dk_diff"] is not None else None,
            "kill_edge": -1 * row["kill_diff"] if row["kill_diff"] is not None else None,
            "death_edge": -1 * row["death_diff"] if row["death_diff"] is not None else None,
            "assist_edge": -1 * row["assist_diff"] if row["assist_diff"] is not None else None,
            "cs_edge": -1 * row["cs_diff"] if row["cs_diff"] is not None else None,
            "cspm_edge": -1 * row["cspm_diff"] if row["cspm_diff"] is not None else None,
            "gold_diff_10_edge": -1 * row["gold_diff_10_diff"] if row["gold_diff_10_diff"] is not None else None,
            "xp_diff_10_edge": -1 * row["xp_diff_10_diff"] if row["xp_diff_10_diff"] is not None else None,
            "cs_diff_10_edge": -1 * row["cs_diff_10_diff"] if row["cs_diff_10_diff"] is not None else None,
            "dpm_edge": -1 * row["dpm_diff"] if row["dpm_diff"] is not None else None,
            "damage_share_edge": -1 * row["damage_share_diff"] if row["damage_share_diff"] is not None else None,
            "vision_score_edge": -1 * row["vision_score_diff"] if row["vision_score_diff"] is not None else None,
        }

        records.append(blue_rec)
        records.append(red_rec)

    out_df = pd.DataFrame(records)

    print(f"Neutral player-lane rows created: {len(out_df):,}")

    insert_cols = [
        "game_id",
        "league",
        "season",
        "split",
        "patch",
        "game_date",
        "position",
        "side",
        "player_name",
        "player_id",
        "team_name",
        "champion",
        "opponent_player",
        "opponent_player_id",
        "opponent_team",
        "opponent_champion",
        "result",
        "kills",
        "deaths",
        "assists",
        "dk_points",
        "cs",
        "cspm",
        "gold_diff_10",
        "xp_diff_10",
        "cs_diff_10",
        "dpm",
        "damage_share",
        "vision_score",
        "dk_edge",
        "kill_edge",
        "death_edge",
        "assist_edge",
        "cs_edge",
        "cspm_edge",
        "gold_diff_10_edge",
        "xp_diff_10_edge",
        "cs_diff_10_edge",
        "dpm_edge",
        "damage_share_edge",
        "vision_score_edge",
        "game_length_seconds",
    ]

    out_df = out_df.replace([np.inf, -np.inf], np.nan)
    out_df = out_df.where(pd.notnull(out_df), None)

    rows = [
        tuple(clean_sql_value(v) for v in row)
        for row in out_df[insert_cols].itertuples(index=False, name=None)
    ]

    cursor.execute("TRUNCATE TABLE dbo.fact_lol_player_lane_matchup")
    conn.commit()

    placeholders = ",".join(["?"] * len(insert_cols))
    col_sql = ",".join(f"[{c}]" for c in insert_cols)

    insert_sql = f"""
        INSERT INTO dbo.fact_lol_player_lane_matchup (
            {col_sql}
        )
        VALUES (
            {placeholders}
        )
    """

    cursor.fast_executemany = False
    cursor.executemany(insert_sql, rows)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM dbo.fact_lol_player_lane_matchup")
    final_count = cursor.fetchone()[0]

    print(f"Inserted {len(rows):,} player-lane matchup rows")
    print(f"SQL rows after insert: {final_count:,}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()