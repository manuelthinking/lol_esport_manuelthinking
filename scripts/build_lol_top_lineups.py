import argparse
import heapq
import os
from itertools import product
from pathlib import Path

import pandas as pd
import pyodbc
from dotenv import load_dotenv


# =========================
# Setup
# =========================

load_dotenv()

BASE_DIR = Path(r"C:\DailyDFS\LoL")
MANUAL_STARTERS_PATH = BASE_DIR / "data" / "manual_starters.csv"
OUTPUT_DIR = BASE_DIR / "lineups"
OUTPUT_DIR.mkdir(exist_ok=True)

DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

POSITION_ORDER = {
    "top": 1,
    "jng": 2,
    "mid": 3,
    "bot": 4,
    "adc": 4,
    "sup": 5,
}


# =========================
# DB Helpers
# =========================

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


def first_non_null(series):
    vals = series.dropna().astype(str).str.strip()
    vals = vals[vals != ""]
    if len(vals) == 0:
        return None
    return vals.iloc[0]


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


def detect_latest_slate(conn):
    sql = """
        SELECT TOP 1
            slate_date,
            slate_name,
            COUNT(*) AS rows
        FROM dbo.dk_lol_slate_player
        GROUP BY slate_date, slate_name
        ORDER BY slate_date DESC, COUNT(*) DESC
    """
    df = pd.read_sql(sql, conn)

    if df.empty:
        raise ValueError("No slates found in dbo.dk_lol_slate_player.")

    return str(df.iloc[0]["slate_date"]), str(df.iloc[0]["slate_name"])


# =========================
# Data Load
# =========================

def load_manual_starters():
    if not MANUAL_STARTERS_PATH.exists():
        return None

    manual = pd.read_csv(MANUAL_STARTERS_PATH)
    manual.columns = manual.columns.str.strip().str.lower()

    required = ["teamname", "position", "playername", "is_starter"]
    missing = [c for c in required if c not in manual.columns]

    if missing:
        print(f"manual_starters.csv missing columns: {missing}")
        return None

    manual["is_starter"] = pd.to_numeric(
        manual["is_starter"],
        errors="coerce",
    ).fillna(0).astype(int)

    manual = manual[manual["is_starter"] == 1].copy()

    if manual.empty:
        return None

    manual["team_key"] = manual["teamname"].apply(norm_text)
    manual["position_key"] = manual["position"].apply(norm_text)
    manual["player_key"] = manual["playername"].apply(norm_text)

    return manual[["team_key", "position_key", "player_key"]].drop_duplicates()


def load_slate_players(conn, slate_date, slate_name):
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

    df = pd.read_sql(sql, conn, params=[slate_date, slate_date, slate_name])

    if df.empty:
        return df

    parsed = df["game_info"].apply(parse_game_info)
    df["away_team"] = parsed.apply(lambda x: x[0])
    df["home_team"] = parsed.apply(lambda x: x[1])
    df["game_time"] = parsed.apply(lambda x: x[2])

    df["team_key"] = df["team_abbrev"].apply(norm_text)
    df["player_key"] = df["dk_player_name"].apply(norm_text)
    df["position_key"] = df["position"].apply(norm_text)

    df = df.sort_values(
        ["team_key", "position_key", "player_key", "salary"],
        ascending=[True, True, True, False],
    )

    df = df.drop_duplicates(
        subset=["team_key", "position_key", "player_key"],
        keep="first",
    ).copy()

    return df


def load_team_rows(conn, slate_date, slate_name):
    sql = """
        SELECT
            slate_date,
            slate_name,
            dk_position,
            roster_position,
            player_name AS team_player_name,
            dk_player_id,
            salary,
            game_info,
            team_abbrev,
            avg_points_per_game AS dk_avg_points
        FROM dbo.dk_lol_slate_player
        WHERE slate_date = ?
            AND slate_name = ?
            AND UPPER(LTRIM(RTRIM(ISNULL(dk_position, '')))) = 'TEAM'
            AND UPPER(LTRIM(RTRIM(ISNULL(roster_position, '')))) = 'TEAM'
    """

    df = pd.read_sql(sql, conn, params=[slate_date, slate_name])

    if df.empty:
        return df

    parsed = df["game_info"].apply(parse_game_info)
    df["away_team"] = parsed.apply(lambda x: x[0])
    df["home_team"] = parsed.apply(lambda x: x[1])
    df["game_time"] = parsed.apply(lambda x: x[2])

    return df


def apply_manual_starters(df, manual):
    if manual is None:
        print("No valid manual starters file found. Using all non-CPT player rows.")
        return df

    starter_df = df.merge(
        manual,
        on=["team_key", "position_key", "player_key"],
        how="inner",
    )

    if starter_df.empty:
        print("Manual starters did not match any DK players. Using all non-CPT player rows.")
        return df

    starter_df = starter_df.drop_duplicates(
        subset=["team_key", "position_key", "player_key"],
        keep="first",
    ).copy()

    return starter_df


# =========================
# Team / Series Projection Logic
# =========================

