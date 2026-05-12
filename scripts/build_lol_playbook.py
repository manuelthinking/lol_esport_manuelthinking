import os
import re
from pathlib import Path
from datetime import datetime

import pandas as pd
import pyodbc
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

MANUAL_STARTERS_PATH = BASE_DIR / "data" / "manual_starters.csv"

DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

SLATE_DATA_DIR = BASE_DIR / "data" / "slate_data"


def detect_latest_slate():
    pattern = re.compile(r"dk_lol_(\d{4}-\d{2}-\d{2})_(.+)\.csv$", re.IGNORECASE)

    files = list(SLATE_DATA_DIR.glob("dk_lol_*.csv"))

    if not files:
        raise FileNotFoundError(f"No dk_lol_*.csv files found in {SLATE_DATA_DIR}")

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
                "modified": path.stat().st_mtime,
            }
        )

    if not parsed:
        raise FileNotFoundError(f"No valid dk_lol_YYYY-MM-DD_slate.csv files found in {SLATE_DATA_DIR}")

    latest = max(parsed, key=lambda x: (x["slate_date"], x["modified"]))
    return latest["slate_date"], latest["slate_name"], latest["path"]


SLATE_DATE, SLATE_NAME, SLATE_FILE = detect_latest_slate()
OUTPUT_FILE = REPORT_DIR / f"lol_playbook_{SLATE_DATE}_{SLATE_NAME}.html"

POSITION_ORDER = {
    "top": 1,
    "jng": 2,
    "mid": 3,
    "bot": 4,
    "sup": 5,
}


def connect():
    conn_str = (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_DATABASE};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


def norm_text(v):
    if pd.isna(v):
        return ""
    return str(v).strip().lower()


def parse_game_info(game_info):
    if not game_info:
        return None, None, None

    parts = str(game_info).split(" ", 1)
    matchup = parts[0]
    game_time = parts[1] if len(parts) > 1 else ""

    if "@" not in matchup:
        return None, None, game_time

    away, home = matchup.split("@", 1)
    return away.strip(), home.strip(), game_time.strip()


def fmt_num(v, decimals=1):
    try:
        if pd.isna(v):
            return "-"
        return f"{float(v):.{decimals}f}"
    except Exception:
        return "-"


def fmt_salary(v):
    try:
        if pd.isna(v):
            return "-"
        return f"${int(v):,}"
    except Exception:
        return "-"


def rating_badge(score):
    try:
        score = float(score)
    except Exception:
        return "neutral"

    if score >= 1.0:
        return "elite"
    if score >= 0.35:
        return "good"
    if score <= -0.75:
        return "bad"
    return "neutral"


def edge_class(v):
    try:
        v = float(v)
    except Exception:
        return "neutral"

    if v > 0:
        return "edge-pos"
    if v < 0:
        return "edge-neg"
    return "neutral"


def projection_label(team_rating, opp_rating):
    if team_rating is None or opp_rating is None or pd.isna(team_rating) or pd.isna(opp_rating):
        return "N/A"
    return "WIN" if team_rating >= opp_rating else "LOSS"


def load_manual_starters():
    if not MANUAL_STARTERS_PATH.exists():
        print(f"No manual starters file found: {MANUAL_STARTERS_PATH}")
        return None

    manual = pd.read_csv(MANUAL_STARTERS_PATH)
    manual.columns = manual.columns.str.strip().str.lower()

    required = ["teamname", "position", "playername", "is_starter"]
    missing = [c for c in required if c not in manual.columns]

    if missing:
        print(f"Manual starters file is missing columns: {missing}")
        return None

    manual["is_starter"] = pd.to_numeric(
        manual["is_starter"],
        errors="coerce",
    ).fillna(0).astype(int)

    manual = manual[manual["is_starter"] == 1].copy()

    if manual.empty:
        print("Manual starters file exists, but no players have is_starter = 1.")
        return None

    manual["team_key"] = manual["teamname"].apply(norm_text)
    manual["position_key"] = manual["position"].apply(norm_text)
    manual["player_key"] = manual["playername"].apply(norm_text)

    manual = manual[
        ["team_key", "position_key", "player_key"]
    ].drop_duplicates()

    print(f"Manual starters loaded: {len(manual):,}")
    return manual


