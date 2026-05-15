import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# ============================================================
# LoL Scenario Lineup Builder
# Save as: C:\DailyDFS\LoL\app_lol_lineup_builder.py
# Run:     python -m streamlit run .\app_lol_lineup_builder.py
#
# This app reuses your existing lineup-builder script functions from:
# C:\DailyDFS\LoL\scripts\build_lol_top_lineups.py
# ============================================================

load_dotenv()

BASE_DIR = Path(r"C:\DailyDFS\LoL")
SCRIPTS_DIR = BASE_DIR / "scripts"
OUTPUT_DIR = BASE_DIR / "lineups"
OUTPUT_DIR.mkdir(exist_ok=True)

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from scripts.build_lol_top_lineups import (
        connect,
        load_manual_starters,
        load_slate_players,
        load_team_rows,
        apply_manual_starters,
        build_team_overview,
        get_slate_profile_team_names,
        load_series_profiles_for_slate,
        build_top_lineups,
        lineups_to_df,
        get_position_multiplier,
        get_position_ceiling_multiplier,
    )
except Exception as e:
    st.error("Could not import functions from scripts/build_lol_top_lineups.py")
    st.exception(e)
    st.stop()

st.set_page_config(page_title="LoL Scenario Lineup Builder", layout="wide")

DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")


def normalize_slot(v):
    slot = str(v).strip().upper()
    return "ADC" if slot == "BOT" else slot

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


@st.cache_data(ttl=300)
def get_slate_dates():
    conn = connect()
    df = pd.read_sql(
        """
        SELECT DISTINCT slate_date
        FROM dbo.dk_lol_slate_player
        ORDER BY slate_date DESC
        """,
        conn,
    )
    conn.close()
    return df["slate_date"].astype(str).tolist()


@st.cache_data(ttl=300)
def get_slate_names(slate_date):
    conn = connect()
    df = pd.read_sql(
        """
        SELECT DISTINCT slate_name
        FROM dbo.dk_lol_slate_player
        WHERE slate_date = ?
        ORDER BY slate_name
        """,
        conn,
        params=[slate_date],
    )
    conn.close()
    return df["slate_name"].astype(str).tolist()


@st.cache_data(ttl=300)
def cached_load_slate_players(slate_date, slate_name):
    conn = connect()
    df = load_slate_players(conn, slate_date, slate_name)
    conn.close()
    return df


@st.cache_data(ttl=300)
def cached_load_team_rows(slate_date, slate_name):
    conn = connect()
    df = load_team_rows(conn, slate_date, slate_name)
    conn.close()
    return df


@st.cache_data(ttl=300)
def cached_load_profiles(profile_team_names):
    conn = connect()
    df = load_series_profiles_for_slate(conn, list(profile_team_names))
    conn.close()
    return df

@st.cache_data(ttl=300)
def cached_load_player_series_profiles(profile_team_names):
    """
    Loads player-level historical scoring ranges by series result.

    Expected source table/view:
        dbo.lol_player_series_profiles

    Required columns:
        player_name, teamname, position, series_result, series_count,
        avg_dk, median_dk, p25_dk, p75_dk, p85_dk, p90_dk, max_dk, std_dk
    """

    if not profile_team_names:
        return pd.DataFrame()

    conn = connect()
    placeholders = ",".join(["?"] * len(profile_team_names))

    sql = f"""
        SELECT
            player_name,
            teamname,
            position,
            series_result,
            series_count,
            avg_dk,
            median_dk,
            p25_dk,
            p75_dk,
            p85_dk,
            p90_dk,
            max_dk,
            std_dk
        FROM dbo.lol_player_series_profiles
        WHERE teamname IN ({placeholders})
            AND series_result IN ('2-0', '2-1', '1-2', '0-2')
    """

    try:
        df = pd.read_sql(sql, conn, params=list(profile_team_names))
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()

    if df.empty:
        return df

    df["player_key"] = df["player_name"].apply(norm_text)
    df["team_merge_key"] = df["teamname"].astype(str).str.strip()
    df["position_key"] = df["position"].apply(norm_text)

    return df


def safe_num(s, default=0):
    return pd.to_numeric(s, errors="coerce").fillna(default)


def game_count_for_result(series_result):
    return 2 if series_result in ["2-0", "0-2"] else 3