def build_team_overview(df):
    d = df.copy()

    team_df = (
        d.groupby(["team_abbrev", "game_info"], dropna=False)
        .agg(
            profile_team_name=("rating_team_name", first_non_null),
            players=("dk_player_name", "nunique"),
            total_salary=("salary", "sum"),
            avg_salary=("salary", "mean"),
            avg_dk=("avg_dk", "mean"),
            total_avg_dk=("avg_dk", "sum"),
            avg_rating=("rating_score", "mean"),
            avg_dk_edge=("avg_dk_edge", "mean"),
            avg_kill_edge=("avg_kill_edge", "mean"),
            avg_death_edge=("avg_death_edge", "mean"),
            avg_assist_edge=("avg_assist_edge", "mean"),
            avg_dpm_edge=("avg_dpm_edge", "mean"),
            avg_value=("dk_value", "mean"),
            starter_games=("games", "sum"),
        )
        .reset_index()
    )

    top_player = (
        d.sort_values("avg_dk", ascending=False)
        .groupby("team_abbrev")
        .head(1)[["team_abbrev", "dk_player_name", "position", "salary", "avg_dk", "rating_score", "dk_value"]]
        .rename(
            columns={
                "dk_player_name": "top_player",
                "position": "top_pos",
                "salary": "top_salary",
                "avg_dk": "top_avg_dk",
                "rating_score": "top_rating",
                "dk_value": "top_value",
            }
        )
    )

    team_df = team_df.merge(top_player, on="team_abbrev", how="left")

    team_df["proj_per_1k_salary"] = team_df.apply(
        lambda r: r["total_avg_dk"] / (r["total_salary"] / 1000)
        if r["total_salary"] else 0,
        axis=1,
    )

    return team_df.sort_values(["avg_rating", "total_avg_dk"], ascending=False)


def get_slate_profile_team_names(df):
    teams = []

    if "rating_team_name" in df.columns:
        teams.extend(
            df["rating_team_name"]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
            .tolist()
        )

    if "team_abbrev" in df.columns:
        teams.extend(
            df["team_abbrev"]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
            .tolist()
        )

    return sorted(set([t for t in teams if t]))


def load_series_profiles_for_slate(conn, profile_team_names):
    if not profile_team_names:
        return pd.DataFrame()

    placeholders = ",".join(["?"] * len(profile_team_names))

    sql = f"""
        SELECT
            teamname,
            league,
            series_result,
            series_count,
            first_series_date,
            last_series_date,

            avg_player_dk_fp_with_gnp,
            avg_player_dk_fp_base,
            avg_player_gnp_bonus_total_5,

            avg_team_kills,
            avg_kills_per_game,
            avg_team_deaths,
            avg_deaths_per_game,
            kill_death_ratio,
            assist_per_kill,

            avg_game_length_minutes,
            avg_total_game_length_minutes,

            avg_team_slot_dk_fp_with_gnp,
            avg_team_slot_dk_per_game,

            avg_dragons,
            avg_barons,
            avg_towers,
            avg_firstbloods,

            avg_gold_diff_15,
            avg_xp_diff_15,
            avg_cs_diff_15,

            series_dfs_score,
            bloodiness_score,
            clean_stomp_score,
            profile_label
        FROM dbo.lol_team_series_profiles
        WHERE teamname IN ({placeholders})
            AND league IN ('LPL', 'LCK')
        ORDER BY teamname, league, series_result
    """

    return pd.read_sql(sql, conn, params=profile_team_names)


