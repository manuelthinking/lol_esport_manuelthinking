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


def safe_diff(a, b):
    a = clean_sql_value(a)
    b = clean_sql_value(b)

    if a is None or b is None:
        return None

    return float(a) - float(b)


def create_table_if_needed(conn):
    cursor = conn.cursor()

    sql = """
    IF OBJECT_ID('dbo.fact_lol_lane_matchup', 'U') IS NULL
    BEGIN
        CREATE TABLE dbo.fact_lol_lane_matchup (
            matchup_id BIGINT IDENTITY(1,1) PRIMARY KEY,

            game_id VARCHAR(100),
            league VARCHAR(50),
            season INT,
            split VARCHAR(50),
            patch VARCHAR(20),
            game_date DATE,

            position VARCHAR(10),

            blue_player VARCHAR(100),
            red_player VARCHAR(100),

            blue_player_id VARCHAR(100),
            red_player_id VARCHAR(100),

            blue_team VARCHAR(100),
            red_team VARCHAR(100),

            blue_champion VARCHAR(100),
            red_champion VARCHAR(100),

            blue_result INT,
            red_result INT,

            blue_kills INT,
            red_kills INT,
            kill_diff FLOAT,

            blue_deaths INT,
            red_deaths INT,
            death_diff FLOAT,

            blue_assists INT,
            red_assists INT,
            assist_diff FLOAT,

            blue_dk FLOAT,
            red_dk FLOAT,
            dk_diff FLOAT,

            blue_cs INT,
            red_cs INT,
            cs_diff FLOAT,

            blue_cspm FLOAT,
            red_cspm FLOAT,
            cspm_diff FLOAT,

            blue_gold_diff_10 FLOAT,
            red_gold_diff_10 FLOAT,
            gold_diff_10_diff FLOAT,

            blue_xp_diff_10 FLOAT,
            red_xp_diff_10 FLOAT,
            xp_diff_10_diff FLOAT,

            blue_cs_diff_10 FLOAT,
            red_cs_diff_10 FLOAT,
            cs_diff_10_diff FLOAT,

            blue_dpm FLOAT,
            red_dpm FLOAT,
            dpm_diff FLOAT,

            blue_damage_share FLOAT,
            red_damage_share FLOAT,
            damage_share_diff FLOAT,

            blue_vision_score FLOAT,
            red_vision_score FLOAT,
            vision_score_diff FLOAT,

            game_length_seconds INT,

            loaded_at DATETIME2 DEFAULT SYSUTCDATETIME()
        );
    END
    """

    cursor.execute(sql)
    conn.commit()
    cursor.close()