def player_sweep_bonus(series_result):
    return 20.0 if series_result == "2-0" else 0.0


def team_sweep_bonus(series_result):
    return 15.0 if series_result == "2-0" else 0.0


def format_df(df):
    d = df.copy()
    round_cols = [
        "salary", "cpt_salary", "salary_left", "base_dk", "series_base_dk",
        "expected_sweep_bonus", "proj_dk", "floor_dk", "ceiling_dk", "value_proj",
        "cpt_proj_dk", "cpt_value", "team_proj_dk", "team_ceiling_dk", "team_value",
        "team_stack_score", "series_dfs_score", "avg_player_dk_fp_with_gnp",
        "avg_team_slot_dk_fp_with_gnp", "avg_team_kills", "avg_kills_per_game",
        "bloodiness_score", "clean_stomp_score", "projection", "ceiling", "objective_score",
        "team_env_mult", "outcome_mult", "player_skill_mult", "position_mult","fallback_proj_dk",
        "hist_sample","hist_avg_dk","typical_dk","hist_p25_dk","hist_p75_dk","hist_p85_dk","hist_p90_dk",
        "range_width","ceiling_gap","cpt_ceiling_dk",
    ]
    for c in round_cols:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce").round(2)
    return d


def rename_for_display(df):
    return df.rename(columns={
        "team_abbrev": "Team",
        "profile_team_name": "Team Name",
        "rating_team_name": "Team Name",
        "game_info": "Matchup",
        "dk_player_name": "Player",
        "team_player_name": "TEAM Slot",
        "slot": "Slot",
        "position": "Pos",
        "salary": "Salary",
        "selected_result": "Result",
        "expected_games": "Games",
        "base_dk": "Base DK/Game",
        "expected_sweep_bonus": "Sweep Bonus",
        "series_base_dk": "Series Base DK",
        "proj_dk": "Proj DK",
        "floor_dk": "Floor",
        "ceiling_dk": "Ceiling",
        "value_proj": "Value",
        "cpt_proj_dk": "CPT Proj",
        "cpt_salary": "CPT Salary",
        "cpt_value": "CPT Value",
        "team_proj_dk": "TEAM Proj",
        "team_ceiling_dk": "TEAM Ceiling",
        "team_value": "TEAM Value",
        "team_stack_score": "Team Score",
        "series_dfs_score": "DFS Profile",
        "avg_player_dk_fp_with_gnp": "Profile Player DK",
        "avg_team_slot_dk_fp_with_gnp": "Profile TEAM DK",
        "avg_team_kills": "Avg Kills",
        "avg_kills_per_game": "Kills/Game",
        "bloodiness_score": "Bloodiness",
        "clean_stomp_score": "Sweep Score",
        "profile_label": "Profile",
        "lineup_num": "#",
        "captain_source_slot": "CPT Pos",
        "salary_left": "Salary Left",
        "projection": "Projection",
        "ceiling": "Ceiling",
        "objective_score": "Objective",
        "stack_shape": "Stack",
        "cpt_team_stack": "CPT Stack",
        "team_slot_stack": "TEAM Stack",
        "max_team_count": "Max Team",
        "fallback_proj_dk": "Model Proj",
        "hist_sample": "Hist Sample",
        "hist_avg_dk": "Hist Avg",
        "typical_dk": "Typical",
        "hist_p25_dk": "P25",
        "hist_p75_dk": "P75",
        "hist_p85_dk": "P85",
        "hist_p90_dk": "P90",
        "range_width": "Range",
        "ceiling_gap": "Ceiling Gap",
        "cpt_ceiling_dk": "CPT Ceiling",
    })


def build_team_strength(team_df):
    d = team_df.copy()
    for c in ["avg_rating", "total_avg_dk", "avg_kill_edge", "avg_dk_edge", "avg_value"]:
        if c not in d.columns:
            d[c] = 0
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)

    if "profile_team_name" not in d.columns:
        d["profile_team_name"] = d["team_abbrev"]
    d["profile_team_name"] = d["profile_team_name"].fillna(d["team_abbrev"])
    d["team_merge_key"] = d["profile_team_name"].astype(str).str.strip()

    d["team_stack_score"] = (
        d["avg_rating"] * 25.0
        + d["total_avg_dk"] * 1.20
        + d["avg_kill_edge"] * 12.0
        + d["avg_dk_edge"] * 4.0
        + d["avg_value"] * 10.0
    )
    return d