def build_slate_predictions(team_df, profiles_df):
    if team_df.empty or profiles_df.empty:
        return pd.DataFrame()

    teams = team_df.copy()
    profiles = profiles_df.copy()

    if "profile_team_name" in teams.columns:
        teams["team_merge_key"] = (
            teams["profile_team_name"]
            .fillna(teams["team_abbrev"])
            .astype(str)
            .str.strip()
        )
    else:
        teams["team_merge_key"] = teams["team_abbrev"].astype(str).str.strip()

    profiles["team_merge_key"] = profiles["teamname"].astype(str).str.strip()

    slate_cols = [
        "team_merge_key",
        "team_abbrev",
        "profile_team_name",
        "game_info",
        "players",
        "total_salary",
        "total_avg_dk",
        "avg_rating",
        "avg_dk_edge",
        "avg_kill_edge",
        "avg_death_edge",
        "avg_dpm_edge",
        "avg_value",
        "top_player",
        "top_avg_dk",
    ]

    slate_cols = [c for c in slate_cols if c in teams.columns]
    slate_strength = teams[slate_cols].copy()

    profile_pivot = profiles.pivot_table(
        index=["team_merge_key", "league"],
        columns="series_result",
        values=[
            "series_count",
            "avg_player_dk_fp_with_gnp",
            "avg_team_slot_dk_fp_with_gnp",
            "avg_team_kills",
            "avg_kills_per_game",
            "avg_team_deaths",
            "avg_game_length_minutes",
            "series_dfs_score",
            "bloodiness_score",
            "clean_stomp_score",
        ],
        aggfunc="max",
    )

    profile_pivot.columns = [
        f"{metric}_{result}".replace("-", "_")
        for metric, result in profile_pivot.columns
    ]

    profile_pivot = profile_pivot.reset_index()

    pred = slate_strength.merge(
        profile_pivot,
        on="team_merge_key",
        how="left",
    )

    numeric_cols = pred.select_dtypes(include=["number"]).columns.tolist()
    pred[numeric_cols] = pred[numeric_cols].fillna(0)

    pred["score_2_0"] = pred.get("series_dfs_score_2_0", 0)
    pred["score_2_1"] = pred.get("series_dfs_score_2_1", 0)
    pred["score_1_2"] = pred.get("series_dfs_score_1_2", 0)
    pred["score_0_2"] = pred.get("series_dfs_score_0_2", 0)

    pred["best_path"] = pred.apply(
        lambda r: "2-1 Ceiling" if r["score_2_1"] > r["score_2_0"] else "2-0 Sweep",
        axis=1,
    )

    pred["best_path_score"] = pred[["score_2_0", "score_2_1"]].max(axis=1)

    for col in ["avg_rating", "total_avg_dk", "avg_kill_edge", "avg_dk_edge", "avg_value"]:
        if col not in pred.columns:
            pred[col] = 0

    pred["slate_stack_score"] = (
        (pred["avg_rating"] * 25.0)
        + (pred["total_avg_dk"] * 1.20)
        + (pred["avg_kill_edge"] * 12.0)
        + (pred["avg_dk_edge"] * 4.0)
        + (pred["avg_value"] * 10.0)
        + (pred["best_path_score"] * 0.35)
    )

    blood_cols = [
        c for c in [
            "bloodiness_score_2_1",
            "bloodiness_score_1_2",
            "bloodiness_score_2_0",
        ]
        if c in pred.columns
    ]

    pred["bloodbath_score"] = pred[blood_cols].max(axis=1) if blood_cols else 0
    pred["sweep_score"] = pred.get("clean_stomp_score_2_0", 0)

    return pred.sort_values("slate_stack_score", ascending=False)


def infer_outcome_probabilities(predictions_df):
    if predictions_df.empty:
        return predictions_df

    d = predictions_df.copy()
    rows = []

    for game_info, g in d.groupby("game_info", dropna=False):
        g = g.copy()

        if len(g) < 2:
            for _, r in g.iterrows():
                row = r.to_dict()
                row.update({
                    "strength_gap": 0,
                    "p_2_0": 0.25,
                    "p_2_1": 0.30,
                    "p_1_2": 0.30,
                    "p_0_2": 0.15,
                })
                rows.append(row)
            continue

        for idx, r in g.iterrows():
            opp = g[g.index != idx].iloc[0]

            stack_gap = float(r.get("slate_stack_score", 0)) - float(opp.get("slate_stack_score", 0))
            rating_gap = float(r.get("avg_rating", 0)) - float(opp.get("avg_rating", 0))

            strength_gap = stack_gap + (rating_gap * 15.0)

            if strength_gap >= 75:
                p_2_0, p_2_1, p_1_2, p_0_2 = 0.44, 0.34, 0.15, 0.07
            elif strength_gap >= 30:
                p_2_0, p_2_1, p_1_2, p_0_2 = 0.34, 0.36, 0.21, 0.09
            elif strength_gap >= -30:
                p_2_0, p_2_1, p_1_2, p_0_2 = 0.22, 0.30, 0.30, 0.18
            elif strength_gap >= -75:
                p_2_0, p_2_1, p_1_2, p_0_2 = 0.12, 0.24, 0.38, 0.26
            else:
                p_2_0, p_2_1, p_1_2, p_0_2 = 0.07, 0.16, 0.35, 0.42

            row = r.to_dict()
            row.update({
                "strength_gap": strength_gap,
                "p_2_0": p_2_0,
                "p_2_1": p_2_1,
                "p_1_2": p_1_2,
                "p_0_2": p_0_2,
            })
            rows.append(row)

    out = pd.DataFrame(rows)

    out["win_path_probability"] = out["p_2_0"] + out["p_2_1"]
    out["loss_path_probability"] = out["p_1_2"] + out["p_0_2"]

    out["expected_outcome_score"] = (
        out["p_2_0"] * out.get("score_2_0", 0)
        + out["p_2_1"] * out.get("score_2_1", 0)
        + out["p_1_2"] * out.get("score_1_2", 0)
        + out["p_0_2"] * out.get("score_0_2", 0)
    )

    out["expected_team_dk"] = (
        out["p_2_0"] * out.get("avg_player_dk_fp_with_gnp_2_0", 0)
        + out["p_2_1"] * out.get("avg_player_dk_fp_with_gnp_2_1", 0)
        + out["p_1_2"] * out.get("avg_player_dk_fp_with_gnp_1_2", 0)
        + out["p_0_2"] * out.get("avg_player_dk_fp_with_gnp_0_2", 0)
    )

    out["expected_team_slot_dk"] = (
        out["p_2_0"] * out.get("avg_team_slot_dk_fp_with_gnp_2_0", 0)
        + out["p_2_1"] * out.get("avg_team_slot_dk_fp_with_gnp_2_1", 0)
        + out["p_1_2"] * out.get("avg_team_slot_dk_fp_with_gnp_1_2", 0)
        + out["p_0_2"] * out.get("avg_team_slot_dk_fp_with_gnp_0_2", 0)
    )

    out["expected_games"] = (
        out["p_2_0"] * 2
        + out["p_2_1"] * 3
        + out["p_1_2"] * 3
        + out["p_0_2"] * 2
    )

    out["projected_path"] = out[["p_2_0", "p_2_1", "p_1_2", "p_0_2"]].idxmax(axis=1)
    out["projected_path"] = out["projected_path"].replace({
        "p_2_0": "2-0",
        "p_2_1": "2-1",
        "p_1_2": "1-2",
        "p_0_2": "0-2",
    })

    return out


