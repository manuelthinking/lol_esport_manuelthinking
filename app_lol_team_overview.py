import os
from pathlib import Path

import pandas as pd
import pyodbc
import streamlit as st
from dotenv import load_dotenv


# =========================
# App Setup
# =========================

load_dotenv()

st.set_page_config(
    page_title="LoL Slate Team Overview",
    layout="wide",
)

BASE_DIR = Path(r"C:\DailyDFS\LoL")
MANUAL_STARTERS_PATH = BASE_DIR / "data" / "manual_starters.csv"

DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

POSITION_ORDER = {
    "top": 1,
    "jng": 2,
    "mid": 3,
    "bot": 4,
    "sup": 5,
}


# =========================
# Database Helpers
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


@st.cache_data(ttl=300)
def get_slate_dates():
    conn = connect()
    sql = """
        SELECT DISTINCT slate_date
        FROM dbo.dk_lol_slate_player
        ORDER BY slate_date DESC
    """
    df = pd.read_sql(sql, conn)
    conn.close()
    return df["slate_date"].astype(str).tolist()


@st.cache_data(ttl=300)
def get_slate_names(slate_date):
    conn = connect()
    sql = """
        SELECT DISTINCT slate_name
        FROM dbo.dk_lol_slate_player
        WHERE slate_date = ?
        ORDER BY slate_name
    """
    df = pd.read_sql(sql, conn, params=[slate_date])
    conn.close()
    return df["slate_name"].astype(str).tolist()


def load_manual_starters():
    if not MANUAL_STARTERS_PATH.exists():
        return None

    manual = pd.read_csv(MANUAL_STARTERS_PATH)
    manual.columns = manual.columns.str.strip().str.lower()

    required = ["teamname", "position", "playername", "is_starter"]
    missing = [c for c in required if c not in manual.columns]

    if missing:
        st.warning(f"manual_starters.csv is missing columns: {missing}")
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


@st.cache_data(ttl=300)
def load_data(slate_date, slate_name):
    conn = connect()

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
    conn.close()

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



@st.cache_data(ttl=300)
def load_series_profiles_for_slate(profile_team_names):
    if not profile_team_names:
        return pd.DataFrame()

    conn = connect()

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

    df = pd.read_sql(sql, conn, params=profile_team_names)
    conn.close()

    return df

@st.cache_data(ttl=300)
def load_bayes_matchup_training():
    conn = connect()

    sql = """
        SELECT
            series_date,
            season,
            league,
            teamname,
            opponent_teamname,
            series_result,
            won_series,
            games_played,

            top_kill_edge,
            jng_kill_edge,
            mid_kill_edge,
            bot_kill_edge,
            sup_assist_edge,
            bot_dk_edge,
            team_rating_edge,

            top_kill_bucket,
            jng_kill_bucket,
            mid_kill_bucket,
            bot_kill_bucket,
            sup_assist_bucket,
            bot_dk_bucket,
            team_rating_bucket
        FROM dbo.vw_lol_bayes_matchup_training
        WHERE league IN ('LPL', 'LCK')
    """

    try:
        df = pd.read_sql(sql, conn)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()

    return df


@st.cache_data(ttl=300)
def load_bayes_league_priors():
    conn = connect()

    sql = """
        SELECT
            league,
            team_series_rows,
            league_win_rate,
            league_p_2_0,
            league_p_2_1,
            league_p_1_2,
            league_p_0_2
        FROM dbo.vw_lol_bayes_league_priors
    """

    try:
        df = pd.read_sql(sql, conn)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()

    return df



def beta_smoothed_rate(successes, attempts, league_rate=0.50, prior_weight=12):
    attempts = float(attempts or 0)
    successes = float(successes or 0)
    league_rate = float(league_rate if pd.notna(league_rate) else 0.50)

    prior_successes = league_rate * prior_weight
    prior_attempts = prior_weight

    return (successes + prior_successes) / (attempts + prior_attempts)