def attach_profile_for_selected_result(scenario_df, profiles_df):
    out = scenario_df.copy()
    if profiles_df.empty:
        return out

    prof = profiles_df.copy()
    prof["team_merge_key"] = prof["teamname"].astype(str).str.strip()

    keep_cols = [
        "team_merge_key", "league", "series_result", "series_count", "avg_player_dk_fp_with_gnp",
        "avg_player_dk_fp_base", "avg_player_gnp_bonus_total_5", "avg_team_kills",
        "avg_kills_per_game", "avg_team_deaths", "avg_deaths_per_game",
        "avg_game_length_minutes", "avg_team_slot_dk_fp_with_gnp", "avg_team_slot_dk_per_game",
        "series_dfs_score", "bloodiness_score", "clean_stomp_score", "profile_label",
    ]
    keep_cols = [c for c in keep_cols if c in prof.columns]

    out = out.merge(
        prof[keep_cols],
        left_on=["team_merge_key", "selected_result"],
        right_on=["team_merge_key", "series_result"],
        how="left",
    )
    return out


def build_scenario_df(team_df, match_selections, profiles_df):
    rows = []
    teams = build_team_strength(team_df)

    for game_info, g in teams.groupby("game_info", dropna=False):
        g = g.copy()
        slate_teams = g["team_abbrev"].dropna().astype(str).tolist()
        if len(slate_teams) != 2:
            continue

        selected = match_selections.get(game_info, f"{slate_teams[0]} 2-0")
        selected_team = " ".join(selected.split()[:-1])
        selected_score = selected.split()[-1]

        if selected_score == "2-0":
            win_result, loss_result = "2-0", "0-2"
        else:
            win_result, loss_result = "2-1", "1-2"

        for _, r in g.iterrows():
            team = str(r["team_abbrev"])
            result = win_result if team == selected_team else loss_result
            rows.append({
                "team_abbrev": team,
                "profile_team_name": r.get("profile_team_name", team),
                "team_merge_key": r.get("team_merge_key", team),
                "game_info": game_info,
                "selected_result": result,
                "expected_games": game_count_for_result(result),
                "expected_sweep_bonus": player_sweep_bonus(result),
                "team_expected_sweep_bonus": team_sweep_bonus(result),
                "team_stack_score": r.get("team_stack_score", 0),
                "avg_rating": r.get("avg_rating", 0),
                "total_avg_dk": r.get("total_avg_dk", 0),
                "avg_kill_edge": r.get("avg_kill_edge", 0),
                "avg_dk_edge": r.get("avg_dk_edge", 0),
                "avg_value": r.get("avg_value", 0),
            })

    scenario = pd.DataFrame(rows)
    return attach_profile_for_selected_result(scenario, profiles_df)


