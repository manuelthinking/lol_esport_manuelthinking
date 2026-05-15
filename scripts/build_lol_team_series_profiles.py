import os
from pathlib import Path

import pandas as pd
import pyodbc
from dotenv import load_dotenv


load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]

DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

SOURCE_TABLE = "dbo.lol_team_series_results"
TARGET_TABLE = "dbo.lol_team_series_profiles"


def connect():
    conn_str = (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_DATABASE};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


def load_series_results(conn):
    sql = f"""
        SELECT
            series_id,
            league,
            [year],
            split,
            playoffs,
            series_start_date,
            teamname,
            opponent,
            series_result,
            is_series_win,
            games_played,
            wins,
            losses,
            max_games,
            games_not_played,
            player_gnp_bonus_per_player,
            player_gnp_bonus_total_5,
            team_slot_gnp_bonus,
            player_dk_fp_base,
            player_dk_fp_with_gnp,
            team_slot_dk_fp_base,
            team_slot_dk_fp_with_gnp,
            avg_game_length_minutes,
            total_game_length_minutes,
            total_team_kills,
            total_team_deaths,
            total_player_kills,
            total_player_deaths,
            total_player_assists,
            total_player_cs,
            total_player_damage,
            total_player_dpm,
            total_dragons,
            total_barons,
            total_towers,
            total_firstbloods,
            avg_gold_diff_10,
            avg_xp_diff_10,
            avg_cs_diff_10,
            avg_gold_diff_15,
            avg_xp_diff_15,
            avg_cs_diff_15
        FROM {SOURCE_TABLE}
        WHERE series_result IN ('2-0', '2-1', '1-2', '0-2')
    """
    return pd.read_sql(sql, conn)


def safe_divide(a, b):
    if b == 0 or pd.isna(b):
        return 0
    return a / b


