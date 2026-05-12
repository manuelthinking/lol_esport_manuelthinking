import argparse
from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]

SLATE_DIR = BASE_DIR / "data" / "slate_data"
OUT_PATH = BASE_DIR / "data" / "manual_starters.csv"


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


def find_latest_dk_file() -> Path:
    candidates = list(SLATE_DIR.glob("dk_lol_*.csv"))

    if not candidates:
        raise FileNotFoundError(
            f"No dk_lol_*.csv files found in {SLATE_DIR}"
        )

    # newest modified file wins
    latest = max(candidates, key=lambda p: p.stat().st_mtime)

    return latest


def clean_dk(df: pd.DataFrame) -> pd.DataFrame:
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

    out["position"] = (
        out["position"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    out["position"] = (
        out["position"]
        .map(POSITION_MAP)
        .fillna(out["position"].str.lower())
    )

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
            "is_starter",
            "notes",
        ]
    ]

    out = out.drop_duplicates()

    out = out.sort_values(
        ["teamname", "position", "playername"]
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

    df = pd.read_csv(dk_path)

    starters = clean_dk(df)

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
    print("Next step:")
    print("Open manual_starters.csv")
    print("Set is_starter = 1 for today's starters")


if __name__ == "__main__":
    main()