import argparse
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

TABLE_NAME = "dbo.lol_team_game_stats"


REQUIRED_COLUMNS = [
    "gameid",
    "league",
    "year",
    "split",
    "playoffs",
    "date",
    "game",
    "patch",
    "participantid",
    "side",
    "position",
    "teamname",
    "gamelength",
    "result",
    "kills",
    "deaths",
    "assists",
    "teamkills",
    "teamdeaths",
    "firstblood",
    "dragons",
    "barons",
    "towers",
    "damagetochampions",
    "dpm",
    "total cs",
    "golddiffat10",
    "xpdiffat10",
    "csdiffat10",
    "golddiffat15",
    "xpdiffat15",
    "csdiffat15",
]

CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252")


def connect():
    conn_str = (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_DATABASE};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


def inspect_oracle_csv(path: Path):
    """Return (is_valid, encoding, reason) without loading the full dataset."""
    if not path.exists():
        return False, None, "file does not exist"
    if path.stat().st_size == 0:
        return False, None, "file is empty"

    with path.open("rb") as f:
        signature = f.read(8)

    # XLSX files are ZIP containers and begin with PK. This catches files that
    # were downloaded/saved as Excel but accidentally given a .csv extension.
    if signature.startswith(b"PK\x03\x04"):
        return False, None, "ZIP/XLSX signature found despite .csv extension"

    if signature.startswith(b"\xd0\xcf\x11\xe0"):
        return False, None, "legacy Excel/XLS signature found despite .csv extension"

    last_error = None
    for encoding in CSV_ENCODINGS:
        try:
            sample = pd.read_csv(path, encoding=encoding, nrows=5, low_memory=False)
        except (UnicodeDecodeError, pd.errors.ParserError, OSError) as exc:
            last_error = exc
            continue

        sample.columns = [str(c).strip() for c in sample.columns]
        missing = [c for c in REQUIRED_COLUMNS if c not in sample.columns]
        if missing:
            preview = ", ".join(missing[:6])
            suffix = "..." if len(missing) > 6 else ""
            return False, encoding, f"missing Oracle columns: {preview}{suffix}"

        return True, encoding, "valid Oracle's Elixir CSV"

    return False, None, f"could not parse as CSV ({last_error})"


def read_oracle_csv(path: Path):
    valid, encoding, reason = inspect_oracle_csv(path)
    if not valid:
        raise ValueError(f"Invalid Oracle's Elixir CSV: {path} ({reason})")

    print(f"Validated Oracle's Elixir CSV ({encoding}): {path}")
    return pd.read_csv(path, encoding=encoding, low_memory=False)


def find_latest_oracle_csv():
    search_dirs = [
        BASE_DIR / "data",
        BASE_DIR / "data" / "raw",
        BASE_DIR / "data" / "oracle_elixir",
        BASE_DIR / "data" / "processed",
        BASE_DIR / "data" / "manual_downloads",
    ]

    candidates = []
    seen = set()

    for folder in search_dirs:
        if not folder.exists():
            continue

        for path in folder.glob("*.csv"):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)

            name = path.name.lower()
            if "oracleselixir" in name or "oracle" in name or "lol_esports_match_data" in name:
                candidates.append(path)

    if not candidates:
        return None

    # Newest first, but select the newest *valid* Oracle CSV rather than
    # blindly trusting the extension or modification time.
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    for path in candidates:
        valid, encoding, reason = inspect_oracle_csv(path)
        if valid:
            print(f"Selected Oracle's Elixir source: {path} [{encoding}]")
            return path
        print(f"Skipping invalid Oracle candidate: {path} -- {reason}")

    return None


def clean_numeric(series):
    return pd.to_numeric(series, errors="coerce").fillna(0)


def calc_player_dk_fp(df):
    kills = clean_numeric(df["kills"])
    assists = clean_numeric(df["assists"])
    deaths = clean_numeric(df["deaths"])
    cs = clean_numeric(df["total cs"])

    ka_bonus = ((kills >= 10) | (assists >= 10)).astype(int) * 2

    return (
        (kills * 3)
        + (assists * 2)
        - deaths
        + (cs * 0.02)
        + ka_bonus
    )


def calc_team_slot_dk_fp(df):
    towers = clean_numeric(df["towers"])
    dragons = clean_numeric(df["dragons"])
    barons = clean_numeric(df["barons"])
    firstblood = clean_numeric(df["firstblood"])
    result = clean_numeric(df["result"])
    gamelength = clean_numeric(df["gamelength"])

    win_under_30_bonus = ((result == 1) & (gamelength < 1800)).astype(int) * 2

    return (
        towers
        + (dragons * 2)
        + (barons * 3)
        + (firstblood * 2)
        + (result * 2)
        + win_under_30_bonus
    )


def validate_columns(df):
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]

    if missing:
        print("")
        print("ERROR: Missing required columns from Oracle's Elixir CSV:")
        for c in missing:
            print(f"  - {c}")

        print("")
        print("Available columns:")
        for c in df.columns:
            print(f"  - {c}")

        raise ValueError("Missing required columns.")


