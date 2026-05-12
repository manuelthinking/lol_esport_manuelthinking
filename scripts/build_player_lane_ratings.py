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


def zscore(series: pd.Series) -> pd.Series:
    std = series.std(ddof=0)
    if std is None or std == 0 or pd.isna(std):
        return pd.Series([0.0] * len(series), index=series.index)
    return (series - series.mean()) / std


def main():
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT DB_NAME()")
    print("Connected DB:", cursor.fetchone()[0])

    sql = """
        SELECT
            game_id,
            season,
            league,
            team_name,
            player_name,
            player_id,
            position,
            result,
            dk_points,
            dk_edge,
            kills,
            deaths,
            assists,
            kill_edge,
            death_edge,
            assist_edge,
            cs,
            cspm,
            cs_edge,
            cspm_edge,
            gold_diff_10,
            xp_diff_10,
            cs_diff_10,
            gold_diff_10_edge,
            xp_diff_10_edge,
            cs_diff_10_edge,
            dpm,
            damage_share,
            vision_score,
            dpm_edge,
            damage_share_edge,
            vision_score_edge
        FROM dbo.fact_lol_player_lane_matchup
    """

    df = pd.read_sql(sql, conn)

    print(f"Player-lane matchup rows loaded: {len(df):,}")

    if df.empty:
        print("No rows found. Exiting.")
        cursor.close()
        conn.close()
        return

    numeric_cols = [
        "result",
        "dk_points",
        "dk_edge",
        "kills",
        "deaths",
        "assists",
        "kill_edge",
        "death_edge",
        "assist_edge",
        "cs",
        "cspm",
        "cs_edge",
        "cspm_edge",
        "gold_diff_10",
        "xp_diff_10",
        "cs_diff_10",
        "gold_diff_10_edge",
        "xp_diff_10_edge",
        "cs_diff_10_edge",
        "dpm",
        "damage_share",
        "vision_score",
        "dpm_edge",
        "damage_share_edge",
        "vision_score_edge",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    group_cols = [
        "season",
        "league",
        "team_name",
        "player_name",
        "player_id",
        "position",
    ]

    ratings = (
        df.groupby(group_cols, dropna=False)
        .agg(
            games=("game_id", "count"),
            win_rate=("result", "mean"),

            avg_dk=("dk_points", "mean"),
            avg_dk_edge=("dk_edge", "mean"),

            avg_kills=("kills", "mean"),
            avg_deaths=("deaths", "mean"),
            avg_assists=("assists", "mean"),

            avg_kill_edge=("kill_edge", "mean"),
            avg_death_edge=("death_edge", "mean"),
            avg_assist_edge=("assist_edge", "mean"),

            avg_cs=("cs", "mean"),
            avg_cspm=("cspm", "mean"),
            avg_cs_edge=("cs_edge", "mean"),
            avg_cspm_edge=("cspm_edge", "mean"),

            avg_gold_diff_10=("gold_diff_10", "mean"),
            avg_xp_diff_10=("xp_diff_10", "mean"),
            avg_cs_diff_10=("cs_diff_10", "mean"),

            avg_gold_diff_10_edge=("gold_diff_10_edge", "mean"),
            avg_xp_diff_10_edge=("xp_diff_10_edge", "mean"),
            avg_cs_diff_10_edge=("cs_diff_10_edge", "mean"),

            avg_dpm=("dpm", "mean"),
            avg_damage_share=("damage_share", "mean"),
            avg_vision_score=("vision_score", "mean"),

            avg_dpm_edge=("dpm_edge", "mean"),
            avg_damage_share_edge=("damage_share_edge", "mean"),
            avg_vision_score_edge=("vision_score_edge", "mean"),
        )
        .reset_index()
    )

    # Rating score v1:
    # Use role-relative z-scores inside season + league + position.
    # Positive: dk edge, kill edge, gold/xp/cs edge, dpm edge, win rate.
    # Negative: death edge.
    ratings["rating_score"] = 0.0

    for _, idx in ratings.groupby(["season", "league", "position"]).groups.items():
        sub = ratings.loc[idx]

        score = (
            0.30 * zscore(sub["avg_dk_edge"].fillna(0))
            + 0.20 * zscore(sub["avg_kill_edge"].fillna(0))
            - 0.10 * zscore(sub["avg_death_edge"].fillna(0))
            + 0.15 * zscore(sub["avg_gold_diff_10_edge"].fillna(0))
            + 0.10 * zscore(sub["avg_xp_diff_10_edge"].fillna(0))
            + 0.05 * zscore(sub["avg_cs_diff_10_edge"].fillna(0))
            + 0.05 * zscore(sub["avg_dpm_edge"].fillna(0))
            + 0.05 * zscore(sub["win_rate"].fillna(0))
        )

        ratings.loc[idx, "rating_score"] = score

    print(ratings.head())
    print(f"Rating rows created: {len(ratings):,}")

    insert_cols = [
        "season",
        "league",
        "team_name",
        "player_name",
        "player_id",
        "position",
        "games",
        "win_rate",
        "avg_dk",
        "avg_dk_edge",
        "avg_kills",
        "avg_deaths",
        "avg_assists",
        "avg_kill_edge",
        "avg_death_edge",
        "avg_assist_edge",
        "avg_cs",
        "avg_cspm",
        "avg_cs_edge",
        "avg_cspm_edge",
        "avg_gold_diff_10",
        "avg_xp_diff_10",
        "avg_cs_diff_10",
        "avg_gold_diff_10_edge",
        "avg_xp_diff_10_edge",
        "avg_cs_diff_10_edge",
        "avg_dpm",
        "avg_damage_share",
        "avg_vision_score",
        "avg_dpm_edge",
        "avg_damage_share_edge",
        "avg_vision_score_edge",
        "rating_score",
    ]

    ratings = ratings.replace([np.inf, -np.inf], np.nan)
    ratings = ratings.where(pd.notnull(ratings), None)

    rows = [
        tuple(clean_sql_value(v) for v in row)
        for row in ratings[insert_cols].itertuples(index=False, name=None)
    ]

    cursor.execute("TRUNCATE TABLE dbo.lol_player_lane_ratings")
    conn.commit()

    placeholders = ",".join(["?"] * len(insert_cols))
    col_sql = ",".join(f"[{c}]" for c in insert_cols)

    insert_sql = f"""
        INSERT INTO dbo.lol_player_lane_ratings (
            {col_sql}
        )
        VALUES (
            {placeholders}
        )
    """

    cursor.fast_executemany = False
    cursor.executemany(insert_sql, rows)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM dbo.lol_player_lane_ratings")
    final_count = cursor.fetchone()[0]

    print(f"Inserted {len(rows):,} player lane rating rows")
    print(f"SQL rows after insert: {final_count:,}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()