def build_player_projections_from_scenario(players, scenario_df, player_profiles_df=None):
    if players.empty or scenario_df.empty:
        return pd.DataFrame()

    if player_profiles_df is None:
        player_profiles_df = pd.DataFrame()

    scen_cols = [
        "team_abbrev", "game_info", "profile_team_name", "selected_result", "expected_games",
        "expected_sweep_bonus", "team_stack_score", "league", "series_count",
        "avg_player_dk_fp_with_gnp", "avg_team_kills", "avg_kills_per_game",
        "series_dfs_score", "bloodiness_score", "clean_stomp_score", "profile_label",
    ]
    scen_cols = [c for c in scen_cols if c in scenario_df.columns]

    m = players.merge(scenario_df[scen_cols], on=["team_abbrev", "game_info"], how="left")

    if "slot" not in m.columns:
        m["slot"] = m["dk_position"].apply(normalize_slot)
    else:
        m["slot"] = m["slot"].apply(normalize_slot)

    m["player_key"] = m["dk_player_name"].apply(norm_text)
    m["team_merge_key"] = m["profile_team_name"].fillna(m["team_abbrev"]).astype(str).str.strip()
    m["position_key"] = m["slot"].apply(norm_text)

    # Base fallback from your existing player rating/DK average.
    m["base_dk"] = pd.to_numeric(m.get("avg_dk"), errors="coerce")
    if "dk_avg_points" in m.columns:
        m["base_dk"] = m["base_dk"].fillna(pd.to_numeric(m["dk_avg_points"], errors="coerce"))
    m["base_dk"] = m["base_dk"].fillna(0)

    m["expected_games"] = pd.to_numeric(m["expected_games"], errors="coerce").fillna(2.5)
    m["expected_sweep_bonus"] = pd.to_numeric(m["expected_sweep_bonus"], errors="coerce").fillna(0)

    # Old fallback projection path.
    m["series_base_dk"] = (m["base_dk"] * m["expected_games"]) + m["expected_sweep_bonus"]

    m["team_stack_score"] = pd.to_numeric(m["team_stack_score"], errors="coerce").fillna(0)
    avg_stack = m["team_stack_score"].replace(0, pd.NA).dropna()
    avg_stack = avg_stack.mean() if len(avg_stack) else 250
    m["team_env_mult"] = (1 + ((m["team_stack_score"] - avg_stack) / 1200)).clip(0.90, 1.10)

    profile_score = pd.to_numeric(m.get("series_dfs_score", 0), errors="coerce").fillna(0)
    avg_profile_score = profile_score.replace(0, pd.NA).dropna()
    avg_profile_score = avg_profile_score.mean() if len(avg_profile_score) else 300
    m["outcome_mult"] = (1 + ((profile_score - avg_profile_score) / 1400)).clip(0.92, 1.10)

    for c in ["rating_score", "avg_dk_edge", "avg_kill_edge", "salary"]:
        if c not in m.columns:
            m[c] = 0
        m[c] = pd.to_numeric(m[c], errors="coerce").fillna(0)

    m["player_skill_mult"] = (
        1
        + m["rating_score"] * 0.025
        + m["avg_dk_edge"] * 0.004
        + m["avg_kill_edge"] * 0.012
    ).clip(0.85, 1.16)

    m["position_mult"] = m["slot"].apply(get_position_multiplier)

    m["fallback_proj_dk"] = (
        m["series_base_dk"]
        * m["team_env_mult"]
        * m["outcome_mult"]
        * m["player_skill_mult"]
        * m["position_mult"]
    ).clip(lower=0)

    # ------------------------------------------------------------
    # New player-history outcome range model
    # ------------------------------------------------------------
    if not player_profiles_df.empty:
        prof = player_profiles_df.copy()

        needed = [
            "player_key", "team_merge_key", "position_key", "series_result",
            "series_count", "avg_dk", "median_dk", "p25_dk", "p75_dk",
            "p85_dk", "p90_dk", "max_dk", "std_dk",
        ]
        needed = [c for c in needed if c in prof.columns]

        m = m.merge(
            prof[needed],
            left_on=["player_key", "team_merge_key", "position_key", "selected_result"],
            right_on=["player_key", "team_merge_key", "position_key", "series_result"],
            how="left",
            suffixes=("", "_hist"),
        )
    else:
        for c in ["series_result", "series_count", "avg_dk_hist", "median_dk", "p25_dk", "p75_dk", "p85_dk", "p90_dk", "max_dk", "std_dk"]:
            if c not in m.columns:
                m[c] = pd.NA

    # Normalize historical columns.
    hist_cols = ["series_count", "avg_dk_hist", "median_dk", "p25_dk", "p75_dk", "p85_dk", "p90_dk", "max_dk", "std_dk"]
    for c in hist_cols:
        if c in m.columns:
            m[c] = pd.to_numeric(m[c], errors="coerce")

    # If SQL column came in as avg_dk instead of avg_dk_hist after merge.
    if "avg_dk_hist" not in m.columns and "avg_dk" in m.columns:
        m["avg_dk_hist"] = pd.to_numeric(m["avg_dk"], errors="coerce")

    m["hist_sample"] = pd.to_numeric(m.get("series_count"), errors="coerce").fillna(0)

    # Confidence ramps up as sample increases.
    # 1-2 samples = light usage, 5+ samples = mostly trust history.
    m["hist_weight"] = (m["hist_sample"] / 5.0).clip(0.0, 0.70)

    # Historical average for selected result. Fallback to old formula if missing.
    m["hist_avg_dk"] = pd.to_numeric(m.get("avg_dk_hist"), errors="coerce")
    m["hist_median_dk"] = pd.to_numeric(m.get("median_dk"), errors="coerce")
    m["hist_p25_dk"] = pd.to_numeric(m.get("p25_dk"), errors="coerce")
    m["hist_p75_dk"] = pd.to_numeric(m.get("p75_dk"), errors="coerce")
    m["hist_p85_dk"] = pd.to_numeric(m.get("p85_dk"), errors="coerce")
    m["hist_p90_dk"] = pd.to_numeric(m.get("p90_dk"), errors="coerce")
    m["hist_max_dk"] = pd.to_numeric(m.get("max_dk"), errors="coerce")

    # Projection = blend of model projection and player result-specific average.
    m["proj_dk"] = (
        (m["fallback_proj_dk"] * (1 - m["hist_weight"]))
        + (m["hist_avg_dk"].fillna(m["fallback_proj_dk"]) * m["hist_weight"])
    ).clip(lower=0)

    # Floor = result-specific P25 where available, otherwise modest fallback.
    m["floor_dk"] = m["hist_p25_dk"].fillna(m["proj_dk"] * 0.65)

    # Typical score = median where available.
    m["typical_dk"] = m["hist_median_dk"].fillna(m["proj_dk"])

    # Ceiling = result-specific P85/P90 where available.
    # Use P90 for players with enough samples, P85 for thin samples.
    m["range_ceiling_dk"] = m.apply(
        lambda r: r["hist_p90_dk"]
        if pd.notna(r.get("hist_p90_dk")) and r.get("hist_sample", 0) >= 5
        else r.get("hist_p85_dk"),
        axis=1,
    )

    # Old multiplier fallback only if we do not have historical range.
    m["ceiling_mult"] = m.apply(
        lambda r: get_position_ceiling_multiplier(
            r.get("slot", ""),
            "2-1 Ceiling" if r.get("selected_result") in ["2-1", "1-2"] else "2-0 Sweep",
            r.get("bloodiness_score", 0),
        ),
        axis=1,
    )

    m["fallback_ceiling_dk"] = m["proj_dk"] * m["ceiling_mult"]

    m["ceiling_dk"] = pd.to_numeric(m["range_ceiling_dk"], errors="coerce").fillna(m["fallback_ceiling_dk"])

    # Safety: ceiling should not be below projection, and floor should not be above projection.
    m["ceiling_dk"] = m[["ceiling_dk", "proj_dk"]].max(axis=1)
    m["floor_dk"] = m[["floor_dk", "proj_dk"]].min(axis=1)

    m["range_width"] = m["ceiling_dk"] - m["floor_dk"]
    m["ceiling_gap"] = m["ceiling_dk"] - m["proj_dk"]

    m["value_proj"] = m.apply(lambda r: r["proj_dk"] / (r["salary"] / 1000) if r["salary"] else 0, axis=1)

    m["cpt_salary"] = m["salary"] * 1.5
    m["cpt_proj_dk"] = m["proj_dk"] * 1.5
    m["cpt_ceiling_dk"] = m["ceiling_dk"] * 1.5
    m["cpt_value"] = m.apply(lambda r: r["cpt_proj_dk"] / (r["cpt_salary"] / 1000) if r["cpt_salary"] else 0, axis=1)

    return m.sort_values(["proj_dk", "ceiling_dk", "value_proj"], ascending=False)