# =========================
# Player / Team Slot Projections
# =========================

def get_position_multiplier(position):
    pos = str(position).lower().strip()

    if pos in ["bot", "adc"]:
        return 1.06
    if pos == "mid":
        return 1.04
    if pos == "jng":
        return 1.02
    if pos == "top":
        return 0.99
    if pos == "sup":
        return 0.90

    return 1.00


def get_position_ceiling_multiplier(position, best_path, bloodbath_score):
    pos = str(position).lower().strip()
    base = 1.45

    if best_path == "2-1 Ceiling":
        base += 0.10

    if bloodbath_score >= 50:
        base += 0.08

    if pos in ["bot", "adc", "mid"]:
        base += 0.08
    elif pos == "jng":
        base += 0.04
    elif pos == "sup":
        base -= 0.08

    return max(1.25, min(base, 1.75))


def build_player_projections(player_df, predictions_df):
    if player_df.empty or predictions_df.empty:
        return pd.DataFrame()

    players = player_df.copy()
    preds = infer_outcome_probabilities(predictions_df)

    pred_cols = [
        "team_abbrev",
        "profile_team_name",
        "league",
        "game_info",
        "slate_stack_score",
        "best_path",
        "best_path_score",
        "score_2_0",
        "score_2_1",
        "score_1_2",
        "score_0_2",
        "bloodbath_score",
        "sweep_score",
        "expected_outcome_score",
        "expected_team_dk",
        "expected_games",
        "projected_path",
        "p_2_0",
        "p_2_1",
        "p_1_2",
        "p_0_2",
        "win_path_probability",
        "loss_path_probability",
        "strength_gap",
    ]

    pred_cols = [c for c in pred_cols if c in preds.columns]

    merged = players.merge(
        preds[pred_cols],
        on=["team_abbrev", "game_info"],
        how="left",
        suffixes=("", "_team"),
    )

    merged["base_dk"] = pd.to_numeric(merged["avg_dk"], errors="coerce")

    if "dk_avg_points" in merged.columns:
        merged["base_dk"] = merged["base_dk"].fillna(
            pd.to_numeric(merged["dk_avg_points"], errors="coerce")
        )

    merged["base_dk"] = merged["base_dk"].fillna(0)

    for col, default in [
        ("p_2_0", 0.25),
        ("p_2_1", 0.30),
        ("p_1_2", 0.30),
        ("p_0_2", 0.15),
    ]:
        merged[col] = pd.to_numeric(merged.get(col, default), errors="coerce").fillna(default)

    merged["expected_games"] = pd.to_numeric(
        merged.get("expected_games", None),
        errors="coerce",
    )

    merged["expected_games"] = merged["expected_games"].fillna(
        (merged["p_2_0"] * 2)
        + (merged["p_2_1"] * 3)
        + (merged["p_1_2"] * 3)
        + (merged["p_0_2"] * 2)
    )

    merged["expected_games"] = merged["expected_games"].clip(2.0, 3.0)
    merged["expected_sweep_bonus"] = merged["p_2_0"] * 20.0

    merged["series_base_dk"] = (
        merged["base_dk"] * merged["expected_games"]
    ) + merged["expected_sweep_bonus"]

    preds_expected_score = pd.to_numeric(
        preds.get("expected_outcome_score", pd.Series([0])),
        errors="coerce",
    ).replace(0, pd.NA).dropna()

    slate_avg_outcome_score = preds_expected_score.mean() if len(preds_expected_score) else 300

    preds_stack = pd.to_numeric(
        preds.get("slate_stack_score", pd.Series([0])),
        errors="coerce",
    ).replace(0, pd.NA).dropna()

    slate_avg_stack = preds_stack.mean() if len(preds_stack) else 250

    merged["expected_outcome_score"] = pd.to_numeric(
        merged["expected_outcome_score"],
        errors="coerce",
    ).fillna(slate_avg_outcome_score)

    merged["slate_stack_score"] = pd.to_numeric(
        merged["slate_stack_score"],
        errors="coerce",
    ).fillna(slate_avg_stack)

    merged["avg_kill_edge"] = pd.to_numeric(merged["avg_kill_edge"], errors="coerce").fillna(0)
    merged["avg_dk_edge"] = pd.to_numeric(merged["avg_dk_edge"], errors="coerce").fillna(0)
    merged["rating_score"] = pd.to_numeric(merged["rating_score"], errors="coerce").fillna(0)
    merged["salary"] = pd.to_numeric(merged["salary"], errors="coerce").fillna(0)

    merged["team_env_mult"] = 1 + ((merged["slate_stack_score"] - slate_avg_stack) / 1200)
    merged["team_env_mult"] = merged["team_env_mult"].clip(0.90, 1.10)

    merged["outcome_mult"] = 1 + ((merged["expected_outcome_score"] - slate_avg_outcome_score) / 1200)
    merged["outcome_mult"] = merged["outcome_mult"].clip(0.92, 1.10)

    merged["player_skill_mult"] = (
        1
        + (merged["rating_score"] * 0.025)
        + (merged["avg_dk_edge"] * 0.004)
        + (merged["avg_kill_edge"] * 0.012)
    )
    merged["player_skill_mult"] = merged["player_skill_mult"].clip(0.85, 1.16)

    merged["position_mult"] = merged["position"].apply(get_position_multiplier)

    merged["loss_path_probability"] = pd.to_numeric(
        merged.get("loss_path_probability", 0.45),
        errors="coerce",
    ).fillna(0.45)

    merged["risk_mult"] = 1 - (merged["loss_path_probability"] * 0.06)
    merged["risk_mult"] = merged["risk_mult"].clip(0.94, 1.02)

    merged["proj_dk"] = (
        merged["series_base_dk"]
        * merged["team_env_mult"]
        * merged["outcome_mult"]
        * merged["player_skill_mult"]
        * merged["position_mult"]
        * merged["risk_mult"]
    )

    merged["proj_dk"] = merged["proj_dk"].clip(lower=0)
    merged["floor_dk"] = merged["proj_dk"] * 0.65

    merged["ceiling_mult"] = merged.apply(
        lambda r: get_position_ceiling_multiplier(
            r.get("position", ""),
            r.get("best_path", ""),
            r.get("bloodbath_score", 0),
        ),
        axis=1,
    )

    merged["ceiling_dk"] = merged["proj_dk"] * merged["ceiling_mult"]

    merged["value_proj"] = merged.apply(
        lambda r: r["proj_dk"] / (r["salary"] / 1000) if r["salary"] else 0,
        axis=1,
    )

    merged["cpt_salary"] = merged["salary"] * 1.5
    merged["cpt_proj_dk"] = merged["proj_dk"] * 1.5
    merged["cpt_value"] = merged.apply(
        lambda r: r["cpt_proj_dk"] / (r["cpt_salary"] / 1000) if r["cpt_salary"] else 0,
        axis=1,
    )

    merged["slot"] = merged["dk_position"].astype(str).str.upper().replace({"BOT": "ADC"})
    merged["pos_sort"] = merged["position_key"].map(POSITION_ORDER).fillna(99)

    return merged.sort_values(
        ["proj_dk", "ceiling_dk", "value_proj"],
        ascending=[False, False, False],
    )


