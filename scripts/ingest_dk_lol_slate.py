import os
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

SLATE_DATE = "2026-05-12"
SLATE_NAME = "lpl_main"
SOURCE_FILE = "dk_lol_2026-05-12_lpl_main.csv"


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
    path = SLATE_DIR / SOURCE_FILE

    if not path.exists():
        raise FileNotFoundError(f"Could not find file: {path}")

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
                SLATE_DATE,
                SLATE_NAME,
                SOURCE_FILE,
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
        SLATE_DATE,
        SLATE_NAME,
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
        SLATE_DATE,
        SLATE_NAME,
    )

    print("Rows inserted:", cursor.fetchone()[0])

    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()