def build_team_projections_from_scenario(team_rows, scenario_df):
    if team_rows.empty or scenario_df.empty:
        return pd.DataFrame()

    scen_cols = [
        "team_abbrev", "game_info", "profile_team_name", "selected_result", "expected_games",
        "team_expected_sweep_bonus", "team_stack_score", "league", "series_count",
        "avg_team_slot_dk_fp_with_gnp", "avg_team_slot_dk_per_game", "series_dfs_score", "profile_label",
    ]
    scen_cols = [c for c in scen_cols if c in scenario_df.columns]

    m = team_rows.merge(scenario_df[scen_cols], on=["team_abbrev", "game_info"], how="left")
    m["salary"] = pd.to_numeric(m["salary"], errors="coerce").fillna(0)
    m["dk_avg_points"] = pd.to_numeric(m["dk_avg_points"], errors="coerce").fillna(0)
    m["expected_games"] = pd.to_numeric(m.get("expected_games", 2.5), errors="coerce").fillna(2.5)
    m["team_expected_sweep_bonus"] = pd.to_numeric(m.get("team_expected_sweep_bonus", 0), errors="coerce").fillna(0)

    m["team_proj_dk"] = pd.to_numeric(m.get("avg_team_slot_dk_fp_with_gnp", 0), errors="coerce").fillna(0)
    m["team_proj_dk"] = m.apply(
        lambda r: r["team_proj_dk"] if r["team_proj_dk"] > 0 else (r["dk_avg_points"] * r["expected_games"] + r["team_expected_sweep_bonus"]),
        axis=1,
    )
    m["team_ceiling_dk"] = m["team_proj_dk"] * 1.35
    m["team_value"] = m.apply(lambda r: r["team_proj_dk"] / (r["salary"] / 1000) if r["salary"] else 0, axis=1)
    return m.sort_values("team_proj_dk", ascending=False)