def build_team_slot_projections(team_rows, predictions_df):
    if team_rows.empty:
        return pd.DataFrame()

    teams = team_rows.copy()
    preds = infer_outcome_probabilities(predictions_df)

    pred_cols = [
        "team_abbrev",
        "game_info",
        "profile_team_name",
        "league",
        "slate_stack_score",
        "expected_team_slot_dk",
        "expected_games",
        "projected_path",
        "p_2_0",
        "p_2_1",
        "p_1_2",
        "p_0_2",
        "win_path_probability",
        "strength_gap",
    ]

    pred_cols = [c for c in pred_cols if c in preds.columns]

    out = teams.merge(
        preds[pred_cols],
        on=["team_abbrev", "game_info"],
        how="left",
    )

    out["salary"] = pd.to_numeric(out["salary"], errors="coerce").fillna(0)
    out["dk_avg_points"] = pd.to_numeric(out["dk_avg_points"], errors="coerce").fillna(0)
    out["team_proj_dk"] = pd.to_numeric(out["expected_team_slot_dk"], errors="coerce").fillna(0)

    # Fallback if no historical TEAM-slot profile matched.
    out["team_proj_dk"] = out.apply(
        lambda r: r["team_proj_dk"] if r["team_proj_dk"] > 0 else r["dk_avg_points"],
        axis=1,
    )

    out["team_ceiling_dk"] = out["team_proj_dk"] * 1.35
    out["team_value"] = out.apply(
        lambda r: r["team_proj_dk"] / (r["salary"] / 1000) if r["salary"] else 0,
        axis=1,
    )

    return out.sort_values("team_proj_dk", ascending=False)


# =========================
# Lineup Builder
# =========================