def load_data(conn):
    sql = """
        WITH latest_rating AS (
            SELECT
                r.*,
                ROW_NUMBER() OVER (
                    PARTITION BY r.player_name, r.position
                    ORDER BY r.season DESC, r.games DESC, r.rating_score DESC
                ) AS rn
            FROM dbo.lol_player_lane_ratings r
            WHERE r.season = YEAR(?)
        )
        SELECT
            dk.slate_date,
            dk.slate_name,
            dk.dk_position,
            dk.roster_position,
            dk.player_name AS dk_player_name,
            dk.dk_player_id,
            dk.salary,
            dk.game_info,
            dk.team_abbrev,
            dk.avg_points_per_game AS dk_avg_points,

            r.season,
            r.league,
            r.team_name AS rating_team_name,
            r.player_name AS rating_player_name,
            r.player_id,
            r.position,
            r.games,
            r.win_rate,
            r.avg_dk,
            r.avg_dk_edge,
            r.avg_kills,
            r.avg_deaths,
            r.avg_assists,
            r.avg_kill_edge,
            r.avg_death_edge,
            r.avg_assist_edge,
            r.avg_gold_diff_10_edge,
            r.avg_xp_diff_10_edge,
            r.avg_cs_diff_10_edge,
            r.avg_dpm_edge,
            r.rating_score,

            CASE 
                WHEN dk.salary > 0 THEN r.avg_dk / (dk.salary / 1000.0)
                ELSE NULL
            END AS dk_value,

            CASE 
                WHEN dk.salary > 0 THEN r.rating_score / (dk.salary / 1000.0)
                ELSE NULL
            END AS rating_value

        FROM dbo.dk_lol_slate_player dk
        LEFT JOIN latest_rating r
            ON LOWER(LTRIM(RTRIM(dk.player_name))) = LOWER(LTRIM(RTRIM(r.player_name)))
            AND r.rn = 1
        WHERE dk.slate_date = ?
            AND dk.slate_name = ?
            AND UPPER(LTRIM(RTRIM(ISNULL(dk.dk_position, '')))) NOT IN ('CPT', 'CAPTAIN', 'TEAM')
            AND UPPER(LTRIM(RTRIM(ISNULL(dk.roster_position, '')))) NOT IN ('CPT', 'CAPTAIN')
    """

    df = pd.read_sql(sql, conn, params=[SLATE_DATE, SLATE_DATE, SLATE_NAME])

    if df.empty:
        return df

    df["away_team"], df["home_team"], df["game_time"] = zip(
        *df["game_info"].apply(parse_game_info)
    )

    df["team_key"] = df["team_abbrev"].apply(norm_text)
    df["player_key"] = df["dk_player_name"].apply(norm_text)
    df["position_key"] = df["position"].apply(norm_text)

    before = len(df)

    df = df.sort_values(
        ["team_key", "position_key", "player_key", "salary"],
        ascending=[True, True, True, False],
    )

    df = df.drop_duplicates(
        subset=["team_key", "position_key", "player_key"],
        keep="first",
    ).copy()

    after = len(df)

    if before != after:
        print(f"Removed duplicate DK player rows: {before - after}")

    return df


def apply_manual_starters(df, manual):
    if manual is None:
        print("No valid manual starter file. Using all non-CPT DK rows.")
        return df

    starter_df = df.merge(
        manual,
        on=["team_key", "position_key", "player_key"],
        how="inner",
    )

    if starter_df.empty:
        print("WARNING: Manual starters did not match any DK players.")
        print("Using all non-CPT DK rows.")
        return df

    starter_df = starter_df.drop_duplicates(
        subset=["team_key", "position_key", "player_key"],
        keep="first",
    ).copy()

    counts = (
        starter_df.groupby("team_abbrev")["dk_player_name"]
        .nunique()
        .sort_index()
    )

    print("")
    print("Starter counts by team:")
    print(counts.to_string())
    print("")

    bad_counts = counts[counts != 5]

    if not bad_counts.empty:
        print("WARNING: Some teams do not have exactly 5 starters marked.")
        print(bad_counts.to_string())
        print("")

    return starter_df