# ============================================================
# App Body
# ============================================================

st.title("LoL Scenario Lineup Builder")
st.caption("Pick the match result scenario first, then projections and lineups rebuild from those exact results.")

if not DB_SERVER or not DB_DATABASE:
    st.error("Missing DB_SERVER or DB_DATABASE in your .env file.")
    st.stop()

st.sidebar.header("Slate")

try:
    slate_dates = get_slate_dates()
except Exception as e:
    st.error("Could not load slate dates.")
    st.exception(e)
    st.stop()

selected_date = st.sidebar.selectbox("Slate Date", slate_dates, key="scenario_slate_date")
slate_names = get_slate_names(selected_date)
selected_slate = st.sidebar.selectbox("Slate Name", slate_names, key="scenario_slate_name")
use_starters_only = st.sidebar.checkbox("Use manual starters only", value=True, key="scenario_starters")

if st.sidebar.button("Clear cache / refresh", key="scenario_refresh"):
    st.cache_data.clear()
    st.rerun()

players_raw = cached_load_slate_players(selected_date, selected_slate)
team_rows = cached_load_team_rows(selected_date, selected_slate)

if players_raw.empty:
    st.warning("No player rows found.")
    st.stop()
if team_rows.empty:
    st.warning("No TEAM rows found.")
    st.stop()

if use_starters_only:
    manual = load_manual_starters()
    players = apply_manual_starters(players_raw, manual)

    if manual is None:
        starter_msg = "No valid manual starters file found. Using all non-CPT players."
    elif len(players) == len(players_raw):
        starter_msg = "Manual starters did not match or were not applied. Using all non-CPT players."
    else:
        starter_msg = "Using manual starters only."
else:
    players = players_raw.copy()
    starter_msg = "Using all non-CPT players."

if "slot" not in players.columns:
    players["slot"] = players["dk_position"].apply(normalize_slot)
else:
    players["slot"] = players["slot"].apply(normalize_slot)

st.sidebar.info(starter_msg)

team_df = build_team_strength(build_team_overview(players))
profile_team_names = tuple(get_slate_profile_team_names(players))
profiles_df = cached_load_profiles(profile_team_names)
player_profiles_df = cached_load_player_series_profiles(profile_team_names)

if profiles_df.empty:
    st.warning("No LPL/LCK series profiles matched. Projections will rely more on DK averages and team strength.")

matchups = []
for game_info, g in team_df.groupby("game_info", dropna=False):
    teams = g["team_abbrev"].dropna().astype(str).tolist()
    if len(teams) == 2:
        matchups.append((game_info, teams[0], teams[1]))

if not matchups:
    st.error("Could not detect two-team matchups from game_info.")
    st.stop()

st.caption(f"Loaded {len(players):,} player rows and {len(team_rows):,} TEAM rows for {selected_date} — {selected_slate}")

tab_results, tab_proj, tab_build, tab_raw = st.tabs(["Match Results", "Projections", "Build Lineups", "Raw Inputs"])

# Shared selections are created in tab_results, then used below.
match_selections = {}

with tab_results:
    st.header("Expected Match Results")
    st.write("Choose the exact series result for each match. A 2-0 winner gets the DK game-not-played bonus baked into player and TEAM projections.")

    for game_info, team_a, team_b in matchups:
        g = team_df[team_df["game_info"] == game_info].sort_values("team_stack_score", ascending=False)
        default_winner = str(g.iloc[0]["team_abbrev"])
        options = [f"{team_a} 2-0", f"{team_a} 2-1", f"{team_b} 2-1", f"{team_b} 2-0"]
        default = options.index(f"{default_winner} 2-0") if f"{default_winner} 2-0" in options else 0
        match_selections[game_info] = st.selectbox(
            str(game_info),
            options=options,
            index=default,
            key=f"result_{game_info}",
        )