def make_player_records(player_proj_df):
    records = []

    for _, r in player_proj_df.iterrows():
        slot = str(r["slot"]).upper()

        if slot == "BOT":
            slot = "ADC"

        if slot not in ["TOP", "JNG", "MID", "ADC", "SUP"]:
            continue

        name = str(r["dk_player_name"]).strip()
        team = str(r["team_abbrev"]).strip()

        records.append(
            {
                "entity_type": "PLAYER",
                "slot": slot,
                "name": name,
                "team": team,
                "salary": int(round(float(r["salary"]))),
                "proj": float(r["proj_dk"]),
                "ceiling": float(r["ceiling_dk"]),
                "value": float(r["value_proj"]),
                "player_id": str(r.get("dk_player_id", "")),
                "unique_key": f"PLAYER|{team}|{name}",
            }
        )

    return records


def make_team_records(team_proj_df):
    records = []

    for _, r in team_proj_df.iterrows():
        team = str(r["team_abbrev"]).strip()
        name = str(r["team_player_name"]).strip()

        records.append(
            {
                "entity_type": "TEAM",
                "slot": "TEAM",
                "name": name,
                "team": team,
                "salary": int(round(float(r["salary"]))),
                "proj": float(r["team_proj_dk"]),
                "ceiling": float(r["team_ceiling_dk"]),
                "value": float(r["team_value"]),
                "player_id": str(r.get("dk_player_id", "")),
                "unique_key": f"TEAM|{team}|{name}",
            }
        )

    return records


def make_cpt_record(base_record):
    return {
        "entity_type": base_record["entity_type"],
        "slot": "CPT",
        "name": base_record["name"],
        "team": base_record["team"],
        "salary": int(round(base_record["salary"] * 1.5)),
        "proj": base_record["proj"] * 1.5,
        "ceiling": base_record["ceiling"] * 1.5,
        "value": base_record["value"],
        "player_id": base_record["player_id"],
        "unique_key": f"CPT|{base_record['unique_key']}",
    }


def lineup_identity(lineup):
    return {
        f"{slot}:{lineup[slot]['unique_key']}"
        for slot in ["CPT", "TOP", "JNG", "MID", "ADC", "SUP", "TEAM"]
    }


def lineup_diff_count(a, b):
    return len(lineup_identity(a).symmetric_difference(lineup_identity(b)))


def is_diverse_enough(candidate, selected, min_diff):
    for existing in selected:
        if lineup_diff_count(candidate, existing) < min_diff:
            return False
    return True


def get_stack_shape(lineup):
    """
    Returns sorted team-count shape for all 7 roster spots:
    CPT, TOP, JNG, MID, ADC, SUP, TEAM

    Example:
      BLG 4 + HLE 3 = (4, 3)
      BLG 4 + HLE 2 + TES 1 = (4, 2, 1)
    """
    team_counts = {}

    for slot in ["CPT", "TOP", "JNG", "MID", "ADC", "SUP", "TEAM"]:
        team = lineup[slot]["team"]
        team_counts[team] = team_counts.get(team, 0) + 1

    shape = tuple(sorted(team_counts.values(), reverse=True))

    return shape, team_counts


def get_cpt_bonus(source_slot):
    slot = str(source_slot).upper().replace("BOT", "ADC")

    bonus = {
        "ADC": 10.0,
        "MID": 8.0,
        "JNG": 5.0,
        "TOP": -4.0,
        "SUP": -12.0,
        "TEAM": -6.0,
    }

    return bonus.get(slot, 0.0)


def get_stack_shape_bonus(stack_shape):
    if stack_shape == (4, 3):
        return 8.0
    if stack_shape == (4, 2, 1):
        return 4.0
    return 0.0