def build_team_game_stats(input_csv):
    print(f"Reading Oracle's Elixir file: {input_csv}")

    df = read_oracle_csv(input_csv)
    df.columns = [c.strip() for c in df.columns]

    validate_columns(df)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["game_date"] = df["date"].dt.date

    numeric_cols = [
        "year",
        "playoffs",
        "game",
        "participantid",
        "gamelength",
        "result",
        "kills",
        "deaths",
        "assists",
        "teamkills",
        "teamdeaths",
        "firstblood",
        "dragons",
        "barons",
        "towers",
        "damagetochampions",
        "dpm",
        "total cs",
        "golddiffat10",
        "xpdiffat10",
        "csdiffat10",
        "golddiffat15",
        "xpdiffat15",
        "csdiffat15",
    ]

    for col in numeric_cols:
        df[col] = clean_numeric(df[col])

    player_df = df[df["position"].isin(["top", "jng", "mid", "bot", "sup"])].copy()
    team_df = df[df["position"].eq("team")].copy()

    if player_df.empty:
        raise ValueError("No player rows found. Expected positions: top, jng, mid, bot, sup.")

    if team_df.empty:
        raise ValueError("No team rows found. Expected position = team.")

    player_df["player_dk_fp"] = calc_player_dk_fp(player_df)

    player_agg = (
        player_df.groupby(["gameid", "teamname"], dropna=False)
        .agg(
            player_count=("position", "count"),
            player_dk_fp_sum=("player_dk_fp", "sum"),
            player_kills_sum=("kills", "sum"),
            player_deaths_sum=("deaths", "sum"),
            player_assists_sum=("assists", "sum"),
            player_cs_sum=("total cs", "sum"),
            player_damage_sum=("damagetochampions", "sum"),
            player_dpm_sum=("dpm", "sum"),
            avg_gold_diff_10=("golddiffat10", "mean"),
            avg_xp_diff_10=("xpdiffat10", "mean"),
            avg_cs_diff_10=("csdiffat10", "mean"),
            avg_gold_diff_15=("golddiffat15", "mean"),
            avg_xp_diff_15=("xpdiffat15", "mean"),
            avg_cs_diff_15=("csdiffat15", "mean"),
        )
        .reset_index()
    )

    team_df["team_slot_dk_fp_base"] = calc_team_slot_dk_fp(team_df)

    base_team = team_df[
        [
            "gameid",
            "league",
            "year",
            "split",
            "playoffs",
            "date",
            "game_date",
            "game",
            "patch",
            "side",
            "teamname",
            "gamelength",
            "result",
            "teamkills",
            "teamdeaths",
            "kills",
            "deaths",
            "assists",
            "firstblood",
            "dragons",
            "barons",
            "towers",
            "team_slot_dk_fp_base",
        ]
    ].copy()

    base_team = base_team.rename(
        columns={
            "game": "game_number",
            "gamelength": "game_length_seconds",
            "result": "is_win",
            "teamkills": "team_kills",
            "teamdeaths": "team_deaths",
            "kills": "team_row_kills",
            "deaths": "team_row_deaths",
            "assists": "team_row_assists",
        }
    )

    opp_map = base_team[["gameid", "teamname"]].copy()
    opp_map = opp_map.merge(
        opp_map,
        on="gameid",
        how="inner",
        suffixes=("", "_opponent"),
    )
    opp_map = opp_map[opp_map["teamname"] != opp_map["teamname_opponent"]]
    opp_map = opp_map.rename(columns={"teamname_opponent": "opponent"})
    opp_map = opp_map[["gameid", "teamname", "opponent"]].drop_duplicates()

    out = base_team.merge(opp_map, on=["gameid", "teamname"], how="left")
    out = out.merge(player_agg, on=["gameid", "teamname"], how="left")

    out["player_count"] = clean_numeric(out["player_count"]).astype(int)
    out["is_win"] = clean_numeric(out["is_win"]).astype(int)
    out["year"] = clean_numeric(out["year"]).astype(int)
    out["playoffs"] = clean_numeric(out["playoffs"]).astype(int)
    out["game_number"] = clean_numeric(out["game_number"]).astype(int)
    out["game_length_minutes"] = out["game_length_seconds"] / 60.0

    out["kill_check_diff"] = out["player_kills_sum"] - out["team_kills"]
    out["death_check_diff"] = out["player_deaths_sum"] - out["team_deaths"]

    final_cols = [
        "gameid", "league", "year", "split", "playoffs", "date", "game_date",
        "game_number", "patch", "side", "teamname", "opponent", "is_win",
        "game_length_seconds", "game_length_minutes", "team_kills", "team_deaths",
        "team_row_kills", "team_row_deaths", "team_row_assists", "firstblood",
        "dragons", "barons", "towers", "player_count", "player_dk_fp_sum",
        "team_slot_dk_fp_base", "player_kills_sum", "player_deaths_sum",
        "player_assists_sum", "player_cs_sum", "player_damage_sum", "player_dpm_sum",
        "avg_gold_diff_10", "avg_xp_diff_10", "avg_cs_diff_10", "avg_gold_diff_15",
        "avg_xp_diff_15", "avg_cs_diff_15", "kill_check_diff", "death_check_diff",
    ]

    out = out[final_cols].copy()
    out = out.sort_values(["game_date", "league", "gameid", "side"], ascending=True)

    print(f"Built team-game rows: {len(out):,}")
    print(f"Unique games: {out['gameid'].nunique():,}")
    print(f"Unique teams: {out['teamname'].nunique():,}")

    bad_player_counts = out[out["player_count"] != 5]
    if not bad_player_counts.empty:
        print("")
        print("WARNING: Some team-game rows do not have exactly 5 player rows.")
        print(bad_player_counts[["gameid", "teamname", "player_count"]].head(20).to_string(index=False))

    bad_kill_checks = out[out["kill_check_diff"].abs() > 0.001]
    if not bad_kill_checks.empty:
        print("")
        print("WARNING: Some player kill sums do not match teamkills.")
        print(bad_kill_checks[["gameid", "teamname", "team_kills", "player_kills_sum", "kill_check_diff"]].head(20).to_string(index=False))

    return out