scenario_df = build_scenario_df(team_df, match_selections, profiles_df)
player_proj_df = build_player_projections_from_scenario(
    players,
    scenario_df,
    player_profiles_df,
)
team_proj_df = build_team_projections_from_scenario(team_rows, scenario_df)

with tab_results:
    st.subheader("Scenario Team Results")
    scenario_cols = [
        "team_abbrev", "profile_team_name", "game_info", "selected_result", "expected_games",
        "expected_sweep_bonus", "team_stack_score", "league", "series_count", "series_dfs_score",
        "avg_player_dk_fp_with_gnp", "avg_team_slot_dk_fp_with_gnp", "avg_team_kills",
        "avg_kills_per_game", "bloodiness_score", "clean_stomp_score", "profile_label",
    ]
    scenario_cols = [c for c in scenario_cols if c in scenario_df.columns]
    st.dataframe(rename_for_display(format_df(scenario_df[scenario_cols])), use_container_width=True, hide_index=True)

with tab_proj:
    st.header("Scenario Projections")

    st.subheader("Player Projections")
    pos_options = ["TOP", "JNG", "MID", "ADC", "SUP"]
    selected_pos = st.multiselect("Positions", pos_options, default=pos_options, key="proj_pos")
    selected_teams = st.multiselect(
        "Teams",
        sorted(player_proj_df["team_abbrev"].dropna().astype(str).unique().tolist()),
        default=sorted(player_proj_df["team_abbrev"].dropna().astype(str).unique().tolist()),
        key="proj_teams",
    )
    view_players = player_proj_df[
        player_proj_df["slot"].isin(selected_pos)
        & player_proj_df["team_abbrev"].astype(str).isin(selected_teams)
    ].copy()
    player_cols = [
        "dk_player_name", "team_abbrev", "rating_team_name", "game_info", "slot", "salary",
        "selected_result", "expected_games",
        "base_dk", "fallback_proj_dk",
        "hist_sample", "hist_avg_dk", "typical_dk", "hist_p25_dk", "hist_p75_dk", "hist_p85_dk", "hist_p90_dk",
        "proj_dk", "floor_dk", "ceiling_dk", "range_width", "ceiling_gap",
        "value_proj", "cpt_proj_dk", "cpt_salary", "cpt_value",
        "rating_score", "series_dfs_score", "profile_label",
    ]
    player_cols = [c for c in player_cols if c in view_players.columns]
    st.dataframe(rename_for_display(format_df(view_players[player_cols])), use_container_width=True, hide_index=True)

    with st.expander("Projection Multipliers"):
        detail_cols = [
            "dk_player_name", "team_abbrev", "slot", "selected_result", "proj_dk", "team_env_mult",
            "outcome_mult", "player_skill_mult", "position_mult", "team_stack_score",
            "series_dfs_score", "bloodiness_score", "clean_stomp_score",
        ]
        detail_cols = [c for c in detail_cols if c in view_players.columns]
        st.dataframe(rename_for_display(format_df(view_players[detail_cols])), use_container_width=True, hide_index=True)

    st.subheader("TEAM Slot Projections")
    team_cols = [
        "team_player_name", "team_abbrev", "game_info", "salary", "selected_result", "expected_games",
        "team_proj_dk", "team_ceiling_dk", "team_value", "series_count", "avg_team_slot_dk_fp_with_gnp", "profile_label",
    ]
    team_cols = [c for c in team_cols if c in team_proj_df.columns]
    st.dataframe(rename_for_display(format_df(team_proj_df[team_cols])), use_container_width=True, hide_index=True)

