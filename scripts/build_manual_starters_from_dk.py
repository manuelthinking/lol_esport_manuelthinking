import argparse
import re
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

SLATE_DIR = BASE_DIR / "data" / "slate_data"
DATA_DIR = BASE_DIR / "data"
OUT_PATH = DATA_DIR / "manual_starters.csv"


POSITION_MAP = {
    "TOP": "top",
    "JNG": "jng",
    "JUNGLE": "jng",
    "MID": "mid",
    "ADC": "bot",
    "BOT": "bot",
    "SUP": "sup",
    "SUPPORT": "sup",
}


VALID_PLAYER_POSITIONS = {"top", "jng", "mid", "bot", "sup"}


def normalize_text(value):
    if pd.isna(value):
        return ""

    return re.sub(r"\s+", " ", str(value).strip()).lower()


def normalize_position(value):
    if pd.isna(value):
        return ""

    value = str(value).upper().strip()
    return POSITION_MAP.get(value, value.lower())


def find_latest_dk_file() -> Path:
    candidates = list(SLATE_DIR.glob("dk_lol_*.csv"))

    if not candidates:
        raise FileNotFoundError(
            f"No dk_lol_*.csv files found in {SLATE_DIR}"
        )

    # newest modified file wins
    latest = max(candidates, key=lambda p: p.stat().st_mtime)

    return latest


def parse_slate_date_from_filename(path: Path):
    """
    Expected:
    dk_lol_2026-05-17_lpl_lck_main.csv
    """
    match = re.search(
        r"dk_lol_(\d{4}-\d{2}-\d{2})_(.+)\.csv$",
        path.name,
        re.IGNORECASE,
    )

    if not match:
        return None

    return pd.to_datetime(match.group(1), errors="coerce")


def find_oracle_files():
    files = []

    # Main yearly files:
    # data/oracle_elixir_2024.csv
    # data/oracle_elixir_2025.csv
    # data/oracle_elixir_2026.csv
    files.extend(DATA_DIR.glob("oracle_elixir_*.csv"))

    # Manual download backup:
    # data/manual_downloads/2026_LoL_esports_match_data_from_OraclesElixir.csv
    manual_dir = DATA_DIR / "manual_downloads"
    if manual_dir.exists():
        files.extend(manual_dir.glob("*OraclesElixir*.csv"))
        files.extend(manual_dir.glob("*Oracle*.csv"))

    # Deduplicate while keeping stable order
    seen = set()
    out = []

    for path in files:
        key = str(path).lower()
        if key not in seen and path.exists():
            seen.add(key)
            out.append(path)

    return out


def load_last_played_lookup():
    """
    Builds a lookup table with each player's most recent recorded game
    from Oracle Elixir files.

    Expected useful Oracle columns:
      - date
      - league
      - teamname
      - position
      - playername
    """

    oracle_files = find_oracle_files()

    if not oracle_files:
        print("Warning: No Oracle Elixir files found. Last played columns will be blank.")
        return pd.DataFrame(
            columns=[
                "player_key",
                "last_played_date",
                "last_played_teamname",
                "last_played_league",
                "last_played_position",
            ]
        )

    frames = []

    for path in oracle_files:
        try:
            df = pd.read_csv(path, low_memory=False)
        except Exception as e:
            print(f"Warning: Could not read Oracle file {path}: {e}")
            continue

        df.columns = df.columns.str.strip().str.lower()

        required_cols = ["date", "playername", "teamname", "position"]

        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            print(f"Warning: Skipping {path.name}. Missing columns: {missing}")
            continue

        use_cols = ["date", "playername", "teamname", "position"]

        if "league" in df.columns:
            use_cols.append("league")

        temp = df[use_cols].copy()

        if "league" not in temp.columns:
            temp["league"] = ""

        temp["game_date"] = pd.to_datetime(temp["date"], errors="coerce")
        temp["playername"] = temp["playername"].astype(str).str.strip()
        temp["teamname"] = temp["teamname"].astype(str).str.strip()
        temp["position"] = temp["position"].apply(normalize_position)
        temp["league"] = temp["league"].astype(str).str.strip()

        temp = temp[
            temp["game_date"].notna()
            & temp["playername"].notna()
            & (temp["playername"].str.strip() != "")
            & temp["position"].isin(VALID_PLAYER_POSITIONS)
        ].copy()

        if temp.empty:
            continue

        temp["player_key"] = temp["playername"].apply(normalize_text)

        frames.append(temp)

    if not frames:
        print("Warning: Oracle files loaded, but no usable player-game rows were found.")
        return pd.DataFrame(
            columns=[
                "player_key",
                "last_played_date",
                "last_played_teamname",
                "last_played_league",
                "last_played_position",
            ]
        )

    all_games = pd.concat(frames, ignore_index=True)

    all_games = all_games.sort_values(
        ["player_key", "game_date"],
        ascending=[True, False],
    )

    latest = (
        all_games
        .drop_duplicates(subset=["player_key"], keep="first")
        .copy()
    )

    latest = latest.rename(
        columns={
            "game_date": "last_played_date",
            "teamname": "last_played_teamname",
            "league": "last_played_league",
            "position": "last_played_position",
        }
    )

    latest = latest[
        [
            "player_key",
            "last_played_date",
            "last_played_teamname",
            "last_played_league",
            "last_played_position",
        ]
    ]

    latest["last_played_date"] = latest["last_played_date"].dt.strftime("%Y-%m-%d")

    return latest