def create_table(conn):
    sql = f"""
    IF OBJECT_ID('{TABLE_NAME}', 'U') IS NULL
    BEGIN
        CREATE TABLE {TABLE_NAME} (
            gameid NVARCHAR(100) NOT NULL,
            league NVARCHAR(50) NULL,
            [year] INT NULL,
            split NVARCHAR(50) NULL,
            playoffs INT NULL,
            [date] DATETIME2 NULL,
            game_date DATE NULL,
            game_number INT NULL,
            patch FLOAT NULL,
            side NVARCHAR(20) NULL,
            teamname NVARCHAR(255) NOT NULL,
            opponent NVARCHAR(255) NULL,
            is_win INT NULL,
            game_length_seconds FLOAT NULL,
            game_length_minutes FLOAT NULL,
            team_kills FLOAT NULL,
            team_deaths FLOAT NULL,
            team_row_kills FLOAT NULL,
            team_row_deaths FLOAT NULL,
            team_row_assists FLOAT NULL,
            firstblood FLOAT NULL,
            dragons FLOAT NULL,
            barons FLOAT NULL,
            towers FLOAT NULL,
            player_count INT NULL,
            player_dk_fp_sum FLOAT NULL,
            team_slot_dk_fp_base FLOAT NULL,
            player_kills_sum FLOAT NULL,
            player_deaths_sum FLOAT NULL,
            player_assists_sum FLOAT NULL,
            player_cs_sum FLOAT NULL,
            player_damage_sum FLOAT NULL,
            player_dpm_sum FLOAT NULL,
            avg_gold_diff_10 FLOAT NULL,
            avg_xp_diff_10 FLOAT NULL,
            avg_cs_diff_10 FLOAT NULL,
            avg_gold_diff_15 FLOAT NULL,
            avg_xp_diff_15 FLOAT NULL,
            avg_cs_diff_15 FLOAT NULL,
            kill_check_diff FLOAT NULL,
            death_check_diff FLOAT NULL,
            loaded_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
            CONSTRAINT pk_lol_team_game_stats PRIMARY KEY (gameid, teamname)
        );
    END
    """
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()


def replace_years(conn, years):
    placeholders = ",".join(["?"] * len(years))
    sql = f"DELETE FROM {TABLE_NAME} WHERE [year] IN ({placeholders})"
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
    sql = f"INSERT INTO {TABLE_NAME} ({sql_cols}) VALUES ({placeholders})"

    rows = []
    for _, r in df.iterrows():
        row = []
        for c in insert_cols:
            v = r[c]
            if pd.isna(v):
                row.append(None)
            elif c == "date":
                row.append(pd.to_datetime(v).to_pydatetime())
            elif c == "game_date":
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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-csv",
        default=None,
        help="Path to Oracle's Elixir CSV. If omitted, script finds the newest valid local Oracle CSV.",
    )
    args = parser.parse_args()

    if not DB_SERVER or not DB_DATABASE:
        raise ValueError("Missing DB_SERVER or DB_DATABASE in .env")

    if args.input_csv:
        input_csv = Path(args.input_csv)
    else:
        input_csv = find_latest_oracle_csv()

    if input_csv is None or not input_csv.exists():
        raise FileNotFoundError(
            "Could not find a valid Oracle's Elixir CSV. Use --input-csv with the full file path."
        )

    team_game_df = build_team_game_stats(input_csv)
    years = sorted(team_game_df["year"].dropna().astype(int).unique().tolist())

    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT DB_NAME()")
    print("Connected DB:", cursor.fetchone()[0])
    cursor.close()

    create_table(conn)
    replace_years(conn, years)
    insert_rows(conn, team_game_df)
    conn.close()

    print("")
    print(f"Done. Table built: {TABLE_NAME}")


if __name__ == "__main__":
    main()