with tab_build:
    st.header("Build Lineups")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        num_lineups = st.number_input("Lineups", min_value=1, max_value=150, value=10, step=1, key="build_n")
    with c2:
        salary_cap = st.number_input("Salary Cap", min_value=45000, max_value=50000, value=50000, step=100, key="build_cap")
    with c3:
        min_diff = st.number_input("Min Diff", min_value=0, max_value=10, value=2, step=1, key="build_diff")
    with c4:
        max_candidates = st.number_input("Max Candidates", min_value=1000, max_value=250000, value=50000, step=5000, key="build_cand")

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        allowed_shape_labels = st.multiselect("Stack Shapes", ["4-3", "4-2-1"], default=["4-3", "4-2-1"], key="build_shapes")
    with c6:
        max_team = st.number_input("Max From Team", min_value=3, max_value=5, value=4, step=1, key="build_max_team")
    with c7:
        min_cpt_team = st.number_input("Min CPT Team Stack", min_value=1, max_value=5, value=3, step=1, key="build_cpt_stack")
    with c8:
        min_team_slot_stack = st.number_input("Min TEAM Slot Stack", min_value=0, max_value=5, value=3, step=1, key="build_team_stack")

    allowed_cpt_slots = st.multiselect(
        "Allowed CPT Positions",
        ["ADC", "MID", "JNG", "TOP", "SUP", "TEAM"],
        default=["ADC", "MID", "JNG"],
        key="build_cpt_slots",
    )

    objective_mode = st.selectbox(
        "Objective",
        ["Projection", "Ceiling", "Projection + Structure"],
        index=2,
        key="build_objective",
    )

    allowed_stack_shapes = []
    if "4-3" in allowed_shape_labels:
        allowed_stack_shapes.append((4, 3))
    if "4-2-1" in allowed_shape_labels:
        allowed_stack_shapes.append((4, 2, 1))

    team_slot_rule = st.selectbox(
        "TEAM Slot Rule",
        [
            "Stacked with CPT team",
            "Stacked with any player team",
            "Allow one-off winner TEAM",
        ],
        index=1,
        key="build_team_slot_rule",
)

    if st.button("Build Top Lineups", type="primary", key="build_button"):
        if not allowed_stack_shapes:
            st.error("Select at least one stack shape.")
        elif not allowed_cpt_slots:
            st.error("Select at least one CPT position.")
        else:
            try:
                lineups, candidate_count = build_top_lineups(
                    player_proj_df=player_proj_df,
                    team_proj_df=team_proj_df,
                    num_lineups=int(num_lineups),
                    salary_cap=int(salary_cap),
                    min_cpt_team=int(min_cpt_team),
                    max_team=int(max_team),
                    min_diff=int(min_diff),
                    max_candidates=int(max_candidates),
                    allowed_stack_shapes=tuple(allowed_stack_shapes),
                    min_team_slot_stack=int(min_team_slot_stack),
                    allowed_cpt_slots=tuple(allowed_cpt_slots),
                    objective_mode=objective_mode,
                )
                lineup_df = lineups_to_df(lineups)
                if lineup_df.empty:
                    st.warning("No valid lineups built. Loosen the settings.")
                else:
                    st.success(f"Built {len(lineup_df)} lineups from {candidate_count:,} retained candidates.")
                    st.dataframe(rename_for_display(format_df(lineup_df)), use_container_width=True, hide_index=True)

                    tag = "_".join(str(v).replace(" ", "") for v in match_selections.values())
                    tag = "".join(ch for ch in tag if ch.isalnum() or ch in ["_", "-"])
                    output_path = OUTPUT_DIR / f"scenario_lineups_{selected_date}_{selected_slate}_{tag}.csv"
                    lineup_df.to_csv(output_path, index=False)
                    st.info(f"Saved CSV to: {output_path}")

                    st.download_button(
                        "Download CSV",
                        data=lineup_df.to_csv(index=False).encode("utf-8"),
                        file_name=output_path.name,
                        mime="text/csv",
                        key="download_lineups",
                    )
            except Exception as e:
                st.error("Lineup build failed.")
                st.exception(e)

with tab_raw:
    st.header("Raw Inputs")
    with st.expander("Players Used"):
        st.dataframe(format_df(players), use_container_width=True, hide_index=True)
    with st.expander("TEAM Rows"):
        st.dataframe(format_df(team_rows), use_container_width=True, hide_index=True)
    with st.expander("Team Overview"):
        st.dataframe(rename_for_display(format_df(team_df)), use_container_width=True, hide_index=True)
    with st.expander("Series Profiles"):
        st.dataframe(rename_for_display(format_df(profiles_df)), use_container_width=True, hide_index=True)
