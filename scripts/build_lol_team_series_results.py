import hashlib
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

SOURCE_TABLE = "dbo.lol_team_game_stats"
TARGET_TABLE = "dbo.lol_team_series_results"


def connect():
    conn_str = (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_DATABASE};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


def clean_text(v):
    if pd.isna(v):
        return ""
    return str(v).strip()


def make_series_key(row):
    teams = sorted([clean_text(row["teamname"]), clean_text(row["opponent"])])
    pieces = [
        clean_text(row["league"]),
        str(int(row["year"])) if not pd.isna(row["year"]) else "",
        clean_text(row["split"]),
        str(int(row["playoffs"])) if not pd.isna(row["playoffs"]) else "",
        str(row["game_date"]),
        teams[0],
        teams[1],
    ]
    raw_key = "|".join(pieces)
    return hashlib.md5(raw_key.encode("utf-8")).hexdigest()


def infer_max_games(wins, losses, games_played):
    """
    Infer series length from final result.

    BO1:
        1-0 or 0-1

    BO3:
        2-0, 2-1, 1-2, 0-2

    BO5:
        3-0, 3-1, 3-2, 2-3, 1-3, 0-3

    Most DK LoL Classic slates we care about are BO3, but this keeps
    the table safe for BO1 and BO5 formats too.
    """
    max_wins = max(wins, losses)

    if max_wins <= 1 and games_played <= 1:
        return 1

    if max_wins == 2:
        return 3

    if max_wins == 3:
        return 5

    return games_played


def load_team_game_stats(conn):
    sql = f"""
        SELECT
            gameid,
            league,
            [year],
            split,
            playoffs,
            [date],
            game_date,
            game_number,
            patch,
            side,
            teamname,
            opponent,
            is_win,
            game_length_seconds,
            game_length_minutes,
            team_kills,
            team_deaths,
            team_row_assists,
            firstblood,
            dragons,
            barons,
            towers,
            player_count,
            player_dk_fp_sum,
            team_slot_dk_fp_base,
            player_kills_sum,
            player_deaths_sum,
            player_assists_sum,
            player_cs_sum,
            player_damage_sum,
            player_dpm_sum,
            avg_gold_diff_10,
            avg_xp_diff_10,
            avg_cs_diff_10,
            avg_gold_diff_15,
            avg_xp_diff_15,
            avg_cs_diff_15
        FROM {SOURCE_TABLE}
    """
    return pd.read_sql(sql, conn)