def build_profiles(df):
    if df.empty:
        raise ValueError(f"No BO3 series rows found in {SOURCE_TABLE}")

    df = df.copy()

    numeric_cols = [
        "year",
        "playoffs",
        "is_series_win",
        "games_played",
        "wins",
        "losses",
        "max_games",
        "games_not_played",
        "player_gnp_bonus_per_player",
        "player_gnp_bonus_total_5",
        "team_slot_gnp_bonus",
        "player_dk_fp_base",
        "player_dk_fp_with_gnp",
        "team_slot_dk_fp_base",
        "team_slot_dk_fp_with_gnp",
        "avg_game_length_minutes",
        "total_game_length_minutes",
        "total_team_kills",
        "total_team_deaths",
        "total_player_kills",
        "total_player_deaths",
        "total_player_assists",
        "total_player_cs",
        "total_player_damage",
        "total_player_dpm",
        "total_dragons",
        "total_barons",
        "total_towers",
        "total_firstbloods",
        "avg_gold_diff_10",
        "avg_xp_diff_10",
        "avg_cs_diff_10",
        "avg_gold_diff_15",
        "avg_xp_diff_15",
        "avg_cs_diff_15",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    grouped = (
        df.groupby(["teamname", "league", "series_result"], dropna=False)
        .agg(
            series_count=("series_id", "nunique"),
            first_series_date=("series_start_date", "min"),
            last_series_date=("series_start_date", "max"),

            avg_games_played=("games_played", "mean"),
            avg_wins=("wins", "mean"),
            avg_losses=("losses", "mean"),
            win_rate=("is_series_win", "mean"),

            avg_player_dk_fp_base=("player_dk_fp_base", "mean"),
            avg_player_dk_fp_with_gnp=("player_dk_fp_with_gnp", "mean"),
            avg_player_gnp_bonus_total_5=("player_gnp_bonus_total_5", "mean"),

            avg_team_slot_dk_fp_base=("team_slot_dk_fp_base", "mean"),
            avg_team_slot_dk_fp_with_gnp=("team_slot_dk_fp_with_gnp", "mean"),
            avg_team_slot_gnp_bonus=("team_slot_gnp_bonus", "mean"),

            avg_game_length_minutes=("avg_game_length_minutes", "mean"),
            avg_total_game_length_minutes=("total_game_length_minutes", "mean"),

            avg_team_kills=("total_team_kills", "mean"),
            avg_team_deaths=("total_team_deaths", "mean"),
            avg_player_kills=("total_player_kills", "mean"),
            avg_player_deaths=("total_player_deaths", "mean"),
            avg_player_assists=("total_player_assists", "mean"),
            avg_player_cs=("total_player_cs", "mean"),
            avg_player_damage=("total_player_damage", "mean"),
            avg_player_dpm=("total_player_dpm", "mean"),

            avg_dragons=("total_dragons", "mean"),
            avg_barons=("total_barons", "mean"),
            avg_towers=("total_towers", "mean"),
            avg_firstbloods=("total_firstbloods", "mean"),

            avg_gold_diff_10=("avg_gold_diff_10", "mean"),
            avg_xp_diff_10=("avg_xp_diff_10", "mean"),
            avg_cs_diff_10=("avg_cs_diff_10", "mean"),
            avg_gold_diff_15=("avg_gold_diff_15", "mean"),
            avg_xp_diff_15=("avg_xp_diff_15", "mean"),
            avg_cs_diff_15=("avg_cs_diff_15", "mean"),
        )
        .reset_index()
    )

    # Per-game rates inside the series.
    grouped["avg_kills_per_game"] = grouped.apply(
        lambda r: safe_divide(r["avg_team_kills"], r["avg_games_played"]),
        axis=1,
    )

    grouped["avg_deaths_per_game"] = grouped.apply(
        lambda r: safe_divide(r["avg_team_deaths"], r["avg_games_played"]),
        axis=1,
    )

    grouped["avg_player_dk_per_game"] = grouped.apply(
        lambda r: safe_divide(r["avg_player_dk_fp_with_gnp"], r["avg_games_played"]),
        axis=1,
    )

    grouped["avg_team_slot_dk_per_game"] = grouped.apply(
        lambda r: safe_divide(r["avg_team_slot_dk_fp_with_gnp"], r["avg_games_played"]),
        axis=1,
    )

    grouped["kill_death_ratio"] = grouped.apply(
        lambda r: safe_divide(r["avg_team_kills"], r["avg_team_deaths"]),
        axis=1,
    )

    grouped["assist_per_kill"] = grouped.apply(
        lambda r: safe_divide(r["avg_player_assists"], r["avg_team_kills"]),
        axis=1,
    )

    # Simple DFS environment score.
    # Higher = more DFS-friendly team/series profile.
    grouped["series_dfs_score"] = (
        (grouped["avg_player_dk_fp_with_gnp"] * 0.40)
        + (grouped["avg_team_kills"] * 2.00)
        + (grouped["avg_kills_per_game"] * 4.00)
        + (grouped["avg_game_length_minutes"] * 1.25)
        + (grouped["avg_team_slot_dk_fp_with_gnp"] * 0.75)
        - (grouped["avg_team_deaths"] * 0.50)
    )

    grouped["bloodiness_score"] = (
        (grouped["avg_team_kills"] * 0.55)
        + (grouped["avg_team_deaths"] * 0.35)
        + (grouped["avg_total_game_length_minutes"] * 0.10)
    )

    grouped["clean_stomp_score"] = (
        (grouped["avg_gold_diff_15"] * 0.01)
        + (grouped["avg_xp_diff_15"] * 0.01)
        + (grouped["avg_towers"] * 1.50)
        + (grouped["avg_dragons"] * 1.25)
        + (grouped["avg_team_slot_gnp_bonus"] * 0.50)
        - (grouped["avg_team_deaths"] * 0.75)
    )

    grouped["profile_label"] = grouped.apply(assign_profile_label, axis=1)

    grouped = grouped.sort_values(
        ["teamname", "league", "series_result"],
        ascending=[True, True, True],
    )

    print("")
    print(f"Built profile rows: {len(grouped):,}")
    print(f"Unique teams: {grouped['teamname'].nunique():,}")
    print("")
    print("Profile rows by result:")
    print(grouped["series_result"].value_counts().sort_index().to_string())

    return grouped


def assign_profile_label(row):
    result = row["series_result"]
    dfs = row["series_dfs_score"]
    blood = row["bloodiness_score"]
    stomp = row["clean_stomp_score"]

    if result == "2-0":
        if dfs >= 230 and stomp >= 20:
            return "Elite 2-0 Smash"
        if dfs >= 210:
            return "Strong 2-0 Producer"
        if stomp >= 20 and dfs < 190:
            return "Clean But Low DFS"
        return "Standard 2-0"

    if result == "2-1":
        if dfs >= 260 and blood >= 45:
            return "Elite 2-1 Bloodbath"
        if dfs >= 235:
            return "Strong 2-1 Ceiling"
        if blood >= 45:
            return "Bloody But Volatile"
        return "Standard 2-1"

    if result == "1-2":
        if dfs >= 230:
            return "Live Losing Stack"
        if blood >= 45:
            return "Useful Loss Volume"
        return "Low Loss Output"

    if result == "0-2":
        if dfs >= 170:
            return "Competitive Sweep Loss"
        return "Dead Sweep Loss"

    return "Unclassified"


def create_table(conn):
    sql = f"""
    IF OBJECT_ID('{TARGET_TABLE}', 'U') IS NULL
    BEGIN
        CREATE TABLE {TARGET_TABLE} (
            teamname NVARCHAR(255) NOT NULL,
            league NVARCHAR(50) NOT NULL,
            series_result NVARCHAR(20) NOT NULL,

            series_count INT NULL,
            first_series_date DATE NULL,
            last_series_date DATE NULL,

            avg_games_played FLOAT NULL,
            avg_wins FLOAT NULL,
            avg_losses FLOAT NULL,
            win_rate FLOAT NULL,

            avg_player_dk_fp_base FLOAT NULL,
            avg_player_dk_fp_with_gnp FLOAT NULL,
            avg_player_gnp_bonus_total_5 FLOAT NULL,

            avg_team_slot_dk_fp_base FLOAT NULL,
            avg_team_slot_dk_fp_with_gnp FLOAT NULL,
            avg_team_slot_gnp_bonus FLOAT NULL,

            avg_game_length_minutes FLOAT NULL,
            avg_total_game_length_minutes FLOAT NULL,

            avg_team_kills FLOAT NULL,
            avg_team_deaths FLOAT NULL,
            avg_player_kills FLOAT NULL,
            avg_player_deaths FLOAT NULL,
            avg_player_assists FLOAT NULL,
            avg_player_cs FLOAT NULL,
            avg_player_damage FLOAT NULL,
            avg_player_dpm FLOAT NULL,

            avg_dragons FLOAT NULL,
            avg_barons FLOAT NULL,
            avg_towers FLOAT NULL,
            avg_firstbloods FLOAT NULL,

            avg_gold_diff_10 FLOAT NULL,
            avg_xp_diff_10 FLOAT NULL,
            avg_cs_diff_10 FLOAT NULL,
            avg_gold_diff_15 FLOAT NULL,
            avg_xp_diff_15 FLOAT NULL,
            avg_cs_diff_15 FLOAT NULL,

            avg_kills_per_game FLOAT NULL,
            avg_deaths_per_game FLOAT NULL,
            avg_player_dk_per_game FLOAT NULL,
            avg_team_slot_dk_per_game FLOAT NULL,
            kill_death_ratio FLOAT NULL,
            assist_per_kill FLOAT NULL,

            series_dfs_score FLOAT NULL,
            bloodiness_score FLOAT NULL,
            clean_stomp_score FLOAT NULL,
            profile_label NVARCHAR(100) NULL,

            loaded_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),

            CONSTRAINT pk_lol_team_series_profiles
                PRIMARY KEY (teamname, league, series_result)
        );
    END
    """
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()


def clear_table(conn):
    sql = f"DELETE FROM {TARGET_TABLE}"
    cur = conn.cursor()
    cur.execute(sql)
    deleted = cur.rowcount
    conn.commit()
    cur.close()
    print(f"Deleted existing profile rows: {deleted}")


def insert_rows(conn, df):
    insert_cols = list(df.columns)
    sql_cols = ", ".join(f"[{c}]" for c in insert_cols)
    placeholders = ", ".join(["?"] * len(insert_cols))

    sql = f"""
        INSERT INTO {TARGET_TABLE} ({sql_cols})
        VALUES ({placeholders})
    """

    rows = []

    for _, r in df.iterrows():
        row = []

        for c in insert_cols:
            v = r[c]

            if pd.isna(v):
                row.append(None)
            elif c in ["first_series_date", "last_series_date"]:
                row.append(pd.to_datetime(v).date())
            else:
                row.append(v)

        rows.append(tuple(row))

    cur = conn.cursor()
    cur.fast_executemany = True
    cur.executemany(sql, rows)
    conn.commit()
    cur.close()

    print(f"Inserted profile rows: {len(rows):,}")


def main():
    if not DB_SERVER or not DB_DATABASE:
        raise ValueError("Missing DB_SERVER or DB_DATABASE in .env")

    conn = connect()

    cursor = conn.cursor()
    cursor.execute("SELECT DB_NAME()")
    print("Connected DB:", cursor.fetchone()[0])
    cursor.close()

    df = load_series_results(conn)
    print(f"Loaded series-result rows: {len(df):,}")

    profiles_df = build_profiles(df)

    create_table(conn)
    clear_table(conn)
    insert_rows(conn, profiles_df)

    conn.close()

    print("")
    print(f"Done. Table built: {TARGET_TABLE}")


if __name__ == "__main__":
    main()