def build_top_lineups(
    player_proj_df,
    team_proj_df,
    num_lineups=10,
    salary_cap=50000,
    min_cpt_team=3,
    max_team=4,
    min_diff=2,
    max_candidates=25000,
    allowed_stack_shapes=((4, 3), (4, 2, 1)),
    min_team_slot_stack=3,
    allowed_cpt_slots=("ADC", "MID", "JNG"),
    objective_mode="Projection + Structure",
):
    player_records = make_player_records(player_proj_df)
    team_records = make_team_records(team_proj_df)

    if not player_records:
        raise ValueError("No player records available for lineup build.")

    if not team_records:
        raise ValueError("No TEAM records available for lineup build.")

    by_slot = {
        "TOP": [],
        "JNG": [],
        "MID": [],
        "ADC": [],
        "SUP": [],
    }

    for rec in player_records:
        slot = str(rec["slot"]).upper().replace("BOT", "ADC")
        rec["slot"] = slot

        if slot in by_slot:
            by_slot[slot].append(rec)

    for slot, rows in by_slot.items():
        if not rows:
            raise ValueError(f"No players available for required slot: {slot}")

    allowed_cpt_slots = set(
        str(x).upper().replace("BOT", "ADC") for x in allowed_cpt_slots
    )

    # CPT can be any allowed player position, and TEAM only if TEAM is enabled.
    cpt_source_records = []

    for rec in player_records:
        source_slot = str(rec["slot"]).upper().replace("BOT", "ADC")
        rec["source_slot"] = source_slot

        if source_slot in allowed_cpt_slots:
            cpt_source_records.append(rec)

    for rec in team_records:
        rec["source_slot"] = "TEAM"

        if "TEAM" in allowed_cpt_slots:
            cpt_source_records.append(rec)

    cpt_candidates = [make_cpt_record(r) for r in cpt_source_records]

    if not cpt_candidates:
        raise ValueError("No CPT candidates available. Check allowed CPT positions.")

    flex_combos = []

    for top, jng, mid, adc, sup in product(
        by_slot["TOP"],
        by_slot["JNG"],
        by_slot["MID"],
        by_slot["ADC"],
        by_slot["SUP"],
    ):
        flex = {
            "TOP": top,
            "JNG": jng,
            "MID": mid,
            "ADC": adc,
            "SUP": sup,
        }

        keys = [x["unique_key"] for x in flex.values()]

        if len(keys) != len(set(keys)):
            continue

        salary = sum(x["salary"] for x in flex.values())
        proj = sum(x["proj"] for x in flex.values())
        ceiling = sum(x["ceiling"] for x in flex.values())

        flex_combos.append(
            {
                "slots": flex,
                "keys": set(keys),
                "salary": salary,
                "proj": proj,
                "ceiling": ceiling,
            }
        )

    print(f"Flex combos built: {len(flex_combos):,}")
    print(f"CPT candidates: {len(cpt_candidates):,}")
    print(f"TEAM candidates: {len(team_records):,}")
    print(f"Allowed stack shapes: {allowed_stack_shapes}")
    print(f"Allowed CPT slots: {sorted(allowed_cpt_slots)}")
    print(f"TEAM slot must be part of stack >= {min_team_slot_stack}")
    print(f"Objective mode: {objective_mode}")

    heap = []
    counter = 0

    for cpt in cpt_candidates:
        cpt_base_key = cpt["unique_key"].replace("CPT|", "", 1)

        for flex in flex_combos:
            if cpt_base_key in flex["keys"]:
                continue

            for team_slot in team_records:
                if team_slot["unique_key"] in flex["keys"]:
                    continue

                if cpt_base_key == team_slot["unique_key"]:
                    continue

                salary = cpt["salary"] + flex["salary"] + team_slot["salary"]

                if salary > salary_cap:
                    continue

                lineup = {
                    "CPT": cpt,
                    "TOP": flex["slots"]["TOP"],
                    "JNG": flex["slots"]["JNG"],
                    "MID": flex["slots"]["MID"],
                    "ADC": flex["slots"]["ADC"],
                    "SUP": flex["slots"]["SUP"],
                    "TEAM": team_slot,
                }

                stack_shape, team_counts = get_stack_shape(lineup)

                if stack_shape not in allowed_stack_shapes:
                    continue

                if max(team_counts.values()) > max_team:
                    continue

                cpt_team_count = team_counts.get(cpt["team"], 0)

                if cpt_team_count < min_cpt_team:
                    continue

                team_slot_team_count = team_counts.get(team_slot["team"], 0)

                if team_slot_team_count < min_team_slot_stack:
                    continue

                projection = cpt["proj"] + flex["proj"] + team_slot["proj"]
                ceiling = cpt["ceiling"] + flex["ceiling"] + team_slot["ceiling"]

                objective_score = projection

                if objective_mode == "Ceiling":
                    objective_score = ceiling

                elif objective_mode == "Projection + Structure":
                    objective_score = (
                        projection
                        + get_cpt_bonus(cpt.get("source_slot", cpt.get("slot", "")))
                        + get_stack_shape_bonus(stack_shape)
                        + (4.0 if cpt_team_count == 4 else 2.0)
                        + (3.0 if team_slot_team_count == 4 else 1.5)
                    )

                lineup["salary"] = salary
                lineup["proj"] = projection
                lineup["ceiling"] = ceiling
                lineup["objective_score"] = objective_score
                lineup["salary_left"] = salary_cap - salary
                lineup["cpt_team_stack"] = cpt_team_count
                lineup["team_slot_stack"] = team_slot_team_count
                lineup["max_team_count"] = max(team_counts.values())
                lineup["stack_shape"] = "-".join(str(x) for x in stack_shape)
                lineup["captain_source_slot"] = cpt.get("source_slot", cpt.get("slot", ""))

                counter += 1

                item = (objective_score, counter, lineup)

                if len(heap) < max_candidates:
                    heapq.heappush(heap, item)
                else:
                    if objective_score > heap[0][0]:
                        heapq.heapreplace(heap, item)

    candidates = [x[2] for x in heap]
    candidates = sorted(candidates, key=lambda x: x["objective_score"], reverse=True)

    print(f"Candidate lineups retained: {len(candidates):,}")

    selected = []

    for lineup in candidates:
        if is_diverse_enough(lineup, selected, min_diff):
            selected.append(lineup)

        if len(selected) >= num_lineups:
            break

    return selected, len(candidates)