@st.cache_data(ttl=300)
def load_bayes_strength_matchups():
    conn = connect()

    sql = """
        SELECT
            series_id,
            league,
            season,
            series_date,
            teamname,
            opponent_teamname,
            series_result,
            won_series,
            games_played,

            team_strength_bucket,
            opponent_strength_bucket,
            strength_matchup_bucket,

            team_mid_strength,
            opp_mid_strength,
            team_bot_strength,
            opp_bot_strength,
            team_sup_strength,
            opp_sup_strength,

            mid_lane_matchup_bucket,
            bot_lane_matchup_bucket,
            sup_lane_matchup_bucket
        FROM dbo.vw_lol_bayes_strength_matchups
        WHERE league IN ('LPL', 'LCK')
          AND season = 2026
    """

    try:
        df = pd.read_sql(sql, conn)
    except Exception as e:
        st.warning(f"Could not load dbo.vw_lol_bayes_strength_matchups: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()

    return df


@st.cache_data(ttl=300)
def load_team_strength_buckets():
    conn = connect()

    sql = """
        SELECT
            league,
            season,
            teamname,
            series_count,
            series_wins,
            series_losses,
            raw_series_win_rate,
            league_win_rate,
            smoothed_series_win_rate,
            team_strength_bucket,
            team_strength_sample_label
        FROM dbo.vw_lol_team_strength_bucket
        WHERE league IN ('LPL', 'LCK')
          AND season = 2026
    """

    try:
        df = pd.read_sql(sql, conn)
    except Exception as e:
        st.warning(f"Could not load dbo.vw_lol_team_strength_bucket: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()

    return df


@st.cache_data(ttl=300)
def load_lane_strength_buckets():
    conn = connect()

    sql = """
        SELECT
            league,
            season,
            teamname,
            position,
            lane_games,
            lane_avg_dk,
            league_position_avg_dk,
            lane_dk_index,
            lane_strength_bucket,
            lane_strength_sample_label
        FROM dbo.vw_lol_lane_strength_bucket
        WHERE league IN ('LPL', 'LCK')
          AND season = 2026
    """

    try:
        df = pd.read_sql(sql, conn)
    except Exception as e:
        st.warning(f"Could not load dbo.vw_lol_lane_strength_bucket: {e}")
        df = pd.DataFrame()
    finally:
        conn.close()

    return df


# =========================
# Data Prep
# =========================

def apply_manual_starters(df, manual):
    if manual is None:
        return df, "No valid manual starters file found. Showing all non-CPT DK rows."

    starter_df = df.merge(
        manual,
        on=["team_key", "position_key", "player_key"],
        how="inner",
    )

    if starter_df.empty:
        return df, "Manual starters did not match any DK players. Showing all non-CPT DK rows."

    starter_df = starter_df.drop_duplicates(
        subset=["team_key", "position_key", "player_key"],
        keep="first",
    ).copy()

    return starter_df, "Using manual starters only."


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
        rating_teams = (
            df["rating_team_name"]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
            .tolist()
        )
        teams.extend(rating_teams)

    if "team_abbrev" in df.columns:
        abbrev_teams = (
            df["team_abbrev"]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
            .tolist()
        )
        teams.extend(abbrev_teams)

    teams = sorted(set([t for t in teams if t]))

    return teams


def format_df(df):
    d = df.copy()

    money_cols = [
        "salary",
        "total_salary",
        "avg_salary",
        "top_salary",
    ]

    num_cols = [
        "avg_dk",
        "total_avg_dk",
        "avg_rating",
        "avg_dk_edge",
        "avg_kill_edge",
        "avg_death_edge",
        "avg_assist_edge",
        "avg_dpm_edge",
        "avg_value",
        "starter_games",
        "top_avg_dk",
        "top_rating",
        "top_value",
        "proj_per_1k_salary",
        "dk_value",
        "rating_value",
        "rating_score",
        "games",

        "avg_player_dk_fp_with_gnp",
        "avg_player_dk_fp_base",
        "avg_player_gnp_bonus_total_5",
        "avg_team_kills",
        "avg_kills_per_game",
        "avg_team_deaths",
        "avg_deaths_per_game",
        "kill_death_ratio",
        "assist_per_kill",
        "avg_game_length_minutes",
        "avg_total_game_length_minutes",
        "avg_team_slot_dk_fp_with_gnp",
        "avg_team_slot_dk_per_game",
        "avg_dragons",
        "avg_barons",
        "avg_towers",
        "avg_firstbloods",
        "avg_gold_diff_15",
        "avg_xp_diff_15",
        "avg_cs_diff_15",
        "series_dfs_score",
        "bloodiness_score",
        "clean_stomp_score",

        "slate_stack_score",
        "best_path_score",
        "score_2_0",
        "score_2_1",
        "score_1_2",
        "score_0_2",
        "bloodbath_score",
        "sweep_score",

        "p_2_0",
        "p_2_1",
        "p_1_2",
        "p_0_2",
        "expected_outcome_score",
        "expected_team_dk",
        "expected_games",
        "win_path_probability",
        "loss_path_probability",
        "strength_gap",

        "base_dk",
        "proj_dk",
        "floor_dk",
        "ceiling_dk",
        "value_proj",
        "cpt_proj_dk",
        "cpt_salary",
        "cpt_value",
        "team_env_mult",
        "player_skill_mult",
        "position_mult",
        "outcome_mult",
        "risk_mult",
        "bayes_win_pct",
        "bayes_p_2_0",
        "bayes_p_2_1",
        "bayes_p_1_2",
        "bayes_p_0_2",
        "team_smoothed_win_rate",
        "opponent_smoothed_win_rate",
        "team_mid_dk_index",
        "opp_mid_dk_index",
        "team_bot_dk_index",
        "opp_bot_dk_index",
        "team_sup_dk_index",
        "opp_sup_dk_index",
        "winner_bayes_win_pct",
        "winner_bayes_2_0_pct",
        "winner_bayes_2_1_pct",
        "confidence_gap",
    ]

    for col in money_cols:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").round(0)

    for col in num_cols:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").round(2)

    return d


def rename_for_display(df):
    rename_map = {
        "team_abbrev": "Team",
        "profile_team_name": "Team Name",
        "teamname": "Team Name",
        "league": "League",
        "game_info": "Matchup",
        "players": "Players",
        "total_salary": "Total Salary",
        "avg_salary": "Avg Salary",
        "avg_dk": "Avg DK",
        "total_avg_dk": "Team Avg DK",
        "avg_rating": "Rating",
        "avg_dk_edge": "DK Edge",
        "avg_kill_edge": "Kill Edge",
        "avg_death_edge": "Death Edge",
        "avg_assist_edge": "Assist Edge",
        "avg_dpm_edge": "DPM Edge",
        "avg_value": "Value",
        "starter_games": "Starter Games",
        "top_player": "Top Player",
        "top_pos": "Top Pos",
        "top_salary": "Top Salary",
        "top_avg_dk": "Top Avg DK",
        "top_rating": "Top Rating",
        "top_value": "Top Value",
        "proj_per_1k_salary": "Team Value",

        "series_result": "Series Result",
        "series_count": "Sample",
        "first_series_date": "First Date",
        "last_series_date": "Last Date",
        "avg_player_dk_fp_with_gnp": "Avg DK w/ Bonus",
        "avg_player_dk_fp_base": "Avg DK Base",
        "avg_player_gnp_bonus_total_5": "Avg Sweep Bonus",
        "avg_team_kills": "Avg Kills",
        "avg_kills_per_game": "Kills/Game",
        "avg_team_deaths": "Avg Deaths",
        "avg_deaths_per_game": "Deaths/Game",
        "kill_death_ratio": "K/D",
        "assist_per_kill": "Assist/Kill",
        "avg_game_length_minutes": "Avg Game Min",
        "avg_total_game_length_minutes": "Series Min",
        "avg_team_slot_dk_fp_with_gnp": "Team Slot DK",
        "avg_team_slot_dk_per_game": "Team Slot/Game",
        "avg_dragons": "Dragons",
        "avg_barons": "Barons",
        "avg_towers": "Towers",
        "avg_firstbloods": "First Bloods",
        "avg_gold_diff_15": "Gold Diff 15",
        "avg_xp_diff_15": "XP Diff 15",
        "avg_cs_diff_15": "CS Diff 15",
        "series_dfs_score": "DFS Score",
        "bloodiness_score": "Bloodiness",
        "clean_stomp_score": "Sweep Score",
        "profile_label": "Profile",

        "slate_stack_score": "Stack Score",
        "prediction_label": "DFS Label",
        "best_path": "Best Path",
        "best_path_score": "Best Path Score",
        "score_2_0": "2-0 Score",
        "score_2_1": "2-1 Score",
        "score_1_2": "1-2 Score",
        "score_0_2": "0-2 Score",
        "bloodbath_score": "Bloodbath",
        "sweep_score": "Sweep Score",

        "favorite_lean": "Favorite Lean",
        "best_stack": "Best Stack",
        "gpp_angle": "GPP Angle",
        "confidence_gap": "Gap",

        "dk_player_name": "Player",
        "position": "Pos",
        "salary": "Salary",
        "rating_team_name": "Team Name",
        "base_dk": "Base DK",
        "proj_dk": "Proj DK",
        "floor_dk": "Floor",
        "ceiling_dk": "Ceiling",
        "value_proj": "Value",
        "cpt_proj_dk": "CPT Proj",
        "cpt_salary": "CPT Salary",
        "cpt_value": "CPT Value",
        "expected_outcome_score": "Outcome Score",
        "expected_team_dk": "Expected Team DK",
        "expected_games": "Exp Games",
        "projected_path": "Projected Path",
        "p_2_0": "P 2-0",
        "p_2_1": "P 2-1",
        "p_1_2": "P 1-2",
        "p_0_2": "P 0-2",
        "win_path_probability": "Win Path %",
        "loss_path_probability": "Loss Path %",
        "strength_gap": "Strength Gap",
        "team_env_mult": "Team Env Mult",
        "player_skill_mult": "Skill Mult",
        "position_mult": "Pos Mult",
        "outcome_mult": "Outcome Mult",
        "risk_mult": "Risk Mult",
        "projection_label": "Projection Label",
        "team_strength_bucket": "Team Strength",
        "opponent_strength_bucket": "Opponent Strength",
        "strength_matchup_bucket": "Strength Matchup",
        "mid_lane_matchup_bucket": "MID Matchup",
        "bot_lane_matchup_bucket": "BOT Matchup",
        "sup_lane_matchup_bucket": "SUP Matchup",
        "similar_sample": "Similar Sample",
        "sample_type": "Sample Type",
        "bayes_win_pct": "Bayes Win %",
        "bayes_p_2_0": "Bayes 2-0 %",
        "bayes_p_2_1": "Bayes 2-1 %",
        "bayes_p_1_2": "Bayes 1-2 %",
        "bayes_p_0_2": "Bayes 0-2 %",
        "suggested_path": "Suggested Path",
        "dfs_note": "DFS Note",
        "opponent": "Opponent",
        "team_lookup_name": "Team Lookup",
        "opponent_lookup_name": "Opponent Lookup",
        "team_mid_strength": "Team MID",
        "opp_mid_strength": "Opp MID",
        "team_bot_strength": "Team BOT",
        "opp_bot_strength": "Opp BOT",
        "team_sup_strength": "Team SUP",
        "opp_sup_strength": "Opp SUP",
        "team_mid_dk_index": "Team MID DK Index",
        "opp_mid_dk_index": "Opp MID DK Index",
        "team_bot_dk_index": "Team BOT DK Index",
        "opp_bot_dk_index": "Opp BOT DK Index",
        "team_sup_dk_index": "Team SUP DK Index",
        "opp_sup_dk_index": "Opp SUP DK Index",
        "favorite_team": "Favorite Team",
        "underdog_team": "Underdog Team",
        "winner_result": "Winner Result",
        "loser_result": "Loser Result",
        "suggested_scenario": "Suggested Scenario",
        "winner_bayes_win_pct": "Winner Bayes Win %",
        "winner_bayes_2_0_pct": "Winner 2-0 %",
        "winner_bayes_2_1_pct": "Winner 2-1 %",
        "confidence_gap": "Win Gap",
        "scenario_confidence": "Confidence",
        "scenario_note": "Scenario Note",
        "lineup_builder_note": "Lineup Builder Note",
        "model_rule": "Model Rule",
        "path_decision": "Path Decision",
        "path_edge_pct": "2-0 vs 2-1 Edge",
        "path_confidence": "Path Confidence",
        "scenario_action": "Scenario Action",
    }

    return df.rename(columns=rename_map)


# =========================
# Team Prediction Logic
# =========================

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

    if blood_cols:
        pred["bloodbath_score"] = pred[blood_cols].max(axis=1)
    else:
        pred["bloodbath_score"] = 0

    pred["sweep_score"] = pred.get("clean_stomp_score_2_0", 0)

    pred["prediction_label"] = pred.apply(assign_prediction_label, axis=1)

    return pred.sort_values("slate_stack_score", ascending=False)


def assign_prediction_label(row):
    best_path = row.get("best_path", "")
    stack_score = row.get("slate_stack_score", 0)
    bloodbath = row.get("bloodbath_score", 0)
    sweep = row.get("sweep_score", 0)

    if stack_score >= 325 and best_path == "2-1 Ceiling":
        return "Elite GPP Stack"
    if stack_score >= 325 and best_path == "2-0 Sweep":
        return "Elite Sweep Stack"
    if bloodbath >= 50:
        return "Bloodbath Upside"
    if sweep >= 25:
        return "Clean Sweep Profile"
    if stack_score >= 275:
        return "Strong Stack"
    if stack_score >= 225:
        return "Playable Stack"
    return "Thin Stack"


def build_matchup_prediction_summary(predictions_df):
    if predictions_df.empty:
        return pd.DataFrame()

    rows = []

    for game_info, g in predictions_df.groupby("game_info", dropna=False):
        g = g.copy()

        if len(g) < 2:
            continue

        g_stack = g.sort_values("slate_stack_score", ascending=False)
        g_rating = g.sort_values("avg_rating", ascending=False)

        best_stack_row = g_stack.iloc[0]
        favorite_row = g_rating.iloc[0]

        second_stack = g_stack.iloc[1] if len(g_stack) > 1 else None
        confidence_gap = (
            best_stack_row["slate_stack_score"] - second_stack["slate_stack_score"]
            if second_stack is not None
            else 0
        )

        best_stack = best_stack_row["team_abbrev"]
        favorite_lean = favorite_row["team_abbrev"]

        best_path = best_stack_row.get("best_path", "")
        label = best_stack_row.get("prediction_label", "")

        if best_path == "2-1 Ceiling":
            gpp_angle = f"{best_stack} has the better 2-1 ceiling profile"
        elif best_path == "2-0 Sweep":
            gpp_angle = f"{best_stack} has the better 2-0 sweep profile"
        else:
            gpp_angle = f"{best_stack} rates best for DFS stack score"

        if label:
            gpp_angle = f"{gpp_angle} — {label}"

        rows.append(
            {
                "game_info": game_info,
                "favorite_lean": favorite_lean,
                "best_stack": best_stack,
                "best_path": best_path,
                "prediction_label": label,
                "slate_stack_score": best_stack_row["slate_stack_score"],
                "confidence_gap": confidence_gap,
                "gpp_angle": gpp_angle,
            }
        )

    out = pd.DataFrame(rows)

    if out.empty:
        return out

    return out.sort_values("slate_stack_score", ascending=False)

@st.cache_data(ttl=300)
def load_lane_power_signals(slate_date=None, slate_name=None, league=None):
    conn = connect()

    sql = """
        SELECT
            game_date,
            slate_name,
            game_info,
            league,
            team,
            opponent,
            team_full_name,
            opponent_full_name,

            bayes_win_pct,
            lane_power_win_pct_modifier,
            adjusted_win_pct,

            top_lane_edge,
            jng_lane_edge,
            mid_lane_edge,
            adc_lane_edge,
            sup_lane_edge,
            total_lane_edge,
            carry_lane_edge,
            main_carry_lane_edge,
            secondary_lane_edge,

            opponent_neutral_or_better_lanes,
            opponent_neutral_or_better_carry_lanes,

            total_lane_edge_tier,
            carry_lane_edge_tier,

            dfs_lane_power_signal,
            dfs_lane_power_note
        FROM dbo.vw_lol_slate_lane_power_signal_live_v1
        WHERE 1 = 1
    """

    params = []

    if slate_date is not None:
        sql += " AND game_date = ?"
        params.append(slate_date)

    if slate_name is not None:
        sql += " AND slate_name = ?"
        params.append(slate_name)

    if league is not None and str(league).strip().upper() != "ALL":
        sql += " AND league = ?"
        params.append(league)

    sql += """
        ORDER BY
            game_date DESC,
            slate_name,
            league,
            game_info,
            team
    """

    try:
        df = pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()

    return df


def format_pct_display(x):
    if pd.isna(x):
        return ""
    return f"{float(x) * 100:.1f}%"


def format_modifier_display(x):
    if pd.isna(x):
        return ""
    sign = "+" if float(x) > 0 else ""
    return f"{sign}{float(x) * 100:.1f}%"


def lane_signal_badge(signal):
    signal = str(signal or "")

    if "Major Carry Concern" in signal:
        return "🔴 " + signal

    if "Strong Carry Support" in signal:
        return "🟢 " + signal

    if "Toss-Up" in signal:
        return "🟡 " + signal

    if "Underdog" in signal:
        return "🟠 " + signal

    if "Thin" in signal:
        return "⚪ " + signal

    return "🔵 " + signal


# =========================
# Bayesian Strength Logic
# =========================

def get_strength_value(df, league, teamname):
    if df.empty:
        return {
            "team_strength_bucket": "unknown",
            "smoothed_series_win_rate": 0.50,
            "series_count": 0,
        }

    m = df[
        (df["league"].astype(str) == str(league))
        & (df["teamname"].astype(str).str.lower().str.strip() == str(teamname).lower().strip())
    ].copy()

    if m.empty:
        return {
            "team_strength_bucket": "unknown",
            "smoothed_series_win_rate": 0.50,
            "series_count": 0,
        }

    r = m.iloc[0]
    return {
        "team_strength_bucket": r.get("team_strength_bucket", "unknown"),
        "smoothed_series_win_rate": r.get("smoothed_series_win_rate", 0.50),
        "series_count": r.get("series_count", 0),
    }


def get_lane_value(df, league, teamname, position):
    if df.empty:
        return {
            "lane_strength_bucket": "unknown",
            "lane_dk_index": None,
            "lane_games": 0,
        }

    m = df[
        (df["league"].astype(str) == str(league))
        & (df["teamname"].astype(str).str.lower().str.strip() == str(teamname).lower().strip())
        & (df["position"].astype(str).str.upper().str.strip() == str(position).upper().strip())
    ].copy()

    if m.empty:
        return {
            "lane_strength_bucket": "unknown",
            "lane_dk_index": None,
            "lane_games": 0,
        }

    r = m.iloc[0]
    return {
        "lane_strength_bucket": r.get("lane_strength_bucket", "unknown"),
        "lane_dk_index": r.get("lane_dk_index", None),
        "lane_games": r.get("lane_games", 0),
    }


def build_current_strength_matchups(player_df, team_strength_df, lane_strength_df):
    if player_df.empty:
        return pd.DataFrame()

    d = player_df.copy()
    rows = []

    def first_valid_text(series, fallback=""):
        vals = series.dropna().astype(str).str.strip()
        vals = vals[vals != ""]
        return vals.iloc[0] if len(vals) else fallback

    for game_info, g in d.groupby("game_info", dropna=False):
        teams = g["team_abbrev"].dropna().astype(str).unique().tolist()

        if len(teams) != 2:
            continue

        # The slate uses abbreviations like BLG/TES/DK.
        # The SQL strength views use full names like Bilibili Gaming / Top Esports / Dplus Kia.
        # Build a slate-local map so lookups hit the SQL views correctly.
        team_name_map = {}
        for t in teams:
            t_rows = g[g["team_abbrev"].astype(str) == t].copy()
            full_name = first_valid_text(t_rows.get("rating_team_name", pd.Series(dtype=str)), fallback=t)
            team_name_map[t] = full_name

        for team in teams:
            opp = [t for t in teams if t != team][0]

            team_rows = g[g["team_abbrev"].astype(str) == team].copy()
            league_vals = team_rows["league"].dropna().astype(str).unique().tolist()
            league = league_vals[0] if league_vals else ""

            team_lookup_name = team_name_map.get(team, team)
            opp_lookup_name = team_name_map.get(opp, opp)

            team_strength = get_strength_value(team_strength_df, league, team_lookup_name)
            opp_strength = get_strength_value(team_strength_df, league, opp_lookup_name)

            team_strength_bucket = team_strength["team_strength_bucket"]
            opp_strength_bucket = opp_strength["team_strength_bucket"]
            strength_matchup_bucket = f"{team_strength_bucket}_vs_{opp_strength_bucket}"

            team_mid = get_lane_value(lane_strength_df, league, team_lookup_name, "MID")
            opp_mid = get_lane_value(lane_strength_df, league, opp_lookup_name, "MID")

            team_bot = get_lane_value(lane_strength_df, league, team_lookup_name, "BOT")
            opp_bot = get_lane_value(lane_strength_df, league, opp_lookup_name, "BOT")

            team_sup = get_lane_value(lane_strength_df, league, team_lookup_name, "SUP")
            opp_sup = get_lane_value(lane_strength_df, league, opp_lookup_name, "SUP")

            mid_lane_matchup_bucket = f"{team_mid['lane_strength_bucket']}_vs_{opp_mid['lane_strength_bucket']}"
            bot_lane_matchup_bucket = f"{team_bot['lane_strength_bucket']}_vs_{opp_bot['lane_strength_bucket']}"
            sup_lane_matchup_bucket = f"{team_sup['lane_strength_bucket']}_vs_{opp_sup['lane_strength_bucket']}"

            rows.append({
                "game_info": game_info,
                "league": league,
                "team_abbrev": team,
                "opponent": opp,
                "team_lookup_name": team_lookup_name,
                "opponent_lookup_name": opp_lookup_name,

                "team_strength_bucket": team_strength_bucket,
                "opponent_strength_bucket": opp_strength_bucket,
                "strength_matchup_bucket": strength_matchup_bucket,

                "team_smoothed_win_rate": team_strength["smoothed_series_win_rate"],
                "opponent_smoothed_win_rate": opp_strength["smoothed_series_win_rate"],
                "team_series_count": team_strength["series_count"],
                "opponent_series_count": opp_strength["series_count"],

                "team_mid_strength": team_mid["lane_strength_bucket"],
                "opp_mid_strength": opp_mid["lane_strength_bucket"],
                "team_bot_strength": team_bot["lane_strength_bucket"],
                "opp_bot_strength": opp_bot["lane_strength_bucket"],
                "team_sup_strength": team_sup["lane_strength_bucket"],
                "opp_sup_strength": opp_sup["lane_strength_bucket"],

                "mid_lane_matchup_bucket": mid_lane_matchup_bucket,
                "bot_lane_matchup_bucket": bot_lane_matchup_bucket,
                "sup_lane_matchup_bucket": sup_lane_matchup_bucket,

                "team_mid_dk_index": team_mid["lane_dk_index"],
                "opp_mid_dk_index": opp_mid["lane_dk_index"],
                "team_bot_dk_index": team_bot["lane_dk_index"],
                "opp_bot_dk_index": opp_bot["lane_dk_index"],
                "team_sup_dk_index": team_sup["lane_dk_index"],
                "opp_sup_dk_index": opp_sup["lane_dk_index"],
            })

    return pd.DataFrame(rows)


def build_bayes_strength_read(
    current_df,
    historical_df,
    priors_df,
    prior_weight=10,
    sample_strategy="Auto Best Available",
):
    if current_df.empty or historical_df.empty:
        return pd.DataFrame()

    rows = []

    for _, cur in current_df.iterrows():
        league = cur.get("league", "")

        league_prior = priors_df[priors_df["league"].astype(str) == str(league)].copy()

        if league_prior.empty:
            league_win_rate = 0.50
            league_p_2_0 = 0.25
            league_p_2_1 = 0.25
            league_p_1_2 = 0.25
            league_p_0_2 = 0.25
        else:
            p = league_prior.iloc[0]
            league_win_rate = p.get("league_win_rate", 0.50)
            league_p_2_0 = p.get("league_p_2_0", 0.25)
            league_p_2_1 = p.get("league_p_2_1", 0.25)
            league_p_1_2 = p.get("league_p_1_2", 0.25)
            league_p_0_2 = p.get("league_p_0_2", 0.25)

        base_filter = (
            (historical_df["league"].astype(str) == str(league))
            & (historical_df["strength_matchup_bucket"].astype(str) == str(cur["strength_matchup_bucket"]))
        )

        strict = historical_df[
            base_filter
            & (historical_df["mid_lane_matchup_bucket"].astype(str) == str(cur["mid_lane_matchup_bucket"]))
            & (historical_df["bot_lane_matchup_bucket"].astype(str) == str(cur["bot_lane_matchup_bucket"]))
            & (historical_df["sup_lane_matchup_bucket"].astype(str) == str(cur["sup_lane_matchup_bucket"]))
        ].copy()

        mid_bot = historical_df[
            base_filter
            & (historical_df["mid_lane_matchup_bucket"].astype(str) == str(cur["mid_lane_matchup_bucket"]))
            & (historical_df["bot_lane_matchup_bucket"].astype(str) == str(cur["bot_lane_matchup_bucket"]))
        ].copy()

        strength_only = historical_df[base_filter].copy()

        sample_options = {
            "Strength + MID/BOT/SUP": strict,
            "Strength + MID/BOT": mid_bot,
            "Strength Only": strength_only,
            "League Prior Only": pd.DataFrame(),
        }

        if sample_strategy in sample_options and sample_strategy != "Auto Best Available":
            sample_df = sample_options[sample_strategy]
            sample_type = sample_strategy
        elif len(strict) >= 5:
            sample_df = strict
            sample_type = "Strength + MID/BOT/SUP"
        elif len(mid_bot) >= 5:
            sample_df = mid_bot
            sample_type = "Strength + MID/BOT"
        elif len(strength_only) >= 5:
            sample_df = strength_only
            sample_type = "Strength Only"
        else:
            sample_df = pd.DataFrame()
            sample_type = "League Prior Only"

        attempts = len(sample_df)

        if attempts:
            wins = pd.to_numeric(sample_df["won_series"], errors="coerce").fillna(0).sum()
            count_2_0 = (sample_df["series_result"] == "2-0").sum()
            count_2_1 = (sample_df["series_result"] == "2-1").sum()
            count_1_2 = (sample_df["series_result"] == "1-2").sum()
            count_0_2 = (sample_df["series_result"] == "0-2").sum()
        else:
            wins = 0
            count_2_0 = 0
            count_2_1 = 0
            count_1_2 = 0
            count_0_2 = 0

        p_win = beta_smoothed_rate(wins, attempts, league_win_rate, prior_weight)

        p_2_0 = beta_smoothed_rate(count_2_0, attempts, league_p_2_0, prior_weight)
        p_2_1 = beta_smoothed_rate(count_2_1, attempts, league_p_2_1, prior_weight)
        p_1_2 = beta_smoothed_rate(count_1_2, attempts, league_p_1_2, prior_weight)
        p_0_2 = beta_smoothed_rate(count_0_2, attempts, league_p_0_2, prior_weight)

        total_path = p_2_0 + p_2_1 + p_1_2 + p_0_2
        if total_path > 0:
            p_2_0 /= total_path
            p_2_1 /= total_path
            p_1_2 /= total_path
            p_0_2 /= total_path

        path_probs = {
            "2-0": p_2_0,
            "2-1": p_2_1,
            "1-2": p_1_2,
            "0-2": p_0_2,
        }

        suggested_path = max(path_probs, key=path_probs.get)

        if sample_type == "League Prior Only":
            dfs_note = "Not enough similar history. Treat as low confidence."
        elif attempts < 8:
            dfs_note = "Thin sample. Use as directional only."
        elif suggested_path == "2-0":
            dfs_note = "Sweep path supported. Strong 4-stack candidate if projections agree."
        elif suggested_path == "2-1":
            dfs_note = "Win path supported, but more likely extended series."
        elif suggested_path == "1-2":
            dfs_note = "Competitive loss profile. Consider one-off or small secondary exposure."
        else:
            dfs_note = "Weak path. Avoid heavy stacks unless ownership/projection creates leverage."

        rows.append({
            "game_info": cur["game_info"],
            "team_abbrev": cur["team_abbrev"],
            "opponent": cur["opponent"],
            "league": league,

            "team_strength_bucket": cur["team_strength_bucket"],
            "opponent_strength_bucket": cur["opponent_strength_bucket"],
            "strength_matchup_bucket": cur["strength_matchup_bucket"],

            "mid_lane_matchup_bucket": cur["mid_lane_matchup_bucket"],
            "bot_lane_matchup_bucket": cur["bot_lane_matchup_bucket"],
            "sup_lane_matchup_bucket": cur["sup_lane_matchup_bucket"],

            "similar_sample": attempts,
            "sample_type": sample_type,

            "bayes_win_pct": (p_2_0 + p_2_1) * 100,
            "bayes_p_2_0": p_2_0 * 100,
            "bayes_p_2_1": p_2_1 * 100,
            "bayes_p_1_2": p_1_2 * 100,
            "bayes_p_0_2": p_0_2 * 100,

            "suggested_path": suggested_path,
            "dfs_note": dfs_note,

            "team_mid_strength": cur["team_mid_strength"],
            "opp_mid_strength": cur["opp_mid_strength"],
            "team_bot_strength": cur["team_bot_strength"],
            "opp_bot_strength": cur["opp_bot_strength"],
            "team_sup_strength": cur["team_sup_strength"],
            "opp_sup_strength": cur["opp_sup_strength"],

            "team_mid_dk_index": cur["team_mid_dk_index"],
            "opp_mid_dk_index": cur["opp_mid_dk_index"],
            "team_bot_dk_index": cur["team_bot_dk_index"],
            "opp_bot_dk_index": cur["opp_bot_dk_index"],
            "team_sup_dk_index": cur["team_sup_dk_index"],
            "opp_sup_dk_index": cur["opp_sup_dk_index"],
        })

    out = pd.DataFrame(rows)

    if out.empty:
        return out

    sample_rank = {
        "Strength + MID/BOT/SUP": 1,
        "Strength + MID/BOT": 2,
        "Strength Only": 3,
        "League Prior Only": 4,
    }

    out["sample_rank"] = out["sample_type"].map(sample_rank).fillna(99)

    return out.sort_values(
        ["sample_rank", "similar_sample", "bayes_win_pct"],
        ascending=[True, False, False],
    ).drop(columns=["sample_rank"])


def get_model_confidence_label(league, sample_type, similar_sample, win_pct):
    """
    Converts the backtested rules into an easy slate-level confidence label.
    These labels are for DFS scenario selection, not betting.
    """

    league = str(league or "").upper().strip()
    sample_type = str(sample_type or "")
    sample = int(float(similar_sample or 0))
    win_pct = float(win_pct or 50)

    if sample_type == "League Prior Only":
        return "Low Confidence - League Prior Only"

    if sample < 8:
        return "Caution - Thin Sample"

    if league == "LCK":
        if win_pct >= 65:
            return "LCK Strong Lean - Trust"
        if win_pct >= 58:
            return "LCK Moderate Lean - Confirm"
        if win_pct >= 52:
            return "LCK Small Lean - Caution"
        return "No Clear Model Lean"

    if league == "LPL":
        if win_pct >= 65 and sample >= 15:
            return "LPL Strong Lean - Still Verify"
        if win_pct >= 58:
            return "LPL Moderate Lean - Use as Lean"
        if win_pct >= 52:
            return "LPL Small Lean - Use as Tie Breaker"
        return "No Clear Model Lean"

    if win_pct >= 65:
        return "Strong Lean"
    if win_pct >= 58:
        return "Moderate Lean"
    if win_pct >= 52:
        return "Small Lean"
    return "No Clear Model Lean"


def choose_scenario_path(league, sample_type, similar_sample, win_pct, p_2_0, p_2_1):
    """
    Chooses 2-0 vs 2-1 using the backtest rules.

    DFS logic:
      - 2-0 is rewarding, but fragile.
      - If 2-0 and 2-1 are close, default to 2-1 unless confidence supports the sweep.
      - LCK strong leans earned more trust in backtesting.
      - LPL is noisier, so require a larger 2-0 edge.
    """

    league = str(league or "").upper().strip()
    sample_type = str(sample_type or "")
    sample = int(float(similar_sample or 0))
    win_pct = float(win_pct or 50)
    p_2_0 = float(p_2_0 or 0)
    p_2_1 = float(p_2_1 or 0)
    path_edge = p_2_0 - p_2_1

    confidence_label = get_model_confidence_label(league, sample_type, sample, win_pct)

    # Low-confidence rows should not force a sweep. If the winner is favored,
    # use the extended-series path as the safer projection base.
    if sample_type == "League Prior Only" or sample < 5:
        return {
            "winner_result": "2-1",
            "loser_result": "1-2",
            "path_decision": "Default 2-1",
            "path_confidence": "Low",
            "model_rule": confidence_label,
            "scenario_action": "Do not use 2-0 unless your manual read strongly supports it.",
            "path_edge_pct": path_edge,
        }

    # If 2-1 is ahead or essentially tied, use 2-1.
    if p_2_1 >= p_2_0:
        return {
            "winner_result": "2-1",
            "loser_result": "1-2",
            "path_decision": "2-1 favored",
            "path_confidence": "Medium" if win_pct >= 58 and sample >= 8 else "Low",
            "model_rule": confidence_label,
            "scenario_action": "Use 2-1 as the base scenario. Keep loser one-offs/secondary exposure alive.",
            "path_edge_pct": path_edge,
        }

    # 2-0 is ahead. Decide whether the sweep edge is strong enough.
    if league == "LCK" and win_pct >= 65 and sample >= 8:
        required_edge = 2.0
    elif league == "LCK" and win_pct >= 58 and sample >= 8:
        required_edge = 5.0
    elif league == "LPL" and win_pct >= 65 and sample >= 15:
        required_edge = 7.0
    elif league == "LPL" and win_pct >= 58 and sample >= 8:
        required_edge = 10.0
    else:
        required_edge = 8.0

    if path_edge >= required_edge:
        return {
            "winner_result": "2-0",
            "loser_result": "0-2",
            "path_decision": f"2-0 supported by +{path_edge:.1f} path edge",
            "path_confidence": "High" if win_pct >= 65 and sample >= 8 else "Medium",
            "model_rule": confidence_label,
            "scenario_action": "Use 2-0 as the base scenario. Prioritize winner stacks and winner TEAM slot.",
            "path_edge_pct": path_edge,
        }

    return {
        "winner_result": "2-1",
        "loser_result": "1-2",
        "path_decision": f"2-0 edge only +{path_edge:.1f}; defaulting to 2-1",
        "path_confidence": "Medium" if win_pct >= 58 and sample >= 8 else "Low",
        "model_rule": confidence_label,
        "scenario_action": "2-0 is possible, but not strong enough as the base. Use 2-1 unless building an alternate sweep set.",
        "path_edge_pct": path_edge,
    }


def build_suggested_scenarios(bayes_read_df):
    """
    Builds one recommended scenario per matchup from the Bayesian read.

    Uses backtest-derived rules:
      - LCK strong leans can be trusted more.
      - LPL leans are useful but need more manual confirmation.
      - 2-0 requires enough confidence and enough edge over 2-1.
      - If 2-0 and 2-1 are close, use 2-1 as the safer base scenario.
    """

    if bayes_read_df.empty:
        return pd.DataFrame()

    rows = []

    for game_info, g in bayes_read_df.groupby("game_info", dropna=False):
        g = g.copy()

        if len(g) < 2:
            continue

        g["bayes_win_pct"] = pd.to_numeric(g["bayes_win_pct"], errors="coerce").fillna(50)
        g["bayes_p_2_0"] = pd.to_numeric(g["bayes_p_2_0"], errors="coerce").fillna(0)
        g["bayes_p_2_1"] = pd.to_numeric(g["bayes_p_2_1"], errors="coerce").fillna(0)
        g["similar_sample"] = pd.to_numeric(g["similar_sample"], errors="coerce").fillna(0)

        ordered = g.sort_values(["bayes_win_pct", "similar_sample"], ascending=[False, False])
        winner = ordered.iloc[0]
        loser = ordered.iloc[1]

        winner_team = str(winner.get("team_abbrev", "")).strip()
        loser_team = str(winner.get("opponent", loser.get("team_abbrev", ""))).strip()
        league = str(winner.get("league", "")).upper().strip()

        p_2_0 = float(winner.get("bayes_p_2_0", 0) or 0)
        p_2_1 = float(winner.get("bayes_p_2_1", 0) or 0)
        win_pct = float(winner.get("bayes_win_pct", 50) or 50)
        loser_win_pct = float(loser.get("bayes_win_pct", 50) or 50)
        gap = win_pct - loser_win_pct
        sample = int(float(winner.get("similar_sample", 0) or 0))
        sample_type = str(winner.get("sample_type", ""))

        path_rule = choose_scenario_path(
            league=league,
            sample_type=sample_type,
            similar_sample=sample,
            win_pct=win_pct,
            p_2_0=p_2_0,
            p_2_1=p_2_1,
        )

        winner_result = path_rule["winner_result"]
        loser_result = path_rule["loser_result"]
        confidence = path_rule["path_confidence"]
        model_rule = path_rule["model_rule"]
        path_decision = path_rule["path_decision"]
        scenario_action = path_rule["scenario_action"]
        path_edge = path_rule["path_edge_pct"]

        if model_rule.startswith("Low Confidence"):
            scenario_note = "Low confidence. Use projections/ownership/manual read before trusting this scenario."
        elif model_rule.startswith("Caution"):
            scenario_note = "Thin sample. Treat as directional, not a lock."
        elif winner_result == "2-0":
            scenario_note = f"{winner_team} sweep is supported. Best fit for heavier {winner_team} stacks and TEAM slot."
        else:
            scenario_note = f"{winner_team} win lean, but 2-1 is the safer base. Opponent one-offs remain viable."

        if winner_result == "2-0":
            lineup_builder_note = (
                f"Set {winner_team}=2-0 and {loser_team}=0-2. "
                f"Prioritize {winner_team} 4-stacks / TEAM slot. Limit {loser_team} exposure. "
                f"Rule: {model_rule}; {path_decision}."
            )
        else:
            lineup_builder_note = (
                f"Set {winner_team}=2-1 and {loser_team}=1-2. "
                f"Favor {winner_team} stacks, but allow {loser_team} one-offs or small secondary exposure. "
                f"Rule: {model_rule}; {path_decision}."
            )

        rows.append({
            "game_info": game_info,
            "favorite_team": winner_team,
            "underdog_team": loser_team,
            "winner_result": winner_result,
            "loser_result": loser_result,
            "suggested_scenario": f"{winner_team} {winner_result} over {loser_team}",
            "league": league,
            "winner_bayes_win_pct": win_pct,
            "winner_bayes_2_0_pct": p_2_0,
            "winner_bayes_2_1_pct": p_2_1,
            "path_edge_pct": path_edge,
            "confidence_gap": gap,
            "similar_sample": sample,
            "sample_type": sample_type,
            "scenario_confidence": confidence,
            "model_rule": model_rule,
            "path_decision": path_decision,
            "scenario_action": scenario_action,
            "scenario_note": scenario_note,
            "lineup_builder_note": lineup_builder_note,
        })

    out = pd.DataFrame(rows)

    if out.empty:
        return out

    confidence_order = {"High": 1, "Medium": 2, "Low": 3}
    out["confidence_sort"] = out["scenario_confidence"].map(confidence_order).fillna(99)

    return out.sort_values(
        ["confidence_sort", "winner_bayes_win_pct", "similar_sample"],
        ascending=[True, False, False],
    ).drop(columns=["confidence_sort"])


# =========================
# Player Projection Logic
# =========================

def infer_outcome_probabilities(predictions_df):
    """
    Adds outcome probabilities to each team:
        p_2_0, p_2_1, p_1_2, p_0_2

    These are DFS-path probabilities, not betting probabilities.
    They are based on stack-score gap versus opponent.
    """

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


def get_position_multiplier(position):
    pos = str(position).lower().strip()

    if pos == "bot":
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

    if pos in ["bot", "mid"]:
        base += 0.08
    elif pos == "jng":
        base += 0.04
    elif pos == "sup":
        base -= 0.08

    return max(1.25, min(base, 1.75))


def assign_player_projection_label(row):
    proj = row.get("proj_dk", 0)
    value = row.get("value_proj", 0)
    ceiling = row.get("ceiling_dk", 0)
    path = row.get("projected_path", "")

    if proj >= 85 and value >= 1.7:
        return "Core Projection"
    if ceiling >= 115 and path in ["2-1", "2-0"]:
        return "GPP Ceiling"
    if value >= 1.8:
        return "Strong Value"
    if proj >= 70:
        return "Playable"
    if value < 1.2:
        return "Thin Value"
    return "Pool Option"


def build_player_projections(player_df, predictions_df):
    """
    Builds DFS player projections using:
      - player historical avg DK
      - player rating/edges
      - team predicted outcome probabilities
      - team expected DFS environment
      - position role
    """

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
        "prediction_label",
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

    # Base player production.
    merged["base_dk"] = pd.to_numeric(merged["avg_dk"], errors="coerce")

    if "dk_avg_points" in merged.columns:
        merged["base_dk"] = merged["base_dk"].fillna(
            pd.to_numeric(merged["dk_avg_points"], errors="coerce")
        )

    merged["base_dk"] = merged["base_dk"].fillna(0)

    # Slate means for relative adjustment.
    avg_expected_score = pd.to_numeric(
        preds.get("expected_outcome_score", pd.Series([0])),
        errors="coerce",
    ).replace(0, pd.NA).dropna()

    if len(avg_expected_score) > 0:
        slate_avg_outcome_score = avg_expected_score.mean()
    else:
        slate_avg_outcome_score = 300

    avg_stack = pd.to_numeric(
        preds.get("slate_stack_score", pd.Series([0])),
        errors="coerce",
    ).replace(0, pd.NA).dropna()

    if len(avg_stack) > 0:
        slate_avg_stack = avg_stack.mean()
    else:
        slate_avg_stack = 250

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

    # Multipliers.
    merged["team_env_mult"] = 1 + ((merged["slate_stack_score"] - slate_avg_stack) / 900)
    merged["team_env_mult"] = merged["team_env_mult"].clip(0.88, 1.12)

    merged["outcome_mult"] = 1 + ((merged["expected_outcome_score"] - slate_avg_outcome_score) / 900)
    merged["outcome_mult"] = merged["outcome_mult"].clip(0.90, 1.12)

    merged["player_skill_mult"] = (
        1
        + (merged["rating_score"] * 0.035)
        + (merged["avg_dk_edge"] * 0.006)
        + (merged["avg_kill_edge"] * 0.018)
    )
    merged["player_skill_mult"] = merged["player_skill_mult"].clip(0.82, 1.20)

    merged["position_mult"] = merged["position"].apply(get_position_multiplier)

    merged["risk_mult"] = 1 - (pd.to_numeric(merged["loss_path_probability"], errors="coerce").fillna(0.45) * 0.08)
    merged["risk_mult"] = merged["risk_mult"].clip(0.92, 1.02)

    # Final projection.
    merged["proj_dk"] = (
        merged["base_dk"]
        * merged["team_env_mult"]
        * merged["outcome_mult"]
        * merged["player_skill_mult"]
        * merged["position_mult"]
        * merged["risk_mult"]
    )

    # Do not let the first-pass model completely destroy low sample players.
    merged["proj_dk"] = merged["proj_dk"].clip(lower=0)

    merged["floor_dk"] = merged["proj_dk"] * 0.70

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

    merged["projection_label"] = merged.apply(assign_player_projection_label, axis=1)

    merged["pos_sort"] = merged["position_key"].map(POSITION_ORDER).fillna(99)

    merged = merged.sort_values(
        ["proj_dk", "ceiling_dk", "value_proj"],
        ascending=[False, False, False],
    )

    return merged


# =========================
# App Body
# =========================

st.title("LoL Slate Team Overview")

if not DB_SERVER or not DB_DATABASE:
    st.error("Missing DB_SERVER or DB_DATABASE from .env file.")
    st.stop()

st.sidebar.header("Slate Selection")

try:
    slate_dates = get_slate_dates()
except Exception as e:
    st.error("Could not connect to SQL Server or load slate dates.")
    st.exception(e)
    st.stop()

if not slate_dates:
    st.error("No slate dates found in dbo.dk_lol_slate_player.")
    st.stop()

selected_date = st.sidebar.selectbox(
    "Slate Date",
    slate_dates,
    key="sidebar_slate_date_select",
)

slate_names = get_slate_names(selected_date)

if not slate_names:
    st.error(f"No slate names found for {selected_date}.")
    st.stop()

selected_slate = st.sidebar.selectbox(
    "Slate Name",
    slate_names,
    key="sidebar_slate_name_select",
)

use_starters_only = st.sidebar.checkbox("Use manual starters only", value=True)

if st.sidebar.button("Clear cache / refresh data"):
    st.cache_data.clear()
    st.rerun()

df = load_data(selected_date, selected_slate)

if df.empty:
    st.warning("No players found for this slate/date.")
    st.stop()

manual = load_manual_starters()

if use_starters_only:
    df, starter_message = apply_manual_starters(df, manual)
else:
    starter_message = "Showing all non-CPT DK rows."

st.sidebar.info(starter_message)
st.caption(f"Loaded {len(df):,} rows for {selected_date} — {selected_slate}")


# Shared prepared data
team_df_base = build_team_overview(df)
profile_team_names = get_slate_profile_team_names(df)
profiles_df_base = load_series_profiles_for_slate(profile_team_names)
predictions_df_base = build_slate_predictions(team_df_base, profiles_df_base)
player_proj_df_base = build_player_projections(df, predictions_df_base)


tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
    [
        "Team Overview",
        "Team Series Splits",
        "Slate Predictions",
        "Bayesian Matchup Read",
        "Player Projections",
        "Player Table",
        "Matchups",
        "Raw Data",
    ]
)


# =========================
# Tab 1: Team Overview
# =========================

with tab1:
    st.header("Team Overview")

    team_df = format_df(team_df_base)

    sort_cols = [
        "avg_rating",
        "total_avg_dk",
        "avg_value",
        "proj_per_1k_salary",
        "avg_dk_edge",
        "avg_kill_edge",
        "avg_dpm_edge",
    ]

    sort_cols = [c for c in sort_cols if c in team_df.columns]

    sort_by = st.selectbox("Sort teams by", sort_cols, index=0, key="team_overview_sort")

    team_df = team_df.sort_values(sort_by, ascending=False)

    main_cols = [
        "team_abbrev",
        "profile_team_name",
        "game_info",
        "players",
        "avg_rating",
        "total_avg_dk",
        "avg_dk_edge",
        "avg_kill_edge",
        "avg_death_edge",
        "avg_value",
        "top_player",
        "top_avg_dk",
    ]

    main_cols = [c for c in main_cols if c in team_df.columns]

    st.dataframe(
        rename_for_display(team_df[main_cols]),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("Extra Team Detail"):
        extra_cols = [
            "team_abbrev",
            "profile_team_name",
            "game_info",
            "total_salary",
            "avg_salary",
            "avg_assist_edge",
            "avg_dpm_edge",
            "starter_games",
            "proj_per_1k_salary",
            "top_pos",
            "top_salary",
            "top_rating",
            "top_value",
        ]

        extra_cols = [c for c in extra_cols if c in team_df.columns]

        st.dataframe(
            rename_for_display(team_df[extra_cols]),
            use_container_width=True,
            hide_index=True,
        )


    st.divider()
    st.subheader("Lane Power PIT Adjustment")

    st.caption(
        "Adds the clean point-in-time lane-power signal next to the current Bayes read. "
        "This is a confidence modifier, not a replacement for the existing Bayes model."
    )

    lane_power_df = load_lane_power_signals(slate_date=selected_date,slate_name=selected_slate,)

    if lane_power_df.empty:
        st.info(
            "No Lane Power PIT signals found for this slate date. "
            "If this is an upcoming slate, the current snapshot may only contain completed historical series."
        )
    else:
        display_df = lane_power_df.copy()

        # Keep this section focused on the teams from the selected slate when names match.
        slate_team_keys = {
            norm_text(t)
            for t in profile_team_names
            if str(t).strip()
        }

        if slate_team_keys:
            slate_filtered = display_df[
                display_df["team"].apply(norm_text).isin(slate_team_keys)
                | display_df["opponent"].apply(norm_text).isin(slate_team_keys)
            ].copy()

            if not slate_filtered.empty:
                display_df = slate_filtered

        display_df["Bayes Win %"] = display_df["bayes_win_pct"].apply(format_pct_display)
        display_df["Lane Modifier"] = display_df["lane_power_win_pct_modifier"].apply(format_modifier_display)
        display_df["Adjusted Win %"] = display_df["adjusted_win_pct"].apply(format_pct_display)
        display_df["DFS Signal"] = display_df["dfs_lane_power_signal"].apply(lane_signal_badge)

        show_cols = [
            "game_date",
            "league",
            "team",
            "opponent",
            "Bayes Win %",
            "Lane Modifier",
            "Adjusted Win %",
            "carry_lane_edge",
            "carry_lane_edge_tier",
            "opponent_neutral_or_better_carry_lanes",
            "DFS Signal",
            "dfs_lane_power_note",
        ]

        show_cols = [c for c in show_cols if c in display_df.columns]

        st.dataframe(
            display_df[show_cols].rename(
                columns={
                    "game_date": "Date",
                    "league": "League",
                    "team": "Team",
                    "opponent": "Opponent",
                    "carry_lane_edge": "Carry Lane Edge",
                    "carry_lane_edge_tier": "Carry Lane Tier",
                    "opponent_neutral_or_better_carry_lanes": "Opp Neutral+ Carry Lanes",
                    "dfs_lane_power_note": "DFS Note",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### Priority Lane Power Flags")

        flag_cols_raw = [
            "bayes_overconfidence_warning_flag",
            "favorite_stomp_support_flag",
            "lane_power_breaks_bayes_tie_flag",
            "bayes_possible_upset_signal_flag",
        ]

        for flag_col in flag_cols_raw:
            if flag_col not in display_df.columns:
                display_df[flag_col] = 0

        flags_df = display_df[
            (pd.to_numeric(display_df["bayes_overconfidence_warning_flag"], errors="coerce").fillna(0) == 1)
            | (pd.to_numeric(display_df["favorite_stomp_support_flag"], errors="coerce").fillna(0) == 1)
            | (pd.to_numeric(display_df["lane_power_breaks_bayes_tie_flag"], errors="coerce").fillna(0) == 1)
            | (pd.to_numeric(display_df["bayes_possible_upset_signal_flag"], errors="coerce").fillna(0) == 1)
        ].copy()

        if flags_df.empty:
            st.info("No major Lane Power flags for this slate/date.")
        else:
            flag_cols = [
                "team",
                "opponent",
                "Bayes Win %",
                "Adjusted Win %",
                "carry_lane_edge",
                "DFS Signal",
                "dfs_lane_power_note",
            ]

            flag_cols = [c for c in flag_cols if c in flags_df.columns]

            st.dataframe(
                flags_df[flag_cols].rename(
                    columns={
                        "team": "Team",
                        "opponent": "Opponent",
                        "carry_lane_edge": "Carry Lane Edge",
                        "dfs_lane_power_note": "DFS Note",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )


# =========================
# Tab 2: Team Series Splits
# =========================

with tab2:
    st.header("Team Series Splits")

    st.caption(
        "Historical LPL/LCK scoring profiles for only the teams on the selected slate. "
        "This compares how each team has scored in 2-0, 2-1, 1-2, and 0-2 series."
    )

    if profiles_df_base.empty:
        st.warning("No matching LPL/LCK team series profiles found for the teams on this slate.")

        st.write("Slate teams detected:")
        st.write(profile_team_names)

        st.info(
            "If this list shows abbreviations but the profile table uses full team names, "
            "we may need to add or update a team-name mapping."
        )
    else:
        profiles_df = format_df(profiles_df_base)

        result_filter = st.multiselect(
            "Series Result",
            options=["2-0", "2-1", "1-2", "0-2"],
            default=["2-0", "2-1", "1-2", "0-2"],
            key="series_result_filter",
        )

        min_sample = st.slider(
            "Minimum Series Count",
            min_value=1,
            max_value=max(1, int(profiles_df["series_count"].max())),
            value=1,
            key="series_min_sample",
        )

        sort_options = [
            "series_dfs_score",
            "avg_player_dk_fp_with_gnp",
            "avg_team_kills",
            "avg_kills_per_game",
            "bloodiness_score",
            "clean_stomp_score",
            "avg_game_length_minutes",
        ]

        sort_options = [c for c in sort_options if c in profiles_df.columns]

        sort_by = st.selectbox(
            "Sort by",
            sort_options,
            index=0,
            key="series_sort",
        )

        view_df = profiles_df.copy()

        view_df = view_df[
            view_df["series_result"].isin(result_filter)
            & (view_df["series_count"] >= min_sample)
        ].copy()

        main_cols = [
            "teamname",
            "league",
            "series_result",
            "series_count",
            "avg_player_dk_fp_with_gnp",
            "avg_team_kills",
            "avg_kills_per_game",
            "avg_team_deaths",
            "avg_deaths_per_game",
            "kill_death_ratio",
            "avg_game_length_minutes",
            "series_dfs_score",
            "bloodiness_score",
            "clean_stomp_score",
            "profile_label",
        ]

        main_cols = [c for c in main_cols if c in view_df.columns]

        view_df = view_df.sort_values(sort_by, ascending=False)

        st.subheader("Slate Team Series Profiles")

        st.dataframe(
            rename_for_display(view_df[main_cols]),
            use_container_width=True,
            hide_index=True,
        )

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Best 2-0 Profiles")

            two_zero = view_df[view_df["series_result"] == "2-0"].copy()

            if not two_zero.empty:
                two_zero = two_zero.sort_values("series_dfs_score", ascending=False)

                st.dataframe(
                    rename_for_display(two_zero[main_cols]),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No 2-0 profiles found with the current filters.")

        with col2:
            st.subheader("Best 2-1 Profiles")

            two_one = view_df[view_df["series_result"] == "2-1"].copy()

            if not two_one.empty:
                two_one = two_one.sort_values("series_dfs_score", ascending=False)

                st.dataframe(
                    rename_for_display(two_one[main_cols]),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No 2-1 profiles found with the current filters.")


# =========================
# Tab 3: Slate Predictions
# =========================

with tab3:
    st.header("Slate Predictions")

    st.caption(
        "Blends current slate team strength with historical LPL/LCK 2-0, 2-1, 1-2, and 0-2 DFS scoring profiles. "
        "Use this as a DFS stack ranking, not as a betting-grade win probability."
    )

    if profiles_df_base.empty:
        st.warning("No series profile data found for this slate's teams.")
    elif predictions_df_base.empty:
        st.warning("Could not build slate predictions. This is likely a team-name matching issue.")
        st.write("Slate teams detected:")
        st.write(profile_team_names)
    else:
        predictions_df = format_df(predictions_df_base)

        summary_df = build_matchup_prediction_summary(predictions_df)
        summary_df = format_df(summary_df)

        if not summary_df.empty:
            st.subheader("Matchup Prediction Summary")

            summary_cols = [
                "game_info",
                "favorite_lean",
                "best_stack",
                "best_path",
                "prediction_label",
                "slate_stack_score",
                "confidence_gap",
                "gpp_angle",
            ]

            summary_cols = [c for c in summary_cols if c in summary_df.columns]

            st.dataframe(
                rename_for_display(summary_df[summary_cols]),
                use_container_width=True,
                hide_index=True,
            )

        st.subheader("Slate Stack Rankings")

        display_cols = [
            "team_abbrev",
            "profile_team_name",
            "league",
            "game_info",
            "slate_stack_score",
            "prediction_label",
            "best_path",
            "best_path_score",
            "score_2_0",
            "score_2_1",
            "score_1_2",
            "score_0_2",
            "bloodbath_score",
            "sweep_score",
            "avg_rating",
            "total_avg_dk",
            "avg_kill_edge",
            "avg_dk_edge",
            "avg_value",
            "top_player",
            "top_avg_dk",
        ]

        display_cols = [c for c in display_cols if c in predictions_df.columns]

        predictions_df = predictions_df.sort_values("slate_stack_score", ascending=False)

        st.dataframe(
            rename_for_display(predictions_df[display_cols]),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("Best 2-0 Sweep Paths"):
            sweep_df = predictions_df.sort_values("score_2_0", ascending=False).copy()

            st.dataframe(
                rename_for_display(sweep_df[display_cols]),
                use_container_width=True,
                hide_index=True,
            )

        with st.expander("Best 2-1 Ceiling Paths"):
            ceiling_df = predictions_df.sort_values("score_2_1", ascending=False).copy()

            st.dataframe(
                rename_for_display(ceiling_df[display_cols]),
                use_container_width=True,
                hide_index=True,
            )

        with st.expander("Extra Prediction Details"):
            extra_cols = [
                "team_abbrev",
                "profile_team_name",
                "league",
                "game_info",

                "series_count_2_0",
                "series_count_2_1",
                "series_count_1_2",
                "series_count_0_2",

                "avg_player_dk_fp_with_gnp_2_0",
                "avg_player_dk_fp_with_gnp_2_1",
                "avg_player_dk_fp_with_gnp_1_2",
                "avg_player_dk_fp_with_gnp_0_2",

                "avg_team_kills_2_0",
                "avg_team_kills_2_1",
                "avg_team_kills_1_2",
                "avg_team_kills_0_2",

                "bloodiness_score_2_0",
                "bloodiness_score_2_1",
                "bloodiness_score_1_2",
                "bloodiness_score_0_2",

                "clean_stomp_score_2_0",
                "clean_stomp_score_2_1",
            ]

            extra_cols = [c for c in extra_cols if c in predictions_df.columns]

            st.dataframe(
                rename_for_display(predictions_df[extra_cols]),
                use_container_width=True,
                hide_index=True,
            )



# =========================
# Tab 4: Bayesian Matchup Read
# =========================

with tab4:
    st.header("Bayesian Matchup Read")

    st.caption(
        "Compares today's team strength and lane strength profile against historical LPL/LCK 2026 matchups. "
        "Small samples are smoothed toward league averages."
    )

    historical_df = load_bayes_strength_matchups()
    priors_df = load_bayes_league_priors()
    team_strength_df = load_team_strength_buckets()
    lane_strength_df = load_lane_strength_buckets()

    if historical_df.empty:
        st.warning("No Bayesian strength matchup rows found. Check dbo.vw_lol_bayes_strength_matchups.")
    elif priors_df.empty:
        st.warning("No league priors found. Check dbo.vw_lol_bayes_league_priors.")
    else:
        prior_weight = st.slider(
            "League Average Prior Weight",
            min_value=4,
            max_value=40,
            value=10,
            step=2,
            help="Higher = pull small samples harder toward league average.",
            key="bayes_strength_prior_weight",
        )

        sample_strategy = st.selectbox(
            "Bayesian Sample Type",
            options=[
                "Auto Best Available",
                "Strength + MID/BOT/SUP",
                "Strength + MID/BOT",
                "Strength Only",
                "League Prior Only",
            ],
            index=0,
            help=(
                "Auto uses the most specific sample with at least 5 historical rows. "
                "Manual choices force that exact sample type, even when the sample is thin."
            ),
            key="bayes_strength_sample_strategy",
        )

        current_strength_df = build_current_strength_matchups(
            player_df=df,
            team_strength_df=team_strength_df,
            lane_strength_df=lane_strength_df,
        )

        bayes_read_df = build_bayes_strength_read(
            current_df=current_strength_df,
            historical_df=historical_df,
            priors_df=priors_df,
            prior_weight=prior_weight,
            sample_strategy=sample_strategy,
        )

        if bayes_read_df.empty:
            st.warning("Could not build Bayesian matchup read for this slate.")
        else:
            scenario_df = build_suggested_scenarios(bayes_read_df)

            if not scenario_df.empty:
                st.subheader("Suggested Scenario Summary")

                scenario_cols = [
                    "game_info",
                    "suggested_scenario",
                    "league",
                    "winner_bayes_win_pct",
                    "winner_bayes_2_0_pct",
                    "winner_bayes_2_1_pct",
                    "path_edge_pct",
                    "similar_sample",
                    "sample_type",
                    "scenario_confidence",
                    "model_rule",
                    "path_decision",
                    "scenario_note",
                ]

                scenario_cols = [c for c in scenario_cols if c in scenario_df.columns]

                st.dataframe(
                    rename_for_display(format_df(scenario_df[scenario_cols])),
                    use_container_width=True,
                    hide_index=True,
                )

                scenario_lines = []
                for _, r in scenario_df.iterrows():
                    scenario_lines.append(
                        f"{r['favorite_team']} {r['winner_result']} / {r['underdog_team']} {r['loser_result']}"
                    )

                with st.expander("Copyable lineup-builder scenario notes"):
                    st.code("\n".join(scenario_lines), language="text")

                    note_cols = [
                        "game_info",
                        "suggested_scenario",
                        "model_rule",
                        "path_decision",
                        "scenario_action",
                        "lineup_builder_note",
                    ]
                    note_cols = [c for c in note_cols if c in scenario_df.columns]

                    st.dataframe(
                        rename_for_display(scenario_df[note_cols]),
                        use_container_width=True,
                        hide_index=True,
                    )

            main_cols = [
                "game_info",
                "team_abbrev",
                "opponent",
                "league",
                "team_strength_bucket",
                "opponent_strength_bucket",
                "strength_matchup_bucket",
                "mid_lane_matchup_bucket",
                "bot_lane_matchup_bucket",
                "sup_lane_matchup_bucket",
                "similar_sample",
                "sample_type",
                "bayes_win_pct",
                "bayes_p_2_0",
                "bayes_p_2_1",
                "bayes_p_1_2",
                "bayes_p_0_2",
                "suggested_path",
                "dfs_note",
            ]

            main_cols = [c for c in main_cols if c in bayes_read_df.columns]

            st.subheader("Bayesian Result Path Read")

            st.dataframe(
                rename_for_display(format_df(bayes_read_df[main_cols])),
                use_container_width=True,
                hide_index=True,
            )

            with st.expander("Lane Strength Details"):
                detail_cols = [
                    "game_info",
                    "team_abbrev",
                    "opponent",
                    "team_mid_strength",
                    "opp_mid_strength",
                    "team_bot_strength",
                    "opp_bot_strength",
                    "team_sup_strength",
                    "opp_sup_strength",
                    "team_mid_dk_index",
                    "opp_mid_dk_index",
                    "team_bot_dk_index",
                    "opp_bot_dk_index",
                    "team_sup_dk_index",
                    "opp_sup_dk_index",
                ]

                detail_cols = [c for c in detail_cols if c in bayes_read_df.columns]

                st.dataframe(
                    rename_for_display(format_df(bayes_read_df[detail_cols])),
                    use_container_width=True,
                    hide_index=True,
                )

            with st.expander("Current Strength Matchups"):
                st.dataframe(
                    rename_for_display(format_df(current_strength_df)),
                    use_container_width=True,
                    hide_index=True,
                )


# =========================
# Tab 5: Player Projections
# =========================

with tab5:
    st.header("Player Projections")

    st.caption(
        "DFS-focused player projections built from player historical production, player rating, team stack score, "
        "and expected series outcome path. These are first-pass DFS projections, not betting projections."
    )

    if player_proj_df_base.empty:
        st.warning("Could not build player projections. This usually means slate predictions did not load.")
    else:
        proj_df = player_proj_df_base.copy()

        teams_available = sorted(proj_df["team_abbrev"].dropna().astype(str).unique().tolist())
        pos_available = ["top", "jng", "mid", "bot", "sup"]

        col_filter1, col_filter2, col_filter3 = st.columns(3)

        with col_filter1:
            selected_teams = st.multiselect(
                "Teams",
                options=teams_available,
                default=teams_available,
                key="player_proj_team_filter",
            )

        with col_filter2:
            selected_positions = st.multiselect(
                "Positions",
                options=pos_available,
                default=pos_available,
                key="player_proj_pos_filter",
            )

        with col_filter3:
            min_proj = st.slider(
                "Minimum Projection",
                min_value=0,
                max_value=150,
                value=0,
                step=5,
                key="player_proj_min",
            )

        view_df = proj_df.copy()

        view_df = view_df[
            view_df["team_abbrev"].isin(selected_teams)
            & view_df["position"].astype(str).str.lower().isin(selected_positions)
            & (view_df["proj_dk"] >= min_proj)
        ].copy()

        sort_options = [
            "proj_dk",
            "ceiling_dk",
            "value_proj",
            "cpt_proj_dk",
            "cpt_value",
            "base_dk",
            "expected_outcome_score",
            "slate_stack_score",
            "rating_score",
        ]

        sort_options = [c for c in sort_options if c in view_df.columns]

        sort_by = st.selectbox(
            "Sort Players By",
            options=sort_options,
            index=0,
            key="player_proj_sort",
        )

        view_df = view_df.sort_values(sort_by, ascending=False)
        view_df = format_df(view_df)

        main_cols = [
            "dk_player_name",
            "team_abbrev",
            "rating_team_name",
            "game_info",
            "position",
            "salary",
            "projection_label",
            "projected_path",
            "base_dk",
            "proj_dk",
            "floor_dk",
            "ceiling_dk",
            "value_proj",
            "cpt_proj_dk",
            "cpt_salary",
            "cpt_value",
            "expected_games",
            "win_path_probability",
            "p_2_0",
            "p_2_1",
            "p_1_2",
            "p_0_2",
        ]

        main_cols = [c for c in main_cols if c in view_df.columns]

        st.subheader("Main Player Projections")

        st.dataframe(
            rename_for_display(view_df[main_cols]),
            use_container_width=True,
            hide_index=True,
        )

        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Best Captain Values")

            cpt_cols = [
                "dk_player_name",
                "team_abbrev",
                "position",
                "salary",
                "cpt_salary",
                "cpt_proj_dk",
                "cpt_value",
                "ceiling_dk",
                "projected_path",
                "projection_label",
            ]

            cpt_cols = [c for c in cpt_cols if c in view_df.columns]

            cpt_df = view_df.sort_values("cpt_value", ascending=False).copy()

            st.dataframe(
                rename_for_display(cpt_df[cpt_cols]),
                use_container_width=True,
                hide_index=True,
            )

        with col_b:
            st.subheader("Highest Ceilings")

            ceil_cols = [
                "dk_player_name",
                "team_abbrev",
                "position",
                "salary",
                "proj_dk",
                "ceiling_dk",
                "value_proj",
                "projected_path",
                "bloodbath_score",
                "projection_label",
            ]

            ceil_cols = [c for c in ceil_cols if c in view_df.columns]

            ceil_df = view_df.sort_values("ceiling_dk", ascending=False).copy()

            st.dataframe(
                rename_for_display(ceil_df[ceil_cols]),
                use_container_width=True,
                hide_index=True,
            )

        with st.expander("Projection Model Detail"):
            detail_cols = [
                "dk_player_name",
                "team_abbrev",
                "position",
                "base_dk",
                "proj_dk",
                "team_env_mult",
                "outcome_mult",
                "player_skill_mult",
                "position_mult",
                "risk_mult",
                "expected_outcome_score",
                "expected_team_dk",
                "slate_stack_score",
                "strength_gap",
                "best_path",
                "projected_path",
                "prediction_label",
            ]

            detail_cols = [c for c in detail_cols if c in view_df.columns]

            st.dataframe(
                rename_for_display(view_df[detail_cols]),
                use_container_width=True,
                hide_index=True,
            )


# =========================
# Tab 6: Player Table
# =========================

with tab6:
    st.header("Player Table")

    player_df = df.copy()
    player_df["pos_sort"] = player_df["position_key"].map(POSITION_ORDER).fillna(99)
    player_df = player_df.sort_values(
        ["team_abbrev", "pos_sort", "salary"],
        ascending=[True, True, False],
    )
    player_df = format_df(player_df)

    display_cols = [
        "team_abbrev",
        "rating_team_name",
        "game_info",
        "dk_player_name",
        "position",
        "salary",
        "games",
        "avg_dk",
        "avg_dk_edge",
        "avg_kill_edge",
        "avg_death_edge",
        "avg_assist_edge",
        "avg_dpm_edge",
        "rating_score",
        "dk_value",
        "rating_value",
    ]

    display_cols = [c for c in display_cols if c in player_df.columns]

    st.dataframe(
        rename_for_display(player_df[display_cols]),
        use_container_width=True,
        hide_index=True,
    )


# =========================
# Tab 7: Matchups
# =========================

with tab7:
    st.header("Matchups")

    for game_info, game_df in df.groupby("game_info", dropna=False):
        away, home, game_time = parse_game_info(game_info)

        if not away or not home:
            continue

        st.subheader(f"{away} vs {home} — {game_time}")

        game_team_df = build_team_overview(game_df)
        game_team_df = format_df(game_team_df)

        matchup_cols = [
            "team_abbrev",
            "profile_team_name",
            "players",
            "avg_rating",
            "total_avg_dk",
            "avg_dk_edge",
            "avg_kill_edge",
            "avg_death_edge",
            "avg_value",
            "top_player",
            "top_avg_dk",
        ]

        matchup_cols = [c for c in matchup_cols if c in game_team_df.columns]

        st.dataframe(
            rename_for_display(game_team_df[matchup_cols]),
            use_container_width=True,
            hide_index=True,
        )


# =========================
# Tab 8: Raw Data
# =========================

with tab8:
    st.header("Raw Data")

    st.dataframe(
        format_df(df),
        use_container_width=True,
        hide_index=True,
    )
