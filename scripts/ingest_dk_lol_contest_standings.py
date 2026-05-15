import os
import re
import uuid
import zipfile
from pathlib import Path

import pandas as pd
import pyodbc
from dotenv import load_dotenv


load_dotenv()

CONTEST_DIR = Path(r"C:\DailyDFS\LoL\data\contest-standings")


def get_conn():
    server = os.getenv("DB_SERVER", r"DESKTOP-I9OLS14\SQLEXPRESS")
    database = os.getenv("DB_DATABASE", "lol_esports")
    driver = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


def parse_zip_name(zip_path: Path):
    """
    Expected:
    contest-standings-20260506_lck_lpl.zip
    """
    m = re.search(r"contest-standings-(\d{8})_(.+)\.zip$", zip_path.name, re.I)
    if not m:
        raise ValueError(f"Could not parse slate_date/slate_name from: {zip_path.name}")

    date_raw = m.group(1)
    slate_name = m.group(2).lower()

    slate_date = f"{date_raw[:4]}-{date_raw[4:6]}-{date_raw[6:8]}"
    return slate_date, slate_name


def parse_contest_id(csv_name: str):
    """
    Expected:
    contest-standings-190196001.csv
    """
    m = re.search(r"contest-standings-(\d+)\.csv$", csv_name, re.I)
    return m.group(1) if m else None


def clean_float(value):
    if pd.isna(value):
        return None
    value = str(value).replace("%", "").replace(",", "").strip()
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def clean_int(value):
    if pd.isna(value):
        return None
    value = str(value).replace(",", "").strip()
    if value == "":
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def clean_str(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    return value if value else None


def ingest_zip(conn, zip_path: Path):
    slate_date, slate_name = parse_zip_name(zip_path)
    etl_batch_id = str(uuid.uuid4())

    print(f"\nProcessing: {zip_path.name}")
    print(f"Slate date: {slate_date}")
    print(f"Slate name: {slate_name}")
    print(f"Batch ID: {etl_batch_id}")

    total_standings = 0
    total_ownership = 0

    with zipfile.ZipFile(zip_path, "r") as z:
        csv_files = [f for f in z.namelist() if f.lower().endswith(".csv")]

        if not csv_files:
            print("No CSV files found.")
            return 0, 0

        for csv_name in csv_files:
            contest_id = parse_contest_id(Path(csv_name).name)

            print(f"Reading CSV: {csv_name}")
            print(f"Contest ID: {contest_id}")

            with z.open(csv_name) as f:
                df = pd.read_csv(f)

            df.columns = [c.strip() for c in df.columns]

            required_cols = [
                "Rank",
                "EntryId",
                "EntryName",
                "TimeRemaining",
                "Points",
                "Lineup",
                "Player",
                "Roster Position",
                "%Drafted",
                "FPTS",
            ]

            missing = [c for c in required_cols if c not in df.columns]
            if missing:
                raise ValueError(f"Missing columns in {csv_name}: {missing}")

            cursor = conn.cursor()

            # Prevent duplicate loads for same source file.
            cursor.execute(
                """
                DELETE FROM raw.dk_lol_contest_standings
                WHERE source_zip = ? AND source_csv = ?;
                """,
                zip_path.name,
                csv_name,
            )

            cursor.execute(
                """
                DELETE FROM raw.dk_lol_player_ownership
                WHERE source_zip = ? AND source_csv = ?;
                """,
                zip_path.name,
                csv_name,
            )

            standings_rows = []
            ownership_rows = []

            for idx, row in df.iterrows():
                source_row_number = idx + 2  # CSV row number after header

                lineup_raw = clean_str(row.get("Lineup"))
                entry_id = clean_str(row.get("EntryId"))
                rank_num = clean_int(row.get("Rank"))

                if lineup_raw is not None or entry_id is not None or rank_num is not None:
                    standings_rows.append(
                        (
                            slate_date,
                            slate_name,
                            contest_id,
                            None,
                            rank_num,
                            entry_id,
                            clean_str(row.get("EntryName")),
                            clean_int(row.get("TimeRemaining")),
                            clean_float(row.get("Points")),
                            lineup_raw,
                            zip_path.name,
                            csv_name,
                            source_row_number,
                            etl_batch_id,
                        )
                    )

                player_name = clean_str(row.get("Player"))

                if player_name is not None:
                    ownership_rows.append(
                        (
                            slate_date,
                            slate_name,
                            contest_id,
                            None,
                            player_name,
                            clean_str(row.get("Roster Position")),
                            clean_float(row.get("%Drafted")),
                            clean_float(row.get("FPTS")),
                            zip_path.name,
                            csv_name,
                            source_row_number,
                            etl_batch_id,
                        )
                    )

            if standings_rows:
                cursor.fast_executemany = True
                cursor.executemany(
                    """
                    INSERT INTO raw.dk_lol_contest_standings (
                        slate_date,
                        slate_name,
                        contest_id,
                        contest_name,
                        rank_num,
                        entry_id,
                        entry_name,
                        time_remaining,
                        points,
                        lineup_raw,
                        source_zip,
                        source_csv,
                        source_row_number,
                        etl_batch_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    standings_rows,
                )

            if ownership_rows:
                cursor.fast_executemany = True
                cursor.executemany(
                    """
                    INSERT INTO raw.dk_lol_player_ownership (
                        slate_date,
                        slate_name,
                        contest_id,
                        contest_name,
                        player_name,
                        roster_position,
                        ownership_pct,
                        actual_fp,
                        source_zip,
                        source_csv,
                        source_row_number,
                        etl_batch_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    ownership_rows,
                )

            conn.commit()

            print(f"Inserted standings rows: {len(standings_rows)}")
            print(f"Inserted ownership rows: {len(ownership_rows)}")

            total_standings += len(standings_rows)
            total_ownership += len(ownership_rows)

    return total_standings, total_ownership


def main():
    if not CONTEST_DIR.exists():
        raise FileNotFoundError(f"Folder not found: {CONTEST_DIR}")

    zip_files = sorted(CONTEST_DIR.glob("*.zip"))

    if not zip_files:
        print(f"No ZIP files found in: {CONTEST_DIR}")
        return

    conn = get_conn()

    grand_standings = 0
    grand_ownership = 0

    try:
        for zip_path in zip_files:
            standings_count, ownership_count = ingest_zip(conn, zip_path)
            grand_standings += standings_count
            grand_ownership += ownership_count

    finally:
        conn.close()

    print("\nDone.")
    print(f"Total standings rows inserted: {grand_standings}")
    print(f"Total ownership rows inserted: {grand_ownership}")


if __name__ == "__main__":
    main()