def team_summary(team_df):
    player_df = team_df.copy()

    if player_df.empty:
        return {
            "avg_rating": None,
            "avg_dk": None,
            "avg_dk_edge": None,
            "avg_kill_edge": None,
            "avg_death_edge": None,
            "avg_assist_edge": None,
            "avg_gold10_edge": None,
            "avg_xp10_edge": None,
            "avg_cs10_edge": None,
            "avg_dpm_edge": None,
            "avg_value": None,
            "starter_games": 0,
        }

    return {
        "avg_rating": player_df["rating_score"].mean(),
        "avg_dk": player_df["avg_dk"].mean(),
        "avg_dk_edge": player_df["avg_dk_edge"].mean(),
        "avg_kill_edge": player_df["avg_kill_edge"].mean(),
        "avg_death_edge": player_df["avg_death_edge"].mean(),
        "avg_assist_edge": player_df["avg_assist_edge"].mean(),
        "avg_gold10_edge": player_df["avg_gold_diff_10_edge"].mean(),
        "avg_xp10_edge": player_df["avg_xp_diff_10_edge"].mean(),
        "avg_cs10_edge": player_df["avg_cs_diff_10_edge"].mean(),
        "avg_dpm_edge": player_df["avg_dpm_edge"].mean(),
        "avg_value": player_df["dk_value"].mean(),
        "starter_games": player_df["games"].sum(),
    }


def matchup_edge_rows(away, home, away_summary, home_summary):
    metrics = [
        ("Team Rating", "avg_rating", 2, "higher", "overall player/team strength rating"),
        ("Avg DK", "avg_dk", 1, "higher", "average DraftKings fantasy production"),
        ("DK Edge", "avg_dk_edge", 1, "higher", "fantasy production above/below lane average"),
        ("Kill Edge", "avg_kill_edge", 2, "higher", "kill production above/below lane average"),
        ("Death Edge", "avg_death_edge", 2, "lower", "death rate relative to lane average"),
        ("Assist Edge", "avg_assist_edge", 2, "higher", "assist production above/below lane average"),
        ("DPM Edge", "avg_dpm_edge", 1, "higher", "damage per minute advantage"),
        ("DK Value", "avg_value", 2, "higher", "DraftKings points per $1K salary"),
    ]

    rows = ""
    away_wins = 0
    home_wins = 0

    for label, key, decimals, direction, explanation in metrics:
        av = away_summary.get(key)
        hv = home_summary.get(key)

        if pd.isna(av) or pd.isna(hv):
            summary = "Not enough data available."
            summary_class = "neutral"
        else:
            if direction == "lower":
                if av <= hv:
                    winner = away
                    margin = hv - av
                    away_wins += 1
                else:
                    winner = home
                    margin = av - hv
                    home_wins += 1

                summary = f"{winner} is better by {fmt_num(margin, decimals)}. Lower is better for {label.lower()} because it means fewer deaths/negative events."
            else:
                if av >= hv:
                    winner = away
                    margin = av - hv
                    away_wins += 1
                else:
                    winner = home
                    margin = hv - av
                    home_wins += 1

                summary = f"{winner} is better by {fmt_num(margin, decimals)}. Higher is better for {label.lower()} because it reflects stronger {explanation}."

            summary_class = "edge-pos" if winner == home else "edge-neg"

        rows += f"""
        <tr>
            <td>{label}</td>
            <td>{fmt_num(av, decimals)}</td>
            <td>{fmt_num(hv, decimals)}</td>
            <td class="{summary_class}"><b>{summary}</b></td>
        </tr>
        """

    if away_wins > home_wins:
        lean = away
        lean_class = "win"
    elif home_wins > away_wins:
        lean = home
        lean_class = "loss"
    else:
        lean = "EVEN"
        lean_class = "neutral"

    return rows, lean, lean_class, away_wins, home_wins


def build_matchup_edge_block(away, home, away_summary, home_summary):
    rows, lean, lean_class, away_wins, home_wins = matchup_edge_rows(
        away,
        home,
        away_summary,
        home_summary,
    )

    return f"""
<table class="edge-table">
    <thead>
        <tr>
            <th>Metric</th>
            <th>{away}</th>
            <th>{home}</th>
            <th>Summary</th>
        </tr>
    </thead>
    <tbody>
        {rows}
    </tbody>
</table>
    """