def clean_dk(df: pd.DataFrame, slate_date=None) -> pd.DataFrame:
    df.columns = df.columns.str.strip()

    required_cols = ["Name", "Position", "TeamAbbrev"]

    missing = [c for c in required_cols if c not in df.columns]

    if missing:
        raise ValueError(f"Missing DK columns: {missing}")

    out = df[required_cols].copy()

    out = out.rename(
        columns={
            "Name": "playername",
            "Position": "position",
            "TeamAbbrev": "teamname",
        }
    )

    out["position"] = out["position"].apply(normalize_position)

    out["playername"] = (
        out["playername"]
        .astype(str)
        .str.strip()
    )

    out["teamname"] = (
        out["teamname"]
        .astype(str)
        .str.strip()
    )

    # remove team slots / captain rows
    invalid_positions = {"team", "captain", "cpt"}

    out = out[
        ~out["position"].isin(invalid_positions)
    ].copy()

    out = out[
        out["playername"].notna()
        & (out["playername"] != "")
    ]

    out = out[
        out["teamname"].notna()
        & (out["teamname"] != "")
    ]

    out["player_key"] = out["playername"].apply(normalize_text)

    last_played = load_last_played_lookup()

    out = out.merge(
        last_played,
        on="player_key",
        how="left",
    )

    if slate_date is not None and not pd.isna(slate_date):
        slate_date = pd.to_datetime(slate_date, errors="coerce")

        out["days_since_last_played"] = (
            slate_date
            - pd.to_datetime(out["last_played_date"], errors="coerce")
        ).dt.days
    else:
        out["days_since_last_played"] = pd.NA

    out["last_played_date"] = out["last_played_date"].fillna("")
    out["last_played_teamname"] = out["last_played_teamname"].fillna("")
    out["last_played_league"] = out["last_played_league"].fillna("")
    out["last_played_position"] = out["last_played_position"].fillna("")

    # optional league detection from filename later
    out["league"] = ""

    # manual starter toggle
    out["is_starter"] = 0

    # optional notes
    out["notes"] = ""

    out = out[
        [
            "league",
            "teamname",
            "position",
            "playername",
            "last_played_date",
            "days_since_last_played",
            "last_played_teamname",
            "last_played_league",
            "last_played_position",
            "is_starter",
            "notes",
        ]
    ]

    out = out.drop_duplicates()

    out = out.sort_values(
        ["teamname", "position", "days_since_last_played", "playername"],
        na_position="last",
    )

    return out


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dk-file",
        default=None,
        help="Optional exact DK file path",
    )

    args = parser.parse_args()

    if args.dk_file:
        dk_path = Path(args.dk_file)
    else:
        dk_path = find_latest_dk_file()

    print(f"Using DK slate file: {dk_path}")

    slate_date = parse_slate_date_from_filename(dk_path)

    if slate_date is not None and not pd.isna(slate_date):
        print(f"Detected slate date: {slate_date.strftime('%Y-%m-%d')}")
    else:
        print("Warning: Could not detect slate date from DK filename.")

    df = pd.read_csv(dk_path)

    starters = clean_dk(df, slate_date=slate_date)

    OUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    starters.to_csv(
        OUT_PATH,
        index=False,
    )

    print("")
    print(f"Created: {OUT_PATH}")
    print(f"Rows: {len(starters):,}")
    print("")
    print("Added columns:")
    print("  last_played_date")
    print("  days_since_last_played")
    print("  last_played_teamname")
    print("  last_played_league")
    print("  last_played_position")
    print("")
    print("Next step:")
    print("Open manual_starters.csv")
    print("Use last_played_date / days_since_last_played to help decide starters")
    print("Set is_starter = 1 for today's starters")


if __name__ == "__main__":
    main()