def lineups_to_df(lineups):
    rows = []

    for i, lu in enumerate(lineups, start=1):
        row = {
            "lineup_num": i,
            "CPT": lu["CPT"]["name"],
            "TOP": lu["TOP"]["name"],
            "JNG": lu["JNG"]["name"],
            "MID": lu["MID"]["name"],
            "ADC": lu["ADC"]["name"],
            "SUP": lu["SUP"]["name"],
            "TEAM": lu["TEAM"]["name"],

            "CPT_team": lu["CPT"]["team"],
            "TOP_team": lu["TOP"]["team"],
            "JNG_team": lu["JNG"]["team"],
            "MID_team": lu["MID"]["team"],
            "ADC_team": lu["ADC"]["team"],
            "SUP_team": lu["SUP"]["team"],
            "TEAM_team": lu["TEAM"]["team"],

            "captain_source_slot": lu.get("captain_source_slot"),
            "salary": round(lu["salary"], 0),
            "salary_left": round(lu["salary_left"], 0),
            "projection": round(lu["proj"], 2),
            "ceiling": round(lu["ceiling"], 2),
            "objective_score": round(lu.get("objective_score", lu["proj"]), 2),

            "stack_shape": lu.get("stack_shape"),
            "cpt_team_stack": lu["cpt_team_stack"],
            "team_slot_stack": lu.get("team_slot_stack"),
            "max_team_count": lu["max_team_count"],
        }

        rows.append(row)

    return pd.DataFrame(rows)


# =========================
# Main
# =========================

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--date", default=None, help="Slate date, example: 2026-05-15")
    parser.add_argument("--slate", default=None, help="Slate name, example: lpl_lck_main")
    parser.add_argument("--num-lineups", type=int, default=10)
    parser.add_argument("--salary-cap", type=int, default=50000)
    parser.add_argument("--min-cpt-team", type=int, default=3)
    parser.add_argument("--max-team", type=int, default=4)
    parser.add_argument("--min-diff", type=int, default=1)
    parser.add_argument("--max-candidates", type=int, default=25000)
    parser.add_argument("--no-starters-filter", action="store_true")
    parser.add_argument("--output", default=None)

    args = parser.parse_args()

    if not DB_SERVER or not DB_DATABASE:
        raise ValueError("Missing DB_SERVER or DB_DATABASE in .env")

    conn = connect()

    cursor = conn.cursor()
    cursor.execute("SELECT DB_NAME()")
    print("Connected DB:", cursor.fetchone()[0])
    cursor.close()

    slate_date = args.date
    slate_name = args.slate

    if not slate_date or not slate_name:
        detected_date, detected_slate = detect_latest_slate(conn)
        slate_date = slate_date or detected_date
        slate_name = slate_name or detected_slate

    print(f"Slate date: {slate_date}")
    print(f"Slate name: {slate_name}")

    players = load_slate_players(conn, slate_date, slate_name)
    team_rows = load_team_rows(conn, slate_date, slate_name)

    if players.empty:
        raise ValueError("No non-CPT player rows found for this slate.")

    if team_rows.empty:
        raise ValueError("No TEAM rows found for this slate.")

    print(f"Player rows loaded before starter filter: {len(players):,}")
    print(f"TEAM rows loaded: {len(team_rows):,}")

    if not args.no_starters_filter:
        manual = load_manual_starters()
        players = apply_manual_starters(players, manual)

    print(f"Player rows used after starter filter: {len(players):,}")

    team_df = build_team_overview(players)
    profile_team_names = get_slate_profile_team_names(players)
    profiles_df = load_series_profiles_for_slate(conn, profile_team_names)

    if profiles_df.empty:
        raise ValueError("No LPL/LCK team series profiles matched this slate.")

    predictions_df = build_slate_predictions(team_df, profiles_df)

    if predictions_df.empty:
        raise ValueError("Could not build slate team predictions.")

    player_proj_df = build_player_projections(players, predictions_df)
    team_proj_df = build_team_slot_projections(team_rows, predictions_df)

    print("")
    print("Top player projections:")
    print(
        player_proj_df[
            ["dk_player_name", "team_abbrev", "slot", "salary", "base_dk", "expected_games", "proj_dk", "ceiling_dk"]
        ]
        .head(15)
        .to_string(index=False)
    )

    print("")
    print("TEAM projections:")
    print(
        team_proj_df[
            ["team_player_name", "team_abbrev", "salary", "team_proj_dk", "team_ceiling_dk"]
        ]
        .to_string(index=False)
    )

    lineups = build_top_lineups(
        player_proj_df=player_proj_df,
        team_proj_df=team_proj_df,
        num_lineups=args.num_lineups,
        salary_cap=args.salary_cap,
        min_cpt_team=args.min_cpt_team,
        max_team=args.max_team,
        min_diff=args.min_diff,
        max_candidates=args.max_candidates,
    )

    lineup_df = lineups_to_df(lineups)

    if lineup_df.empty:
        raise ValueError("No valid lineups built. Try lowering min-cpt-team or increasing max-team.")

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = OUTPUT_DIR / f"top_{args.num_lineups}_lol_lineups_{slate_date}_{slate_name}.csv"

    lineup_df.to_csv(output_path, index=False)

    print("")
    print("Top lineups:")
    print(lineup_df.to_string(index=False))

    print("")
    print(f"Lineups written to: {output_path}")

    conn.close()


if __name__ == "__main__":
    main()