def build_player_rows(team_df):
    flex_df = team_df.copy()

    flex_df["pos_sort"] = flex_df["position_key"].map(POSITION_ORDER).fillna(99)

    flex_df = flex_df.sort_values(
        ["pos_sort", "salary"],
        ascending=[True, False],
    )

    flex_df = flex_df.drop_duplicates(
        subset=["team_key", "position_key", "player_key"],
        keep="first",
    )

    rows = ""

    for _, r in flex_df.iterrows():
        badge = rating_badge(r["rating_score"])

        rows += f"""
        <tr>
            <td class="name">{r['dk_player_name']}</td>
            <td>{fmt_salary(r['salary'])}</td>
            <td>{str(r['position']).upper() if pd.notna(r['position']) else '-'}</td>
            <td>{fmt_num(r['games'], 0)}</td>
            <td>{fmt_num(r['avg_dk'], 1)}</td>
            <td>{fmt_num(r['avg_dk_edge'], 1)}</td>
            <td>{fmt_num(r['avg_kill_edge'], 2)}</td>
            <td>{fmt_num(r['avg_death_edge'], 2)}</td>
            <td>{fmt_num(r['avg_dpm_edge'], 1)}</td>
            <td><span class="badge {badge}">{fmt_num(r['rating_score'], 2)}</span></td>
            <td>{fmt_num(r['dk_value'], 2)}</td>
        </tr>
        """

    return rows


def build_team_block(team_name, team_df, summary, prediction):
    pred_class = "win" if prediction == "WIN" else "loss" if prediction == "LOSS" else "neutral"

    player_rows = build_player_rows(team_df)

    return f"""
    <div class="team-card">
        <div class="team-header">
            <h2>{team_name}</h2>
            <div class="prediction {pred_class}">{prediction}</div>
        </div>

        <div class="summary-grid">
            <div><span>Avg Rating</span><b>{fmt_num(summary['avg_rating'], 2)}</b></div>
            <div><span>Avg DK</span><b>{fmt_num(summary['avg_dk'], 1)}</b></div>
            <div><span>DK Edge</span><b>{fmt_num(summary['avg_dk_edge'], 1)}</b></div>
            <div><span>Kill Edge</span><b>{fmt_num(summary['avg_kill_edge'], 2)}</b></div>
            <div><span>Death Edge</span><b>{fmt_num(summary['avg_death_edge'], 2)}</b></div>
            <div><span>DPM Edge</span><b>{fmt_num(summary['avg_dpm_edge'], 1)}</b></div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Name</th>
                    <th>DK $</th>
                    <th>POS</th>
                    <th>G</th>
                    <th>Avg DK</th>
                    <th>DK Edge</th>
                    <th>Kill Edge</th>
                    <th>Death Edge</th>
                    <th>DPM</th>
                    <th>Rating</th>
                    <th>Value</th>
                </tr>
            </thead>
            <tbody>
                {player_rows}
            </tbody>
        </table>
    </div>
    """