def build_series_results(df):
    if df.empty:
        raise ValueError(f"No rows found in {SOURCE_TABLE}")

    df = df.copy()

    df["game_date"] = pd.to_datetime(df["game_date"], errors="coerce").dt.date
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    numeric_cols = [
        "year",
        "playoffs",
        "game_number",
        "patch",
        "is_win",
        "game_length_seconds",
        "game_length_minutes",
        "team_kills",
        "team_deaths",
        "team_row_assists",
        "firstblood",
        "dragons",
        "barons",
        "towers",
        "player_count",
        "player_dk_fp_sum",
        "team_slot_dk_fp_base",
        "player_kills_sum",
        "player_deaths_sum",
        "player_assists_sum",
        "player_cs_sum",
        "player_damage_sum",
        "player_dpm_sum",
        "avg_gold_diff_10",
        "avg_xp_diff_10",
        "avg_cs_diff_10",
        "avg_gold_diff_15",
        "avg_xp_diff_15",
        "avg_cs_diff_15",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["series_id"] = df.apply(make_series_key, axis=1)

    series_rows = []

    group_cols = ["series_id", "teamname"]

    for (series_id, teamname), g in df.groupby(group_cols, dropna=False):
        g = g.sort_values(["game_number", "date", "gameid"]).copy()

        first = g.iloc[0]

        games_played = int(g["gameid"].nunique())
        wins = int(g["is_win"].sum())
        losses = int(games_played - wins)

        max_games = infer_max_games(wins, losses, games_played)

        is_series_win = 1 if wins > losses else 0
        games_not_played = max_games - games_played if is_series_win == 1 else 0

        if games_not_played < 0:
            games_not_played = 0

        player_gnp_bonus_per_player = 20 * games_not_played
        player_gnp_bonus_total_5 = player_gnp_bonus_per_player * 5

        team_slot_gnp_bonus = 15 * games_not_played

        player_dk_fp_base = float(g["player_dk_fp_sum"].sum())
        player_dk_fp_with_gnp = player_dk_fp_base + player_gnp_bonus_total_5

        team_slot_dk_fp_base = float(g["team_slot_dk_fp_base"].sum())
        team_slot_dk_fp_with_gnp = team_slot_dk_fp_base + team_slot_gnp_bonus

        gameids = ",".join(g["gameid"].astype(str).drop_duplicates().tolist())

        series_rows.append(
            {
                "series_id": series_id,
                "league": first["league"],
                "year": int(first["year"]),
                "split": first["split"],
                "playoffs": int(first["playoffs"]),
                "series_start_datetime": g["date"].min(),
                "series_end_datetime": g["date"].max(),
                "series_start_date": g["game_date"].min(),
                "series_end_date": g["game_date"].max(),
                "teamname": teamname,
                "opponent": first["opponent"],
                "series_result": f"{wins}-{losses}",
                "is_series_win": is_series_win,
                "games_played": games_played,
                "wins": wins,
                "losses": losses,
                "max_games": max_games,
                "games_not_played": games_not_played,
                "player_gnp_bonus_per_player": player_gnp_bonus_per_player,
                "player_gnp_bonus_total_5": player_gnp_bonus_total_5,
                "team_slot_gnp_bonus": team_slot_gnp_bonus,
                "player_dk_fp_base": player_dk_fp_base,
                "player_dk_fp_with_gnp": player_dk_fp_with_gnp,
                "team_slot_dk_fp_base": team_slot_dk_fp_base,
                "team_slot_dk_fp_with_gnp": team_slot_dk_fp_with_gnp,
                "avg_game_length_minutes": float(g["game_length_minutes"].mean()),
                "total_game_length_minutes": float(g["game_length_minutes"].sum()),
                "total_team_kills": float(g["team_kills"].sum()),
                "total_team_deaths": float(g["team_deaths"].sum()),
                "total_player_kills": float(g["player_kills_sum"].sum()),
                "total_player_deaths": float(g["player_deaths_sum"].sum()),
                "total_player_assists": float(g["player_assists_sum"].sum()),
                "total_player_cs": float(g["player_cs_sum"].sum()),
                "total_player_damage": float(g["player_damage_sum"].sum()),
                "total_player_dpm": float(g["player_dpm_sum"].sum()),
                "total_dragons": float(g["dragons"].sum()),
                "total_barons": float(g["barons"].sum()),
                "total_towers": float(g["towers"].sum()),
                "total_firstbloods": float(g["firstblood"].sum()),
                "avg_gold_diff_10": float(g["avg_gold_diff_10"].mean()),
                "avg_xp_diff_10": float(g["avg_xp_diff_10"].mean()),
                "avg_cs_diff_10": float(g["avg_cs_diff_10"].mean()),
                "avg_gold_diff_15": float(g["avg_gold_diff_15"].mean()),
                "avg_xp_diff_15": float(g["avg_xp_diff_15"].mean()),
                "avg_cs_diff_15": float(g["avg_cs_diff_15"].mean()),
                "gameids": gameids,
            }
        )

    out = pd.DataFrame(series_rows)

    out = out.sort_values(
        ["series_start_date", "league", "series_id", "teamname"],
        ascending=[True, True, True, True],
    )

    print("")
    print(f"Built team-series rows: {len(out):,}")
    print(f"Unique series: {out['series_id'].nunique():,}")
    print(f"Unique teams: {out['teamname'].nunique():,}")

    print("")
    print("Series result counts:")
    print(out["series_result"].value_counts().sort_index().to_string())

    weird = out[~out["series_result"].isin(["1-0", "0-1", "2-0", "2-1", "1-2", "0-2", "3-0", "3-1", "3-2", "2-3", "1-3", "0-3"])]

    if not weird.empty:
        print("")
        print("WARNING: Unusual series results found:")
        print(
            weird[
                [
                    "league",
                    "series_start_date",
                    "teamname",
                    "opponent",
                    "series_result",
                    "games_played",
                    "gameids",
                ]
            ]
            .head(30)
            .to_string(index=False)
        )

    bad_series = (
        out.groupby("series_id")["teamname"]
        .nunique()
        .reset_index(name="team_count")
    )
    bad_series = bad_series[bad_series["team_count"] != 2]

    if not bad_series.empty:
        print("")
        print("WARNING: Some series do not have exactly two teams:")
        print(bad_series.head(30).to_string(index=False))

    return out


def create_table(conn):
    sql = f"""
    IF OBJECT_ID('{TARGET_TABLE}', 'U') IS NULL
    BEGIN
        CREATE TABLE {TARGET_TABLE} (
            series_id NVARCHAR(64) NOT NULL,
            league NVARCHAR(50) NULL,
            [year] INT NULL,
            split NVARCHAR(50) NULL,
            playoffs INT NULL,
            series_start_datetime DATETIME2 NULL,
            series_end_datetime DATETIME2 NULL,
            series_start_date DATE NULL,
            series_end_date DATE NULL,
            teamname NVARCHAR(255) NOT NULL,
            opponent NVARCHAR(255) NULL,
            series_result NVARCHAR(20) NULL,
            is_series_win INT NULL,
            games_played INT NULL,
            wins INT NULL,
            losses INT NULL,
            max_games INT NULL,
            games_not_played INT NULL,
            player_gnp_bonus_per_player FLOAT NULL,
            player_gnp_bonus_total_5 FLOAT NULL,
            team_slot_gnp_bonus FLOAT NULL,
            player_dk_fp_base FLOAT NULL,
            player_dk_fp_with_gnp FLOAT NULL,
            team_slot_dk_fp_base FLOAT NULL,
            team_slot_dk_fp_with_gnp FLOAT NULL,
            avg_game_length_minutes FLOAT NULL,
            total_game_length_minutes FLOAT NULL,
            total_team_kills FLOAT NULL,
            total_team_deaths FLOAT NULL,
            total_player_kills FLOAT NULL,
            total_player_deaths FLOAT NULL,
            total_player_assists FLOAT NULL,
            total_player_cs FLOAT NULL,
            total_player_damage FLOAT NULL,
            total_player_dpm FLOAT NULL,
            total_dragons FLOAT NULL,
            total_barons FLOAT NULL,
            total_towers FLOAT NULL,
            total_firstbloods FLOAT NULL,
            avg_gold_diff_10 FLOAT NULL,
            avg_xp_diff_10 FLOAT NULL,
            avg_cs_diff_10 FLOAT NULL,
            avg_gold_diff_15 FLOAT NULL,
            avg_xp_diff_15 FLOAT NULL,
            avg_cs_diff_15 FLOAT NULL,
            gameids NVARCHAR(MAX) NULL,
            loaded_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),

            CONSTRAINT pk_lol_team_series_results PRIMARY KEY (series_id, teamname)
        );
    END
    """

    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()


def replace_years(conn, years):
    placeholders = ",".join(["?"] * len(years))
    sql = f"DELETE FROM {TARGET_TABLE} WHERE [year] IN ({placeholders})"

    cur = conn.cursor()
    cur.execute(sql, years)
    deleted = cur.rowcount
    conn.commit()
    cur.close()

    print(f"Deleted existing rows for years {years}: {deleted}")


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
            elif c in ["series_start_datetime", "series_end_datetime"]:
                row.append(pd.to_datetime(v).to_pydatetime())
            elif c in ["series_start_date", "series_end_date"]:
                row.append(pd.to_datetime(v).date())
            else:
                row.append(v)

        rows.append(tuple(row))

    cur = conn.cursor()
    cur.fast_executemany = True
    cur.executemany(sql, rows)
    conn.commit()
    cur.close()

    print(f"Inserted rows: {len(rows):,}")


def main():
    if not DB_SERVER or not DB_DATABASE:
        raise ValueError("Missing DB_SERVER or DB_DATABASE in .env")

    conn = connect()

    cursor = conn.cursor()
    cursor.execute("SELECT DB_NAME()")
    print("Connected DB:", cursor.fetchone()[0])
    cursor.close()

    df = load_team_game_stats(conn)

    print(f"Loaded team-game rows: {len(df):,}")

    series_df = build_series_results(df)

    years = sorted(series_df["year"].dropna().astype(int).unique().tolist())

    create_table(conn)
    replace_years(conn, years)
    insert_rows(conn, series_df)

    conn.close()

    print("")
    print(f"Done. Table built: {TARGET_TABLE}")


if __name__ == "__main__":
    main()