def main():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT DB_NAME()")
    print("Connected DB:", cursor.fetchone()[0])

    create_table_if_needed(conn)

    sql = """
        SELECT
            game_id,
            league,
            season,
            split,
            patch,
            game_date,
            side,
            position,
            player_name,
            player_id,
            team_name,
            champion,
            result,
            kills,
            deaths,
            assists,
            dk_points,
            cs,
            cspm,
            gold_diff_10,
            xp_diff_10,
            cs_diff_10,
            dpm,
            damage_share,
            vision_score,
            game_length_seconds
        FROM dbo.fact_lol_player_game
        WHERE position IN ('top', 'jng', 'mid', 'bot', 'sup')
    """

    df = pd.read_sql(sql, conn)

    print(f"Player-game rows loaded: {len(df):,}")

    if df.empty:
        print("No player-game rows found. Exiting.")
        cursor.close()
        conn.close()
        return

    df["side"] = df["side"].astype(str).str.lower().str.strip()
    df["position"] = df["position"].astype(str).str.lower().str.strip()

    blue = df[df["side"] == "blue"].copy()
    red = df[df["side"] == "red"].copy()

    print(f"Blue rows: {len(blue):,}")
    print(f"Red rows: {len(red):,}")

    merged = blue.merge(
        red,
        on=["game_id", "position"],
        suffixes=("_blue", "_red"),
        how="inner",
    )

    print(f"Lane matchup rows created: {len(merged):,}")

    records = []

    for _, row in merged.iterrows():
        rec = {
            "game_id": row["game_id"],
            "league": row["league_blue"],
            "season": row["season_blue"],
            "split": row["split_blue"],
            "patch": row["patch_blue"],
            "game_date": row["game_date_blue"],

            "position": row["position"],

            "blue_player": row["player_name_blue"],
            "red_player": row["player_name_red"],

            "blue_player_id": row["player_id_blue"],
            "red_player_id": row["player_id_red"],

            "blue_team": row["team_name_blue"],
            "red_team": row["team_name_red"],

            "blue_champion": row["champion_blue"],
            "red_champion": row["champion_red"],

            "blue_result": row["result_blue"],
            "red_result": row["result_red"],

            "blue_kills": row["kills_blue"],
            "red_kills": row["kills_red"],
            "kill_diff": safe_diff(row["kills_blue"], row["kills_red"]),

            "blue_deaths": row["deaths_blue"],
            "red_deaths": row["deaths_red"],
            "death_diff": safe_diff(row["deaths_blue"], row["deaths_red"]),

            "blue_assists": row["assists_blue"],
            "red_assists": row["assists_red"],
            "assist_diff": safe_diff(row["assists_blue"], row["assists_red"]),

            "blue_dk": row["dk_points_blue"],
            "red_dk": row["dk_points_red"],
            "dk_diff": safe_diff(row["dk_points_blue"], row["dk_points_red"]),

            "blue_cs": row["cs_blue"],
            "red_cs": row["cs_red"],
            "cs_diff": safe_diff(row["cs_blue"], row["cs_red"]),

            "blue_cspm": row["cspm_blue"],
            "red_cspm": row["cspm_red"],
            "cspm_diff": safe_diff(row["cspm_blue"], row["cspm_red"]),

            "blue_gold_diff_10": row["gold_diff_10_blue"],
            "red_gold_diff_10": row["gold_diff_10_red"],
            "gold_diff_10_diff": safe_diff(row["gold_diff_10_blue"], row["gold_diff_10_red"]),

            "blue_xp_diff_10": row["xp_diff_10_blue"],
            "red_xp_diff_10": row["xp_diff_10_red"],
            "xp_diff_10_diff": safe_diff(row["xp_diff_10_blue"], row["xp_diff_10_red"]),

            "blue_cs_diff_10": row["cs_diff_10_blue"],
            "red_cs_diff_10": row["cs_diff_10_red"],
            "cs_diff_10_diff": safe_diff(row["cs_diff_10_blue"], row["cs_diff_10_red"]),

            "blue_dpm": row["dpm_blue"],
            "red_dpm": row["dpm_red"],
            "dpm_diff": safe_diff(row["dpm_blue"], row["dpm_red"]),

            "blue_damage_share": row["damage_share_blue"],
            "red_damage_share": row["damage_share_red"],
            "damage_share_diff": safe_diff(row["damage_share_blue"], row["damage_share_red"]),

            "blue_vision_score": row["vision_score_blue"],
            "red_vision_score": row["vision_score_red"],
            "vision_score_diff": safe_diff(row["vision_score_blue"], row["vision_score_red"]),

            "game_length_seconds": row["game_length_seconds_blue"],
        }

        records.append(rec)

    matchup_df = pd.DataFrame(records)

    insert_cols = [
        "game_id",
        "league",
        "season",
        "split",
        "patch",
        "game_date",
        "position",
        "blue_player",
        "red_player",
        "blue_player_id",
        "red_player_id",
        "blue_team",
        "red_team",
        "blue_champion",
        "red_champion",
        "blue_result",
        "red_result",
        "blue_kills",
        "red_kills",
        "kill_diff",
        "blue_deaths",
        "red_deaths",
        "death_diff",
        "blue_assists",
        "red_assists",
        "assist_diff",
        "blue_dk",
        "red_dk",
        "dk_diff",
        "blue_cs",
        "red_cs",
        "cs_diff",
        "blue_cspm",
        "red_cspm",
        "cspm_diff",
        "blue_gold_diff_10",
        "red_gold_diff_10",
        "gold_diff_10_diff",
        "blue_xp_diff_10",
        "red_xp_diff_10",
        "xp_diff_10_diff",
        "blue_cs_diff_10",
        "red_cs_diff_10",
        "cs_diff_10_diff",
        "blue_dpm",
        "red_dpm",
        "dpm_diff",
        "blue_damage_share",
        "red_damage_share",
        "damage_share_diff",
        "blue_vision_score",
        "red_vision_score",
        "vision_score_diff",
        "game_length_seconds",
    ]

    matchup_df = matchup_df.replace([np.inf, -np.inf], np.nan)
    matchup_df = matchup_df.where(pd.notnull(matchup_df), None)

    rows = [
        tuple(clean_sql_value(v) for v in row)
        for row in matchup_df[insert_cols].itertuples(index=False, name=None)
    ]

    cursor.execute("TRUNCATE TABLE dbo.fact_lol_lane_matchup")
    conn.commit()

    placeholders = ",".join(["?"] * len(insert_cols))
    col_sql = ",".join(f"[{c}]" for c in insert_cols)

    insert_sql = f"""
        INSERT INTO dbo.fact_lol_lane_matchup (
            {col_sql}
        )
        VALUES (
            {placeholders}
        )
    """

    cursor.fast_executemany = False
    cursor.executemany(insert_sql, rows)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM dbo.fact_lol_lane_matchup")
    final_count = cursor.fetchone()[0]

    print(f"Inserted {len(rows):,} lane matchup rows")
    print(f"SQL rows after insert: {final_count:,}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()