def build_html(df):
    generated_at = datetime.now().strftime("%Y-%m-%d %I:%M %p")

    game_sections = ""

    for game_info, game_df in df.groupby("game_info", dropna=False):
        away, home, game_time = parse_game_info(game_info)

        if not away or not home:
            continue

        away_df = game_df[game_df["team_abbrev"] == away].copy()
        home_df = game_df[game_df["team_abbrev"] == home].copy()

        away_summary = team_summary(away_df)
        home_summary = team_summary(home_df)

        away_prediction = projection_label(
            away_summary["avg_rating"],
            home_summary["avg_rating"],
        )

        home_prediction = projection_label(
            home_summary["avg_rating"],
            away_summary["avg_rating"],
        )

        matchup_edge_block = build_matchup_edge_block(
            away,
            home,
            away_summary,
            home_summary,
        )

        game_sections += f"""
        <section class="matchup">
            <div class="matchup-title">
                <h1>{away} vs {home}</h1>
                <span>{game_time}</span>
            </div>

            {matchup_edge_block}

            <div class="teams">
                {build_team_block(away, away_df, away_summary, away_prediction)}
                {build_team_block(home, home_df, home_summary, home_prediction)}
            </div>
        </section>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>LoL Playbook - {SLATE_DATE} {SLATE_NAME}</title>
        <style>
            body {{
                font-family: Arial, Helvetica, sans-serif;
                background: #f4f4f4;
                color: #111;
                margin: 0;
                padding: 24px;
            }}

            .page-title {{
                text-align: center;
                margin-bottom: 24px;
            }}

            .page-title h1 {{
                margin: 0;
                font-size: 38px;
                letter-spacing: 1px;
            }}

            .page-title p {{
                margin: 6px 0;
                font-size: 14px;
                color: #555;
            }}

            .matchup {{
                background: white;
                border: 1px solid #ccc;
                margin-bottom: 28px;
                padding: 16px;
                box-shadow: 0 2px 6px rgba(0,0,0,0.08);
            }}

            .matchup-title {{
                background: #222;
                color: white;
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px 16px;
                margin-bottom: 16px;
            }}

            .matchup-title h1 {{
                font-size: 24px;
                margin: 0;
            }}

            .matchup-title span {{
                font-size: 14px;
                color: #ddd;
            }}

            .matchup-edge-card {{
                border: 1px solid #bbb;
                background: #fff;
                margin-bottom: 16px;
            }}

            .edge-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 12px 14px;
                background: #f0f0f0;
                border-bottom: 1px solid #ccc;
            }}

            .edge-header h2 {{
                margin: 0;
                font-size: 18px;
            }}

            .edge-header p {{
                margin: 4px 0 0;
                font-size: 12px;
                color: #555;
            }}

            .edge-lean {{
                padding: 8px 14px;
                font-weight: bold;
                color: white;
                border-radius: 4px;
            }}

            .edge-lean.win {{
                background: #23c552;
            }}

            .edge-lean.loss {{
                background: #f84f31;
            }}

            .edge-lean.neutral {{
                background: #999;
            }}

            .edge-table th {{
                background: #444;
            }}

            .edge-pos {{
                color: #0b7a28;
                font-weight: bold;
            }}

            .edge-neg {{
                color: #b00020;
                font-weight: bold;
            }}

            .teams {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 18px;
            }}

            .team-card {{
                border: 1px solid #bbb;
                background: #fafafa;
            }}

            .team-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                background: #666;
                color: white;
                padding: 10px 12px;
            }}

            .team-header h2 {{
                margin: 0;
                font-size: 20px;
            }}

            .prediction {{
                padding: 8px 16px;
                color: white;
                font-weight: bold;
                border-radius: 2px;
            }}

            .prediction.win {{
                background: #23c552;
            }}

            .prediction.loss {{
                background: #f84f31;
            }}

            .prediction.neutral {{
                background: #999;
            }}

            .summary-grid {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                border-bottom: 1px solid #ccc;
            }}

            .summary-grid div {{
                padding: 8px;
                border-right: 1px solid #ddd;
                border-bottom: 1px solid #ddd;
                text-align: center;
                background: white;
            }}

            .summary-grid span {{
                display: block;
                font-size: 11px;
                color: #666;
                text-transform: uppercase;
            }}

            .summary-grid b {{
                font-size: 16px;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 12px;
            }}

            th {{
                background: #e60000;
                color: white;
                padding: 7px 4px;
                font-size: 11px;
            }}

            td {{
                padding: 6px 4px;
                border-bottom: 1px solid #ddd;
                text-align: center;
            }}

            td.name {{
                text-align: left;
                font-weight: bold;
                color: #245c2b;
            }}

            .badge {{
                display: inline-block;
                min-width: 42px;
                padding: 3px 6px;
                border-radius: 4px;
                font-weight: bold;
            }}

            .badge.elite {{
                background: #1ed760;
                color: #111;
            }}

            .badge.good {{
                background: #c7f9cc;
                color: #111;
            }}

            .badge.neutral {{
                background: #eee;
                color: #111;
            }}

            .badge.bad {{
                background: #ffb3b3;
                color: #111;
            }}

            .footer {{
                text-align: center;
                font-size: 12px;
                color: #666;
                margin-top: 24px;
            }}
        </style>
    </head>

    <body>
        <div class="page-title">
            <h1>LEAGUE OF LEGENDS PLAYBOOK</h1>
            <p>{SLATE_DATE} — {SLATE_NAME.upper()}</p>
            <p>Generated: {generated_at}</p>
        </div>

        {game_sections}

        <div class="footer">
            Built from non-captain DK salary data + manual starters + internal lane ratings + team matchup metrics.
        </div>
    </body>
    </html>
    """

    return html


def main():
    conn = connect()

    cursor = conn.cursor()
    cursor.execute("SELECT DB_NAME()")
    print("Connected DB:", cursor.fetchone()[0])
    cursor.close()

    manual = load_manual_starters()

    df = load_data(conn)
    conn.close()

    print(f"Detected slate date: {SLATE_DATE}")
    print(f"Detected slate name: {SLATE_NAME}")
    print(f"Detected slate file: {SLATE_FILE}")
    print(f"Slate rows loaded before starter filter: {len(df):,}")

    if df.empty:
        print("No slate rows found.")
        return

    df = apply_manual_starters(df, manual)

    print(f"Slate rows loaded after starter filter: {len(df):,}")

    html = build_html(df)
    OUTPUT_FILE.write_text(html, encoding="utf-8")

    print(f"Report written to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()