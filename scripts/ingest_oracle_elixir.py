import os
import json
from pathlib import Path

import gdown
import pandas as pd
import pyodbc
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
MANUAL_DIR = DATA_DIR / "manual_downloads"

DATA_DIR.mkdir(exist_ok=True)
MANUAL_DIR.mkdir(exist_ok=True)

DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

YEARS = [2026]

CSV_URLS = {
    2024: "https://drive.google.com/uc?id=1IjIEhLc9n8eLKeY-yh_YigKVWbhgGBsN",
    2025: "https://drive.google.com/uc?id=1v6LRphp2kYciU4SXp0PCjEMuev1bDejc",
    2026: "https://drive.google.com/uc?id=1hnpbrUpBMS1TZI7IovfpKeZfWJH1Aptm",
}

TARGET_LEAGUES = {"LCK", "LPL"}
STARTER_POSITIONS = {"top", "jng", "mid", "bot", "sup"}


def connect():
    conn_str = (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_DATABASE};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


def is_valid_csv(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False

    first_bytes = path.read_text(errors="ignore")[:300].lower()
    if "<html" in first_bytes or "<!doctype html" in first_bytes:
        return False

    return True


def find_manual_file(year: int) -> Path | None:
    candidates = sorted(
        MANUAL_DIR.glob(f"*{year}*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for path in candidates:
        if is_valid_csv(path):
            print(f"Using manual fallback file: {path}")
            return path

    print(f"No valid manual fallback CSV found in {MANUAL_DIR}")
    return None


def download_year(year: int) -> Path | None:
    url = CSV_URLS.get(year)

    if not url:
        print(f"No URL configured for {year}. Checking manual folder.")
        return find_manual_file(year)

    out_path = DATA_DIR / f"oracle_elixir_{year}.csv"

    print(f"Downloading {year}: {url}")

    try:
        gdown.download(
            url=url,
            output=str(out_path),
            quiet=False,
        )
    except Exception as e:
        print(f"Google download failed for {year}: {e}")
        print("Checking manual_downloads folder instead...")
        return find_manual_file(year)

    if not is_valid_csv(out_path):
        print(f"Downloaded file was not valid for {year}. Checking manual_downloads folder instead...")
        return find_manual_file(year)

    print(f"Saved {out_path}")
    return out_path


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = (
        df.columns
        .str.lower()
        .str.strip()
        .str.replace(" ", "_", regex=False)
        .str.replace("%", "pct", regex=False)
    )
    return df


def load_csv(path: Path, year: int) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df = clean_columns(df)

    df = df[df["league"].isin(TARGET_LEAGUES)].copy()

    df["source_year"] = year
    df["source_file"] = path.name

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date

    df = df.where(pd.notnull(df), None)

    print(f"{year}: {len(df):,} LCK/LPL rows loaded from {path.name}")
    return df


def delete_year_from_staging(year: int):
    with connect() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM raw.oracle_elixir_match_data_staging
            WHERE source_year = ?
            """,
            year,
        )
        conn.commit()

    print(f"Deleted existing staging rows for {year}")


def insert_df(df: pd.DataFrame):
    if df.empty:
        print("No rows to insert.")
        return

    rows = []

    for _, row in df.iterrows():
        clean_row = {}

        for k, v in row.items():
            if pd.isna(v):
                clean_row[k] = None
            else:
                clean_row[k] = str(v)

        rows.append(
            (
                int(row.get("source_year")),
                row.get("source_file"),
                json.dumps(clean_row),
            )
        )

    with connect() as conn:
        cursor = conn.cursor()
        cursor.fast_executemany = True

        cursor.executemany(
            """
            INSERT INTO raw.oracle_elixir_match_data_staging
                (source_year, source_file, row_json)
            VALUES (?, ?, ?)
            """,
            rows,
        )

        conn.commit()

    print(f"Inserted {len(rows):,} rows into raw.oracle_elixir_match_data_staging")


def ensure_latest_starters_table():
    with connect() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            IF OBJECT_ID('raw.oracle_elixir_latest_starters', 'U') IS NULL
            BEGIN
                CREATE TABLE raw.oracle_elixir_latest_starters (
                    league NVARCHAR(50) NOT NULL,
                    teamname NVARCHAR(255) NOT NULL,
                    position NVARCHAR(20) NOT NULL,
                    playername NVARCHAR(255) NOT NULL,
                    latest_game_date DATE NULL,
                    latest_gameid NVARCHAR(100) NULL,
                    side NVARCHAR(20) NULL,
                    source_year INT NULL,
                    source_file NVARCHAR(255) NULL,
                    refreshed_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
                );
            END
            """
        )

        conn.commit()

    print("Ensured raw.oracle_elixir_latest_starters exists")


def refresh_latest_starters(df: pd.DataFrame):
    required_cols = ["league", "teamname", "position", "playername", "date"]

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required starter columns: {missing}")

    starters = df.copy()

    starters["position"] = starters["position"].astype(str).str.lower().str.strip()
    starters["playername"] = starters["playername"].astype(str).str.strip()
    starters["teamname"] = starters["teamname"].astype(str).str.strip()
    starters["date_sort"] = pd.to_datetime(starters["date"], errors="coerce")

    starters = starters[
        starters["position"].isin(STARTER_POSITIONS)
        & starters["playername"].notna()
        & (starters["playername"] != "")
        & (starters["playername"].str.lower() != "none")
        & starters["teamname"].notna()
        & (starters["teamname"] != "")
        & starters["date_sort"].notna()
    ].copy()

    if starters.empty:
        print("No starter rows found.")
        return

    sort_cols = ["league", "teamname", "position", "date_sort"]
    ascending = [True, True, True, False]

    if "gameid" in starters.columns:
        sort_cols.append("gameid")
        ascending.append(False)

    starters = starters.sort_values(sort_cols, ascending=ascending)

    latest = starters.drop_duplicates(
        subset=["league", "teamname", "position"],
        keep="first",
    )

    rows = []

    for _, row in latest.iterrows():
        rows.append(
            (
                row.get("league"),
                row.get("teamname"),
                row.get("position"),
                row.get("playername"),
                row.get("date"),
                row.get("gameid") if "gameid" in latest.columns else None,
                row.get("side") if "side" in latest.columns else None,
                int(row.get("source_year")),
                row.get("source_file"),
            )
        )

    with connect() as conn:
        cursor = conn.cursor()
        cursor.fast_executemany = True

        cursor.execute("TRUNCATE TABLE raw.oracle_elixir_latest_starters;")

        cursor.executemany(
            """
            INSERT INTO raw.oracle_elixir_latest_starters
                (
                    league,
                    teamname,
                    position,
                    playername,
                    latest_game_date,
                    latest_gameid,
                    side,
                    source_year,
                    source_file
                )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

        conn.commit()

    print(f"Refreshed {len(rows):,} latest starter rows")


def main():
    all_loaded = []

    for year in YEARS:
        path = download_year(year)

        if not path:
            print(f"No valid file found for {year}. Keeping existing DB rows unchanged.")
            continue

        df = load_csv(path, year)

        if df.empty:
            print(f"Loaded file for {year}, but no LCK/LPL rows found. Keeping existing DB rows unchanged.")
            continue

        # Only delete after we have a valid loaded dataframe.
        delete_year_from_staging(year)
        insert_df(df)

        all_loaded.append(df)

    if all_loaded:
        combined_df = pd.concat(all_loaded, ignore_index=True)
        ensure_latest_starters_table()
        refresh_latest_starters(combined_df)
    else:
        print("No new data loaded. Latest starters were not refreshed.")

    print("Done.")


if __name__ == "__main__":
    main()