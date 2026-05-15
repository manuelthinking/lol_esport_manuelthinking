import os
import re
from pathlib import Path

import pandas as pd
import pyodbc
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
SLATE_DIR = BASE_DIR / "data" / "slate_data"

DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")


def detect_latest_slate_file():
    pattern = re.compile(r"dk_lol_(\d{4}-\d{2}-\d{2})_(.+)\.csv$", re.IGNORECASE)

    files = list(SLATE_DIR.glob("dk_lol_*.csv"))

    if not files:
        raise FileNotFoundError(f"No dk_lol_*.csv files found in {SLATE_DIR}")

    parsed = []

    for path in files:
        match = pattern.match(path.name)
        if not match:
            continue

        parsed.append(
            {
                "path": path,
                "slate_date": match.group(1),
                "slate_name": match.group(2),
                "source_file": path.name,
                "modified": path.stat().st_mtime,
            }
        )

    if not parsed:
        raise FileNotFoundError(
            f"No valid dk_lol_YYYY-MM-DD_slate.csv files found in {SLATE_DIR}"
        )

    latest = max(parsed, key=lambda x: (x["slate_date"], x["modified"]))

    return latest


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
        if pd.isna(v):
            return None
        return int(float(v))
    except Exception:
        return None


def safe_float(v):
    try:
        if pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def main():
    slate = detect_latest_slate_file()

    path = slate["path"]
    slate_date = slate["slate_date"]
    slate_name = slate["slate_name"]
    source_file = slate["source_file"]

    print(f"Detected slate date: {slate_date}")
    print(f"Detected slate name: {slate_name}")
    print(f"Detected source file: {path}")

    conn = connect()
    cursor = conn.cursor()

    cursor.execute("SELECT DB_NAME()")
    print("Connected DB:", cursor.fetchone()[0])

    df = pd.read_csv(path)

    print(f"Loaded DK salary rows: {len(df):,}")
    print(df.head())

    rows = []

    for _, row in df.iterrows():
        rows.append(
            (
                slate_date,
                slate_name,
                source_file,
                row.get("Position"),
                row.get("Name + ID"),
                row.get("Name"),
                str(row.get("ID")) if not pd.isna(row.get("ID")) else None,
                row.get("Roster Position"),
                safe_int(row.get("Salary")),
                row.get("Game Info"),
                row.get("TeamAbbrev"),
                safe_float(row.get("AvgPointsPerGame")),
            )
        )

    cursor.execute(
        """
        DELETE FROM dbo.dk_lol_slate_player
        WHERE slate_date = ?
          AND slate_name = ?
        """,
        slate_date,
        slate_name,
    )
    conn.commit()

    insert_sql = """
        INSERT INTO dbo.dk_lol_slate_player (
            slate_date,
            slate_name,
            source_file,
            dk_position,
            name_id,
            player_name,
            dk_player_id,
            roster_position,
            salary,
            game_info,
            team_abbrev,
            avg_points_per_game
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    cursor.fast_executemany = False
    cursor.executemany(insert_sql, rows)
    conn.commit()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM dbo.dk_lol_slate_player
        WHERE slate_date = ?
          AND slate_name = ?
        """,
        slate_date,
        slate_name,
    )

    print("Rows inserted:", cursor.fetchone()[0])

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()