import os
from pathlib import Path

import pandas as pd
import pyodbc
import streamlit as st
from dotenv import load_dotenv
from engine.jobs import list_jobs, run_job


# ============================================================
# App Config
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

DB_SERVER = os.getenv("DB_SERVER", r"DESKTOP-I9OLS14\SQLEXPRESS")
DB_DATABASE = os.getenv("DB_DATABASE", "lol_esports")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")

LINEUPS_DIR = BASE_DIR / "lineups"
SLATE_DIR = BASE_DIR / "data" / "slate_data"
CONTEST_DIR = BASE_DIR / "data" / "contest-standings"
MANUAL_STARTERS_PATH = BASE_DIR / "data" / "manual_starters.csv"


st.set_page_config(
    page_title="LoL DFS Command Center",
    page_icon="🎮",
    layout="wide",
)


# ============================================================
# Helpers
# ============================================================

@st.cache_resource(show_spinner=False)
def get_conn():
    conn_str = (
        f"DRIVER={{{DB_DRIVER}}};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_DATABASE};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str)


@st.cache_data(ttl=60, show_spinner=False)
def read_sql(sql: str, params=None) -> pd.DataFrame:
    conn = get_conn()
    return pd.read_sql(sql, conn, params=params)


def safe_query(sql: str, params=None) -> pd.DataFrame:
    try:
        return read_sql(sql, params=params)
    except Exception as e:
        st.error(f"SQL error: {e}")
        return pd.DataFrame()


def fmt_int(x):
    try:
        if pd.isna(x):
            return "0"
        return f"{int(x):,}"
    except Exception:
        return "0"


def fmt_pct(x):
    try:
        if pd.isna(x):
            return "—"
        return f"{float(x):.1%}"
    except Exception:
        return "—"


def fmt_num(x, digits=2):
    try:
        if pd.isna(x):
            return "—"
        return f"{float(x):,.{digits}f}"
    except Exception:
        return "—"


def status_badge(label: str, status: str):
    status = str(status).upper().strip()

    if status in {"READY", "OK", "COMPLETE", "LOADED", "YES"}:
        color = "#16a34a"
    elif status in {"WARNING", "CHECK", "PARTIAL"}:
        color = "#ca8a04"
    elif status in {"MISSING", "ERROR", "NO", "NEEDS REVIEW"}:
        color = "#dc2626"
    else:
        color = "#64748b"

    st.markdown(
        f"""
        <div style="
            border:1px solid #e5e7eb;
            border-radius:12px;
            padding:12px 14px;
            background:#ffffff;
            box-shadow:0 1px 2px rgba(0,0,0,0.04);
        ">
            <div style="font-size:13px;color:#64748b;margin-bottom:4px;">{label}</div>
            <div style="font-size:20px;font-weight:700;color:{color};">{status}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_latest_slate_from_db():
    sql = """
    SELECT TOP 1
        slate_date,
        slate_name,
        COUNT(*) AS slate_rows,
        COUNT(DISTINCT team_abbrev) AS teams,
        SUM(CASE WHEN LOWER(ISNULL(dk_position, '')) IN ('team') THEN 1 ELSE 0 END) AS team_rows,
        SUM(CASE WHEN LOWER(ISNULL(dk_position, '')) NOT IN ('team') THEN 1 ELSE 0 END) AS player_rows
    FROM dbo.dk_lol_slate_player
    GROUP BY slate_date, slate_name
    ORDER BY slate_date DESC, slate_name DESC;
    """
    df = safe_query(sql)
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def get_available_slates():
    sql = """
    SELECT
        slate_date,
        slate_name,
        COUNT(*) AS slate_rows,
        COUNT(DISTINCT team_abbrev) AS teams
    FROM dbo.dk_lol_slate_player
    GROUP BY slate_date, slate_name
    ORDER BY slate_date DESC, slate_name;
    """
    return safe_query(sql)


def get_manual_starters_summary():
    if not MANUAL_STARTERS_PATH.exists():
        return {
            "exists": False,
            "rows": 0,
            "starters": 0,
            "teams": 0,
        }

    try:
        df = pd.read_csv(MANUAL_STARTERS_PATH)
        starters = 0
        if "is_starter" in df.columns:
            starters = int(pd.to_numeric(df["is_starter"], errors="coerce").fillna(0).sum())

        teams = int(df["teamname"].nunique()) if "teamname" in df.columns else 0

        return {
            "exists": True,
            "rows": len(df),
            "starters": starters,
            "teams": teams,
        }
    except Exception:
        return {
            "exists": False,
            "rows": 0,
            "starters": 0,
            "teams": 0,
        }


def count_matching_files(folder: Path, pattern: str):
    if not folder.exists():
        return 0
    return len(list(folder.glob(pattern)))


def get_lineup_file_count(slate_date, slate_name):
    if not LINEUPS_DIR.exists():
        return 0

    date_str = str(slate_date)
    slate_name = str(slate_name)

    patterns = [
        f"*{date_str}*{slate_name}*.csv",
        f"*{date_str}*.csv",
    ]

    files = set()
    for pattern in patterns:
        for p in LINEUPS_DIR.glob(pattern):
            files.add(p)

    return len(files)


def app_header():
    st.title("🎮 LoL DFS Command Center")
    st.caption(
        "iRebal-style control center for slate health, starters, Bayes, ownership, lineups, and contest review."
    )


# ============================================================
# Sidebar / Slate Selection
# ============================================================

app_header()

with st.sidebar:
    st.header("Command Center")

    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    slates_df = get_available_slates()

    if slates_df.empty:
        st.error("No slates found in dbo.dk_lol_slate_player.")
        st.stop()

    slates_df["slate_label"] = (
        slates_df["slate_date"].astype(str)
        + " | "
        + slates_df["slate_name"].astype(str)
        + " | rows "
        + slates_df["slate_rows"].astype(str)
    )

    selected_label = st.selectbox(
        "Slate",
        options=slates_df["slate_label"].tolist(),
        index=0,
    )

    selected_row = slates_df[slates_df["slate_label"] == selected_label].iloc[0]
    selected_slate_date = selected_row["slate_date"]
    selected_slate_name = selected_row["slate_name"]

    st.caption(f"Selected: {selected_slate_date} / {selected_slate_name}")

    page = st.radio(
        "Navigation",
        [
            "Slate Dashboard",
            "Data Health",
            "Exceptions",
            "Starter Review",
            "Bayes Review",
            "Ownership Review",
            "Contest Review",
            "Top 1% Lineups",
            "Daily Commands",
        ],
    )


# ============================================================
# Queries
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def get_slate_players(slate_date, slate_name):
    sql = """
    SELECT
        slate_date,
        slate_name,
        dk_position,
        roster_position,
        player_name,
        dk_player_id,
        team_abbrev,
        game_info,
        salary,
        avg_points_per_game,
        loaded_at
    FROM dbo.dk_lol_slate_player
    WHERE slate_date = ?
      AND slate_name = ?
    ORDER BY team_abbrev, dk_position, player_name;
    """
    return read_sql(sql, params=[slate_date, slate_name])


@st.cache_data(ttl=60, show_spinner=False)
def get_today_lane_ratings(slate_date, slate_name):
    sql = """
    SELECT
        signal_version,
        game_date AS slate_date,
        slate_name,
        game_info,
        league,
        team AS team_abbrev,
        opponent AS opponent_abbrev,
        team_full_name,
        opponent_full_name,
        bayes_win_pct,
        adjusted_win_pct,
        lane_rows,
        rated_lane_rows,
        top_lane_edge,
        jng_lane_edge,
        mid_lane_edge,
        adc_lane_edge,
        sup_lane_edge,
        total_lane_edge,
        carry_lane_edge,
        main_carry_lane_edge,
        secondary_lane_edge,
        opponent_neutralized_lanes,
        opponent_neutral_high_edges,
        total_lane_edge_tier,
        carry_lane_edge_tier,
        lane_power_win_pct,
        dfs_lane_power_signal,
        dfs_lane_power_note
    FROM dbo.vw_lol_slate_lane_power_signal_live_v1
    WHERE game_date = ?
      AND slate_name = ?
    ORDER BY team;
    """
    return read_sql(sql, params=[slate_date, slate_name])


@st.cache_data(ttl=60, show_spinner=False)
def get_ownership_training(slate_date, slate_name):
    sql = """
    SELECT
        slate_date,
        slate_name,
        ownership_player_name,
        dk_player_name,
        dk_player_id,
        ownership_roster_position,
        ownership_slot_type,
        dk_position,
        dk_roster_position,
        team_abbrev,
        opponent_abbrev,
        game_info,
        position,
        salary,
        ownership_pct,
        actual_fp,
        games,
        avg_dk,
        rating_score,
        dk_value,
        starter_role,
        is_starter,
        actual_starter_flag,
        bayes_sample_type,
        bayes_similar_sample,
        bayes_win_pct,
        bayes_p_2_0,
        bayes_p_2_1,
        bayes_p_1_2,
        bayes_p_0_2,
        bayes_suggested_path,
        suggested_winner_teamname,
        suggested_match_score,
        team_strength_bucket,
        opponent_strength_bucket,
        strength_matchup_bucket,
        salary_tier,
        bayes_team_win_flag,
        bayes_sweep_flag
    FROM dbo.vw_lol_ownership_training
    WHERE slate_date = ?
      AND slate_name = ?
    ORDER BY team_abbrev, position, dk_player_name;
    """
    return read_sql(sql, params=[slate_date, slate_name])


@st.cache_data(ttl=60, show_spinner=False)
def get_bayes_backtest():
    sql = """
    SELECT TOP 500
        target_series_date,
        league,
        team_a,
        team_b,
        predicted_winner_teamname,
        predicted_match_score,
        predicted_winner_bayes_win_pct,
        prediction_sample_type,
        prediction_similar_sample,
        actual_winner_teamname,
        actual_match_score,
        match_winner_correct,
        match_score_correct,
        match_confidence_label,
        dfs_note
    FROM dbo.vw_lol_bayes_prediction_backtest_match_level
    ORDER BY target_series_date DESC, league, team_a, team_b;
    """
    return read_sql(sql)


@st.cache_data(ttl=60, show_spinner=False)
def get_contest_summary(slate_date, slate_name):
    sql = """
    SELECT
        slate_date,
        slate_name,
        contest_id,
        lineups,
        best_rank,
        worst_rank,
        winning_score,
        avg_score
    FROM lol.vw_contest_summary
    WHERE slate_date = ?
      AND slate_name = ?
    ORDER BY contest_id;
    """
    return read_sql(sql, params=[slate_date, slate_name])


@st.cache_data(ttl=60, show_spinner=False)
def get_finish_bucket_summary(slate_date, slate_name):
    sql = """
    SELECT
        slate_date,
        slate_name,
        contest_id,
        finish_bucket,
        lineups,
        avg_points,
        avg_total_ownership,
        avg_player_ownership,
        avg_salary_left
    FROM lol.vw_finish_bucket_summary
    WHERE slate_date = ?
      AND slate_name = ?
    ORDER BY contest_id, finish_bucket;
    """
    return read_sql(sql, params=[slate_date, slate_name])


@st.cache_data(ttl=60, show_spinner=False)
def get_top_1pct_lineups(slate_date, slate_name):
    sql = """
    SELECT TOP 200
        slate_date,
        slate_name,
        contest_id,
        rank_num,
        points,
        captain_player,
        captain_team,
        captain_position,
        stack_structure,
        team_stack_summary,
        total_ownership,
        avg_ownership,
        salary_left,
        lineup_raw
    FROM lol.vw_top_1pct_lineups
    WHERE slate_date = ?
      AND slate_name = ?
    ORDER BY rank_num ASC, points DESC;
    """
    return read_sql(sql, params=[slate_date, slate_name])


@st.cache_data(ttl=60, show_spinner=False)
def get_raw_contest_counts(slate_date, slate_name):
    sql = """
    SELECT
        slate_date,
        slate_name,
        COUNT(*) AS raw_contest_rows,
        COUNT(DISTINCT contest_id) AS contests,
        MAX(loaded_at) AS last_loaded_at
    FROM raw.dk_lol_contest_standings
    WHERE slate_date = ?
      AND slate_name = ?
    GROUP BY slate_date, slate_name;
    """
    return read_sql(sql, params=[slate_date, slate_name])


@st.cache_data(ttl=60, show_spinner=False)
def get_raw_ownership_counts(slate_date, slate_name):
    sql = """
    SELECT
        slate_date,
        slate_name,
        COUNT(*) AS raw_ownership_rows,
        COUNT(DISTINCT contest_id) AS contests,
        MAX(loaded_at) AS last_loaded_at
    FROM raw.dk_lol_player_ownership
    WHERE slate_date = ?
      AND slate_name = ?
    GROUP BY slate_date, slate_name;
    """
    return read_sql(sql, params=[slate_date, slate_name])


# ============================================================
# Load Selected Slate Data
# ============================================================

slate_players_df = safe_query(
    """
    SELECT
        slate_date,
        slate_name,
        dk_position,
        roster_position,
        player_name,
        dk_player_id,
        team_abbrev,
        game_info,
        salary,
        avg_points_per_game,
        loaded_at
    FROM dbo.dk_lol_slate_player
    WHERE slate_date = ?
      AND slate_name = ?
    ORDER BY team_abbrev, dk_position, player_name;
    """,
    params=[selected_slate_date, selected_slate_name],
)

lane_df = safe_query(
    """
    SELECT
        signal_version,
        game_date AS slate_date,
        slate_name,
        game_info,
        league,
        team AS team_abbrev,
        opponent AS opponent_abbrev,
        team_full_name,
        opponent_full_name,
        bayes_win_pct,
        adjusted_win_pct,
        lane_rows,
        rated_lane_rows,
        top_lane_edge,
        jng_lane_edge,
        mid_lane_edge,
        adc_lane_edge,
        sup_lane_edge,
        total_lane_edge,
        carry_lane_edge,
        main_carry_lane_edge,
        secondary_lane_edge,
        opponent_neutralized_lanes,
        opponent_neutral_high_edges,
        total_lane_edge_tier,
        carry_lane_edge_tier,
        lane_power_win_pct,
        dfs_lane_power_signal,
        dfs_lane_power_note
    FROM dbo.vw_lol_slate_lane_power_signal_live_v1
    WHERE game_date = ?
      AND slate_name = ?
    ORDER BY team;
    """,
    params=[selected_slate_date, selected_slate_name],
)
ownership_df = safe_query(
    """
    SELECT
        slate_date,
        slate_name,
        ownership_player_name,
        dk_player_name,
        dk_player_id,
        ownership_roster_position,
        ownership_slot_type,
        dk_position,
        dk_roster_position,
        team_abbrev,
        opponent_abbrev,
        game_info,
        position,
        salary,
        ownership_pct,
        actual_fp,
        games,
        avg_dk,
        rating_score,
        dk_value,
        starter_role,
        is_starter,
        actual_starter_flag,
        bayes_sample_type,
        bayes_similar_sample,
        bayes_win_pct,
        bayes_p_2_0,
        bayes_p_2_1,
        bayes_p_1_2,
        bayes_p_0_2,
        bayes_suggested_path,
        suggested_winner_teamname,
        suggested_match_score,
        team_strength_bucket,
        opponent_strength_bucket,
        strength_matchup_bucket,
        salary_tier,
        bayes_team_win_flag,
        bayes_sweep_flag
    FROM dbo.vw_lol_ownership_training
    WHERE slate_date = ?
      AND slate_name = ?
    ORDER BY team_abbrev, position, dk_player_name;
    """,
    params=[selected_slate_date, selected_slate_name],
)


manual_summary = get_manual_starters_summary()
lineup_file_count = get_lineup_file_count(selected_slate_date, selected_slate_name)


# ============================================================
# Health Calculations
# ============================================================

slate_rows = len(slate_players_df)
teams_count = slate_players_df["team_abbrev"].nunique() if not slate_players_df.empty else 0

player_rows = 0
team_rows = 0

if not slate_players_df.empty:
    player_rows = int((slate_players_df["dk_position"].astype(str).str.lower() != "team").sum())
    team_rows = int((slate_players_df["dk_position"].astype(str).str.lower() == "team").sum())

lane_rows = len(lane_df)
ownership_rows = len(ownership_df)

missing_lane_rows = 0

missing_bayes_rows = 0
matched_bayes_rows = 0

if not ownership_df.empty and "bayes_win_pct" in ownership_df.columns:
    missing_bayes_rows = int(ownership_df["bayes_win_pct"].isna().sum())
    matched_bayes_rows = int(ownership_df["bayes_win_pct"].notna().sum())

contest_counts_df = safe_query(
    """
    SELECT
        slate_date,
        slate_name,
        COUNT(*) AS raw_contest_rows,
        COUNT(DISTINCT contest_id) AS contests,
        MAX(loaded_at) AS last_loaded_at
    FROM raw.dk_lol_contest_standings
    WHERE slate_date = ?
      AND slate_name = ?
    GROUP BY slate_date, slate_name;
    """,
    params=[selected_slate_date, selected_slate_name],
)

ownership_counts_df = safe_query(
    """
    SELECT
        slate_date,
        slate_name,
        COUNT(*) AS raw_ownership_rows,
        COUNT(DISTINCT contest_id) AS contests,
        MAX(loaded_at) AS last_loaded_at
    FROM raw.dk_lol_player_ownership
    WHERE slate_date = ?
      AND slate_name = ?
    GROUP BY slate_date, slate_name;
    """,
    params=[selected_slate_date, selected_slate_name],
)

raw_contest_rows = int(contest_counts_df["raw_contest_rows"].iloc[0]) if not contest_counts_df.empty else 0
raw_ownership_rows = int(ownership_counts_df["raw_ownership_rows"].iloc[0]) if not ownership_counts_df.empty else 0


def determine_overall_status():
    if slate_rows == 0:
        return "MISSING SLATE"

    if manual_summary["starters"] == 0:
        return "NEEDS STARTERS"

    if ownership_rows > 0 and missing_bayes_rows == ownership_rows:
        return "MISSING BAYES"

    if ownership_rows == 0:
        return "NO OWNERSHIP YET"

    if lineup_file_count == 0:
        return "READY TO BUILD"

    if raw_contest_rows > 0:
        return "CONTEST REVIEW READY"

    return "LINEUPS BUILT"


overall_status = determine_overall_status()

def build_exceptions(
    slate_players_df,
    lane_df,
    ownership_df,
    manual_summary,
    raw_contest_rows,
    raw_ownership_rows,
    lineup_file_count,
    selected_slate_date,
    selected_slate_name,
):
    exceptions = []

    def add_exception(
        severity,
        category,
        issue,
        detail,
        suggested_action,
        row_count=None,
    ):
        exceptions.append(
            {
                "severity": severity,
                "category": category,
                "issue": issue,
                "detail": detail,
                "suggested_action": suggested_action,
                "row_count": row_count,
            }
        )

    # ------------------------------------------------------------
    # Slate checks
    # ------------------------------------------------------------
    if slate_players_df.empty:
        add_exception(
            "HIGH",
            "Slate",
            "No DK slate rows loaded",
            f"No rows found for {selected_slate_date} / {selected_slate_name}.",
            "Run scripts\\ingest_dk_lol_slate.py and confirm the slate file name is correct.",
            0,
        )
        return pd.DataFrame(exceptions)

    player_rows_df = slate_players_df[
        slate_players_df["dk_position"].astype(str).str.lower() != "team"
    ].copy()

    team_rows_df = slate_players_df[
        slate_players_df["dk_position"].astype(str).str.lower() == "team"
    ].copy()

    if player_rows_df.empty:
        add_exception(
            "HIGH",
            "Slate",
            "No player rows found",
            "Slate exists, but no non-TEAM player rows were detected.",
            "Check DK slate ingest logic and dk_position values.",
            0,
        )

    if team_rows_df.empty:
        add_exception(
            "MEDIUM",
            "Slate",
            "No TEAM rows found",
            "Slate exists, but no TEAM slot rows were detected.",
            "Check DK slate ingest logic. TEAM rows are needed for lineup building.",
            0,
        )

    # ------------------------------------------------------------
    # Manual starter checks
    # ------------------------------------------------------------
    if not manual_summary.get("exists", False):
        add_exception(
            "HIGH",
            "Starters",
            "manual_starters.csv missing",
            "The manual starters file does not exist.",
            "Run scripts\\build_manual_starters_from_dk.py.",
            0,
        )
    elif manual_summary.get("starters", 0) == 0:
        add_exception(
            "HIGH",
            "Starters",
            "No starters selected",
            "manual_starters.csv exists, but no players are marked is_starter = 1.",
            "Open data\\manual_starters.csv and mark starters.",
            manual_summary.get("rows", 0),
        )
    elif manual_summary.get("starters", 0) < 10:
        add_exception(
            "MEDIUM",
            "Starters",
            "Low starter count",
            f"Only {manual_summary.get('starters', 0)} starters are marked.",
            "Confirm all teams have 5 starters marked.",
            manual_summary.get("starters", 0),
        )

    # ------------------------------------------------------------
    # Lane rating checks
    # ------------------------------------------------------------
    if lane_df.empty:
        add_exception(
            "HIGH",
            "Ratings",
            "No lane rating rows",
            "No rows found in dbo.v_lol_today_slate_with_lane_ratings for this slate.",
            "Run player/team/lane build scripts, then rebuild the playbook.",
            0,
        )

    else:
        # New lane-power signal is team/matchup-level, not player-level.
        # So do not compare it to slate player names unless a player-name column exists.
        if "dk_player_name" in lane_df.columns:
            slate_player_names = set(
                player_rows_df["player_name"].astype(str).str.strip().str.lower()
            )
            lane_player_names = set(
                lane_df["dk_player_name"].astype(str).str.strip().str.lower()
            )

            missing_lane_names = sorted(slate_player_names - lane_player_names)

            if missing_lane_names:
                preview = ", ".join(missing_lane_names[:10])
                add_exception(
                    "MEDIUM",
                    "Ratings",
                    "Some slate players missing lane ratings",
                    f"{len(missing_lane_names)} player(s) from DK slate are missing lane rating rows. Example: {preview}",
                    "Check name matching between DK slate and Oracle/player rating data.",
                    len(missing_lane_names),
                )
        else:
            add_exception(
                "OK",
                "Ratings",
                "Lane power signal available",
                f"{len(lane_df)} team/matchup lane-power row(s) found for this slate.",
                "Use this as the slate-level lane power check. Player-level missing checks are skipped for this view.",
                len(lane_df),
            )

        if "games" in lane_df.columns:
            low_games = lane_df[
                pd.to_numeric(lane_df["games"], errors="coerce").fillna(0) < 3
            ]

            if not low_games.empty:
                add_exception(
                    "LOW",
                    "Ratings",
                    "Low sample player ratings",
                    f"{len(low_games)} player(s) have fewer than 3 rated games.",
                    "Review these players manually. Low samples can distort rating_score and dk_value.",
                    len(low_games),
                )

    # ------------------------------------------------------------
    # Ownership checks
    # ------------------------------------------------------------
    if ownership_df.empty:
        add_exception(
            "HIGH",
            "Ownership",
            "No ownership training rows",
            "No rows found in dbo.vw_lol_ownership_training for this slate.",
            "This is expected before contest results/ownership are loaded. After contest finishes, run contest ingest, transform, and enrich scripts.",
            0,
        )
    else:
        if "ownership_pct" in ownership_df.columns:
            missing_own = ownership_df["ownership_pct"].isna().sum()
            if missing_own > 0:
                add_exception(
                    "MEDIUM",
                    "Ownership",
                    "Missing ownership percentage",
                    f"{missing_own} ownership rows have NULL ownership_pct.",
                    "Check raw.dk_lol_player_ownership and contest standings import.",
                    int(missing_own),
                )

        if "bayes_win_pct" in ownership_df.columns:
            missing_bayes = ownership_df["bayes_win_pct"].isna().sum()
            total_own = len(ownership_df)

            if missing_bayes == total_own:
                add_exception(
                    "HIGH",
                    "Bayes",
                    "All Bayes values missing",
                    "Every ownership training row has NULL bayes_win_pct.",
                    "Run/review Bayes SQL views and confirm team/opponent matching for this slate.",
                    int(missing_bayes),
                )
            elif missing_bayes > 0:
                add_exception(
                    "MEDIUM",
                    "Bayes",
                    "Some Bayes values missing",
                    f"{missing_bayes} of {total_own} rows have NULL bayes_win_pct.",
                    "Check unmatched teams, league names, or strength matchup joins.",
                    int(missing_bayes),
                )

        if "bayes_similar_sample" in ownership_df.columns:
            low_sample = ownership_df[
                pd.to_numeric(ownership_df["bayes_similar_sample"], errors="coerce").fillna(0) < 5
            ]

            if not low_sample.empty:
                add_exception(
                    "LOW",
                    "Bayes",
                    "Low Bayes similar-sample count",
                    f"{len(low_sample)} rows have bayes_similar_sample under 5.",
                    "Treat these Bayes paths as lower confidence.",
                    len(low_sample),
                )

        if "is_starter" in ownership_df.columns:
            non_starters = ownership_df[
                pd.to_numeric(ownership_df["is_starter"], errors="coerce").fillna(0) == 0
            ]

            if not non_starters.empty:
                add_exception(
                    "MEDIUM",
                    "Starters",
                    "Ownership view includes non-starters",
                    f"{len(non_starters)} rows are marked is_starter = 0.",
                    "Confirm manual starters file and starter history logic.",
                    len(non_starters),
                )

    # ------------------------------------------------------------
    # Raw ownership / contest checks
    # ------------------------------------------------------------
    if raw_ownership_rows == 0:
        add_exception(
            "LOW",
            "Post-Contest",
            "No raw player ownership loaded",
            "No rows found in raw.dk_lol_player_ownership for this slate.",
            "After contest finishes, ingest contest standings and ownership files.",
            0,
        )

    if raw_contest_rows == 0:
        add_exception(
            "LOW",
            "Post-Contest",
            "No raw contest standings loaded",
            "No rows found in raw.dk_lol_contest_standings for this slate.",
            "After contest finishes, place contest standings zip in data\\contest-standings and run ingest.",
            0,
        )

    # ------------------------------------------------------------
    # Lineup file checks
    # ------------------------------------------------------------
    if lineup_file_count == 0:
        add_exception(
            "MEDIUM",
            "Lineups",
            "No generated lineup files found",
            "No lineup CSV files found for this selected slate.",
            "Open app_lol_lineup_builder.py and build at least one scenario.",
            0,
        )

    # ------------------------------------------------------------
    # If no exceptions
    # ------------------------------------------------------------
    if not exceptions:
        add_exception(
            "OK",
            "Slate",
            "No major exceptions detected",
            "The selected slate looks healthy based on current checks.",
            "Proceed to lineup building or contest review.",
            0,
        )

    out = pd.DataFrame(exceptions)

    severity_order = {
        "HIGH": 1,
        "MEDIUM": 2,
        "LOW": 3,
        "OK": 4,
    }

    out["severity_sort"] = out["severity"].map(severity_order).fillna(99)

    out = out.sort_values(
        ["severity_sort", "category", "issue"],
        ascending=[True, True, True],
    ).drop(columns=["severity_sort"])

    return out

# ============================================================
# Page: Slate Dashboard
# ============================================================

if page == "Slate Dashboard":
    st.subheader("Slate Dashboard")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        status_badge("Overall Status", overall_status)
    with c2:
        status_badge("DK Slate", "LOADED" if slate_rows > 0 else "MISSING")
    with c3:
        status_badge("Manual Starters", "READY" if manual_summary["starters"] > 0 else "NEEDS REVIEW")
    with c4:
        status_badge("Contest Results", "LOADED" if raw_contest_rows > 0 else "NO")

    st.divider()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Slate Rows", fmt_int(slate_rows))
    c2.metric("Teams", fmt_int(teams_count))
    c3.metric("Player Rows", fmt_int(player_rows))
    c4.metric("Team Rows", fmt_int(team_rows))
    c5.metric("Lineup Files", fmt_int(lineup_file_count))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Manual Rows", fmt_int(manual_summary["rows"]))
    c2.metric("Marked Starters", fmt_int(manual_summary["starters"]))
    c3.metric("Lane Rating Rows", fmt_int(lane_rows))
    c4.metric("Ownership Rows", fmt_int(ownership_rows))
    c5.metric("Raw Contest Rows", fmt_int(raw_contest_rows))

    st.divider()

    st.markdown("### Slate Player Table")
    st.dataframe(
        slate_players_df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# Page: Data Health
# ============================================================

elif page == "Data Health":
    st.subheader("Data Health")

    health_rows = [
        {
            "check": "DK slate loaded",
            "status": "OK" if slate_rows > 0 else "MISSING",
            "value": slate_rows,
            "note": "Rows from dbo.dk_lol_slate_player",
        },
        {
            "check": "Manual starters file exists",
            "status": "OK" if manual_summary["exists"] else "MISSING",
            "value": manual_summary["rows"],
            "note": str(MANUAL_STARTERS_PATH),
        },
        {
            "check": "Manual starters selected",
            "status": "OK" if manual_summary["starters"] > 0 else "NEEDS REVIEW",
            "value": manual_summary["starters"],
            "note": "is_starter = 1 count",
        },
        {
            "check": "Lane Power Signal available",
            "status": "OK" if lane_rows > 0 else "MISSING",
            "value": lane_rows,
            "note": "Rows from dbo.vw_lol_slate_lane_power_signal_live_v1",
        },
        {
            "check": "Ownership training available",
            "status": "OK" if ownership_rows > 0 else "MISSING",
            "value": ownership_rows,
            "note": "Rows from dbo.vw_lol_ownership_training",
        },
        {
            "check": "Bayes matched rows",
            "status": "OK" if matched_bayes_rows > 0 else "MISSING",
            "value": matched_bayes_rows,
            "note": "ownership rows with bayes_win_pct",
        },
        {
            "check": "Bayes missing rows",
            "status": "OK" if missing_bayes_rows == 0 else "CHECK",
            "value": missing_bayes_rows,
            "note": "ownership rows missing bayes_win_pct",
        },
        {
            "check": "Contest standings loaded",
            "status": "OK" if raw_contest_rows > 0 else "NO",
            "value": raw_contest_rows,
            "note": "Rows from raw.dk_lol_contest_standings",
        },
        {
            "check": "Raw player ownership loaded",
            "status": "OK" if raw_ownership_rows > 0 else "NO",
            "value": raw_ownership_rows,
            "note": "Rows from raw.dk_lol_player_ownership",
        },
        {
            "check": "Generated lineup files",
            "status": "OK" if lineup_file_count > 0 else "NO",
            "value": lineup_file_count,
            "note": str(LINEUPS_DIR),
        },
    ]

    health_df = pd.DataFrame(health_rows)

    st.dataframe(
        health_df,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.markdown("### File Counts")

    c1, c2, c3 = st.columns(3)
    c1.metric("Slate CSV Files", fmt_int(count_matching_files(SLATE_DIR, "dk_lol_*.csv")))
    c2.metric("Contest ZIP Files", fmt_int(count_matching_files(CONTEST_DIR, "contest-standings-*.zip")))
    c3.metric("Lineup CSV Files", fmt_int(count_matching_files(LINEUPS_DIR, "*.csv")))

# ============================================================
# Page: Exceptions
# ============================================================

elif page == "Exceptions":
    st.subheader("Exceptions")

    st.caption(
        "This page flags slate issues that need review before lineup building or post-contest analysis."
    )

    exceptions_df = build_exceptions(
        slate_players_df=slate_players_df,
        lane_df=lane_df,
        ownership_df=ownership_df,
        manual_summary=manual_summary,
        raw_contest_rows=raw_contest_rows,
        raw_ownership_rows=raw_ownership_rows,
        lineup_file_count=lineup_file_count,
        selected_slate_date=selected_slate_date,
        selected_slate_name=selected_slate_name,
    )

    if exceptions_df.empty:
        st.success("No exceptions found.")
    else:
        high_count = int((exceptions_df["severity"] == "HIGH").sum())
        medium_count = int((exceptions_df["severity"] == "MEDIUM").sum())
        low_count = int((exceptions_df["severity"] == "LOW").sum())
        ok_count = int((exceptions_df["severity"] == "OK").sum())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("High", high_count)
        c2.metric("Medium", medium_count)
        c3.metric("Low", low_count)
        c4.metric("OK", ok_count)

        severity_filter = st.multiselect(
            "Severity",
            options=["HIGH", "MEDIUM", "LOW", "OK"],
            default=["HIGH", "MEDIUM", "LOW", "OK"],
        )

        category_filter = st.multiselect(
            "Category",
            options=sorted(exceptions_df["category"].dropna().unique()),
            default=sorted(exceptions_df["category"].dropna().unique()),
        )

        view_df = exceptions_df.copy()

        if severity_filter:
            view_df = view_df[view_df["severity"].isin(severity_filter)]

        if category_filter:
            view_df = view_df[view_df["category"].isin(category_filter)]

        st.dataframe(
            view_df,
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        st.markdown("### Fix Order")

        if high_count > 0:
            st.error(
                "Fix HIGH exceptions first. These can break slate accuracy or lineup quality."
            )
        elif medium_count > 0:
            st.warning(
                "No HIGH exceptions found, but MEDIUM exceptions should be reviewed before building."
            )
        else:
            st.success(
                "No major build-blocking exceptions found."
            )

        st.markdown(
            """
            Recommended order:

            1. Fix missing slate or starter issues.
            2. Fix Bayes matching issues.
            3. Review ownership gaps.
            4. Build lineups.
            5. Load contest results after lock/contest completion.
            """
        )

    st.divider()

    st.markdown("### Detail: Missing Bayes Rows")

    if ownership_df.empty:
        st.info("No ownership/Bayes rows available for this slate.")
    elif "bayes_win_pct" not in ownership_df.columns:
        st.info("bayes_win_pct column not available.")
    else:
        missing_bayes_df = ownership_df[ownership_df["bayes_win_pct"].isna()].copy()

        if missing_bayes_df.empty:
            st.success("No missing Bayes rows.")
        else:
            cols = [
                "slate_date",
                "slate_name",
                "dk_player_name",
                "ownership_roster_position",
                "team_abbrev",
                "opponent_abbrev",
                "rating_team_name",
                "league",
                "position",
                "salary",
                "ownership_pct",
                "bayes_sample_type",
                "bayes_win_pct",
                "bayes_suggested_path",
                "team_strength_bucket",
                "opponent_strength_bucket",
                "salary_tier",
                "ownership_slot_type",
            ]
            cols = [c for c in cols if c in missing_bayes_df.columns]

            st.dataframe(
                missing_bayes_df[cols],
                use_container_width=True,
                hide_index=True,
            )

    st.divider()

    st.markdown("### Detail: Low Sample / Non-Starter Review")

    if ownership_df.empty:
        st.info("No ownership rows available.")
    else:
        review_df = ownership_df.copy()

        masks = []

        if "bayes_similar_sample" in review_df.columns:
            masks.append(
                pd.to_numeric(review_df["bayes_similar_sample"], errors="coerce").fillna(0) < 5
            )

        if "is_starter" in review_df.columns:
            masks.append(
                pd.to_numeric(review_df["is_starter"], errors="coerce").fillna(0) == 0
            )

        if masks:
            combined_mask = masks[0]
            for m in masks[1:]:
                combined_mask = combined_mask | m

            issue_df = review_df[combined_mask].copy()
        else:
            issue_df = pd.DataFrame()

        if issue_df.empty:
            st.success("No low-sample or non-starter rows found from ownership view.")
        else:
            cols = [
                "dk_player_name",
                "team_abbrev",
                "opponent_abbrev",
                "position",
                "salary",
                "ownership_pct",
                "starter_role",
                "is_starter",
                "actual_starter_flag",
                "bayes_sample_type",
                "bayes_similar_sample",
                "bayes_win_pct",
                "bayes_suggested_path",
            ]
            cols = [c for c in cols if c in issue_df.columns]

            st.dataframe(
                issue_df[cols],
                use_container_width=True,
                hide_index=True,
            )


# ============================================================
# Page: Starter Review
# ============================================================

elif page == "Starter Review":
    st.subheader("Starter Review")

    st.caption("This page reads your manual_starters.csv and compares it visually to the selected slate.")

    if not MANUAL_STARTERS_PATH.exists():
        st.warning(f"manual_starters.csv not found: {MANUAL_STARTERS_PATH}")
    else:
        manual_df = pd.read_csv(MANUAL_STARTERS_PATH)

        c1, c2, c3 = st.columns(3)
        c1.metric("Manual Rows", fmt_int(len(manual_df)))
        c2.metric(
            "Marked Starters",
            fmt_int(pd.to_numeric(manual_df.get("is_starter", 0), errors="coerce").fillna(0).sum()),
        )
        c3.metric(
            "Teams",
            fmt_int(manual_df["teamname"].nunique() if "teamname" in manual_df.columns else 0),
        )

        team_filter = st.multiselect(
            "Filter Team",
            options=sorted(manual_df["teamname"].dropna().unique()) if "teamname" in manual_df.columns else [],
        )

        view_df = manual_df.copy()
        if team_filter and "teamname" in view_df.columns:
            view_df = view_df[view_df["teamname"].isin(team_filter)]

        st.dataframe(
            view_df,
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    st.markdown("### Slate Players")
    st.dataframe(
        slate_players_df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# Page: Bayes Review
# ============================================================

elif page == "Bayes Review":
    st.subheader("Bayes Review")

    if ownership_df.empty:
        st.warning("No rows found in dbo.vw_lol_ownership_training for this slate.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rows", fmt_int(len(ownership_df)))
        c2.metric("Bayes Matched", fmt_int(matched_bayes_rows))
        c3.metric("Bayes Missing", fmt_int(missing_bayes_rows))

        avg_bayes = ownership_df["bayes_win_pct"].mean() if "bayes_win_pct" in ownership_df.columns else None
        c4.metric("Avg Bayes Win %", fmt_num(avg_bayes, 3))

        st.markdown("### Bayes by Team")
        if "team_abbrev" in ownership_df.columns:
            team_bayes = (
                ownership_df
                .groupby("team_abbrev", dropna=False)
                .agg(
                    rows=("dk_player_name", "count"),
                    avg_bayes_win_pct=("bayes_win_pct", "mean"),
                    missing_bayes=("bayes_win_pct", lambda s: int(s.isna().sum())),
                    suggested_winner=("suggested_winner_teamname", lambda s: ", ".join(sorted(set([str(x) for x in s.dropna()]))[:3])),
                    suggested_score=("suggested_match_score", lambda s: ", ".join(sorted(set([str(x) for x in s.dropna()]))[:3])),
                )
                .reset_index()
                .sort_values(["avg_bayes_win_pct", "team_abbrev"], ascending=[False, True])
            )

            st.dataframe(
                team_bayes,
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("### Player-Level Bayes / Ownership Table")
        cols = [
            "team_abbrev",
            "opponent_abbrev",
            "dk_player_name",
            "position",
            "salary",
            "ownership_pct",
            "avg_dk",
            "rating_score",
            "bayes_win_pct",
            "bayes_p_2_0",
            "bayes_p_2_1",
            "bayes_p_1_2",
            "bayes_p_0_2",
            "bayes_suggested_path",
            "suggested_winner_teamname",
            "suggested_match_score",
            "team_strength_bucket",
            "opponent_strength_bucket",
            "strength_matchup_bucket",
        ]
        cols = [c for c in cols if c in ownership_df.columns]

        st.dataframe(
            ownership_df[cols],
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    st.markdown("### Recent Bayes Backtest")
    backtest_df = safe_query(
        """
        SELECT TOP 500
            target_series_date,
            league,
            team_a,
            team_b,
            predicted_winner_teamname,
            predicted_match_score,
            predicted_winner_bayes_win_pct,
            prediction_sample_type,
            prediction_similar_sample,
            actual_winner_teamname,
            actual_match_score,
            match_winner_correct,
            match_score_correct,
            match_confidence_label,
            dfs_note
        FROM dbo.vw_lol_bayes_prediction_backtest_match_level
        ORDER BY target_series_date DESC, league, team_a, team_b;
        """
    )

    if not backtest_df.empty:
        c1, c2, c3 = st.columns(3)

        winner_acc = backtest_df["match_winner_correct"].mean() if "match_winner_correct" in backtest_df.columns else None
        score_acc = backtest_df["match_score_correct"].mean() if "match_score_correct" in backtest_df.columns else None

        c1.metric("Backtest Rows", fmt_int(len(backtest_df)))
        c2.metric("Winner Accuracy", fmt_pct(winner_acc))
        c3.metric("Score Accuracy", fmt_pct(score_acc))

        st.dataframe(
            backtest_df,
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No Bayes backtest rows found.")


# ============================================================
# Page: Ownership Review
# ============================================================

elif page == "Ownership Review":
    st.subheader("Ownership Review")

    if ownership_df.empty:
        st.warning("No ownership training rows found for this slate.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ownership Rows", fmt_int(len(ownership_df)))
        c2.metric("Avg Ownership", fmt_num(ownership_df["ownership_pct"].mean(), 2))
        c3.metric("Max Ownership", fmt_num(ownership_df["ownership_pct"].max(), 2))
        c4.metric("Players", fmt_int(ownership_df["dk_player_name"].nunique()))

        st.markdown("### Ownership by Team")
        team_own = (
            ownership_df
            .groupby("team_abbrev", dropna=False)
            .agg(
                rows=("dk_player_name", "count"),
                avg_ownership=("ownership_pct", "mean"),
                max_ownership=("ownership_pct", "max"),
                avg_salary=("salary", "mean"),
                avg_rating=("rating_score", "mean"),
                avg_bayes=("bayes_win_pct", "mean"),
            )
            .reset_index()
            .sort_values("avg_ownership", ascending=False)
        )

        st.dataframe(
            team_own,
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("### Player Ownership Detail")
        cols = [
            "team_abbrev",
            "opponent_abbrev",
            "dk_player_name",
            "ownership_roster_position",
            "ownership_slot_type",
            "position",
            "salary",
            "ownership_pct",
            "actual_fp",
            "avg_dk",
            "rating_score",
            "dk_value",
            "starter_role",
            "is_starter",
            "bayes_win_pct",
            "bayes_suggested_path",
            "salary_tier",
        ]
        cols = [c for c in cols if c in ownership_df.columns]

        st.dataframe(
            ownership_df[cols],
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# Page: Contest Review
# ============================================================

elif page == "Contest Review":
    st.subheader("Contest Review")

    contest_df = safe_query(
        """
        SELECT
            slate_date,
            slate_name,
            contest_id,
            lineups,
            best_rank,
            worst_rank,
            winning_score,
            avg_score
        FROM lol.vw_contest_summary
        WHERE slate_date = ?
          AND slate_name = ?
        ORDER BY contest_id;
        """,
        params=[selected_slate_date, selected_slate_name],
    )

    bucket_df = safe_query(
        """
        SELECT
            slate_date,
            slate_name,
            contest_id,
            finish_bucket,
            lineups,
            avg_points,
            avg_total_ownership,
            avg_player_ownership,
            avg_salary_left
        FROM lol.vw_finish_bucket_summary
        WHERE slate_date = ?
          AND slate_name = ?
        ORDER BY contest_id, finish_bucket;
        """,
        params=[selected_slate_date, selected_slate_name],
    )

    if contest_df.empty:
        st.warning("No contest summary found for this slate.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Contests", fmt_int(contest_df["contest_id"].nunique()))
        c2.metric("Lineups", fmt_int(contest_df["lineups"].sum()))
        c3.metric("Best Rank", fmt_int(contest_df["best_rank"].min()))
        c4.metric("Winning Score", fmt_num(contest_df["winning_score"].max(), 2))

        st.markdown("### Contest Summary")
        st.dataframe(
            contest_df,
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    st.markdown("### Finish Bucket Summary")
    if bucket_df.empty:
        st.info("No finish bucket summary found.")
    else:
        st.dataframe(
            bucket_df,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# Page: Top 1% Lineups
# ============================================================

elif page == "Top 1% Lineups":
    st.subheader("Top 1% Lineups")

    top_df = safe_query(
        """
        SELECT TOP 200
            slate_date,
            slate_name,
            contest_id,
            rank_num,
            points,
            captain_player,
            captain_team,
            captain_position,
            stack_structure,
            team_stack_summary,
            total_ownership,
            avg_ownership,
            salary_left,
            lineup_raw
        FROM lol.vw_top_1pct_lineups
        WHERE slate_date = ?
          AND slate_name = ?
        ORDER BY rank_num ASC, points DESC;
        """,
        params=[selected_slate_date, selected_slate_name],
    )

    if top_df.empty:
        st.warning("No top 1% lineup rows found for this slate.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Rows", fmt_int(len(top_df)))
        c2.metric("Best Score", fmt_num(top_df["points"].max(), 2))
        c3.metric("Avg Ownership", fmt_num(top_df["avg_ownership"].mean(), 2))
        c4.metric("Avg Salary Left", fmt_num(top_df["salary_left"].mean(), 0))

        st.markdown("### Captain Position Summary")
        cap_summary = (
            top_df
            .groupby("captain_position", dropna=False)
            .agg(
                lineups=("rank_num", "count"),
                avg_points=("points", "mean"),
                avg_total_ownership=("total_ownership", "mean"),
                avg_salary_left=("salary_left", "mean"),
            )
            .reset_index()
            .sort_values("lineups", ascending=False)
        )

        st.dataframe(
            cap_summary,
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("### Top 1% Lineup Detail")
        st.dataframe(
            top_df,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# Page: Daily Commands
# ============================================================

elif page == "Daily Commands":
    st.subheader("Daily Commands")

    st.caption(
        "Run controlled LoL pipeline jobs through the Action Engine. "
        "The Command Center calls engine.jobs.run_job(); the engine decides whether to run Python, SQL, or validation checks."
    )

    # ------------------------------------------------------------
    # Action Engine Jobs
    # ------------------------------------------------------------
    try:
        jobs = list_jobs()
    except Exception as e:
        st.error(f"Could not load Action Engine jobs: {e}")
        jobs = []

    if not jobs:
        st.warning("No Action Engine jobs are currently registered in engine/jobs.py.")
    else:
        job_map = {j.job_id: j for j in jobs}

        def job_group(job):
            label = f"{job.job_id} {job.label} {job.description}".lower()

            if any(x in label for x in ["check", "health", "validation", "missing", "gap"]):
                return "Validation / Health Checks"

            if any(x in label for x in ["contest", "ownership", "top 1%", "standings"]):
                return "Post-Contest Review"

            if any(x in label for x in ["bayes", "view", "backtest", "refresh"]):
                return "Model / SQL Refresh"

            if any(x in label for x in ["slate", "starter", "playbook", "ingest"]):
                return "Slate Prep"

            return "Other Jobs"

        job_table = pd.DataFrame(
            [
                {
                    "group": job_group(j),
                    "job_id": j.job_id,
                    "label": j.label,
                    "job_type": j.job_type,
                    "target": j.target,
                    "timeout_seconds": j.timeout_seconds,
                    "description": j.description,
                }
                for j in jobs
            ]
        )

        st.markdown("### Registered Action Engine Jobs")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Registered Jobs", fmt_int(len(job_table)))
        c2.metric("Python Jobs", fmt_int((job_table["job_type"] == "python").sum()))
        c3.metric("SQL File Jobs", fmt_int((job_table["job_type"] == "sql_file").sum()))
        c4.metric("SQL Query Jobs", fmt_int((job_table["job_type"] == "sql_query").sum()))

        group_options = ["All"] + sorted(job_table["group"].dropna().unique().tolist())
        selected_group = st.selectbox("Job Group", options=group_options)

        view_jobs_df = job_table.copy()
        if selected_group != "All":
            view_jobs_df = view_jobs_df[view_jobs_df["group"] == selected_group]

        st.dataframe(
            view_jobs_df[["group", "job_id", "label", "job_type", "timeout_seconds", "description"]],
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.markdown("### Run Action Engine Job")

        available_job_ids = view_jobs_df["job_id"].tolist()

        selected_job_id = st.selectbox(
            "Select Job",
            options=available_job_ids,
            format_func=lambda job_id: f"{job_map[job_id].label}  ({job_id})",
        )

        selected_job = job_map[selected_job_id]

        c1, c2 = st.columns([2, 1])

        with c1:
            st.markdown(f"**{selected_job.label}**")
            if selected_job.description:
                st.write(selected_job.description)

            st.write("**Job ID:**", selected_job.job_id)
            st.write("**Job Type:**", selected_job.job_type)
            st.write("**Target:**", selected_job.target)

        with c2:
            st.metric("Timeout", f"{selected_job.timeout_seconds}s")
            st.metric("Selected Slate", f"{selected_slate_date}")
            st.caption(str(selected_slate_name))

        st.info(
            "First milestone: run one controlled job at a time and show stdout/stderr. "
            "Later we can add saved run history, chained workflows, and per-slate arguments."
        )

        run_clicked = st.button(
            "Run Selected Job",
            type="primary",
            use_container_width=True,
        )

        if run_clicked:
            st.cache_data.clear()

            with st.spinner(f"Running {selected_job.label}..."):
                result = run_job(selected_job_id)

            st.divider()
            st.markdown("### Engine Result")

            if result.success:
                st.success(f"Job succeeded in {result.duration_seconds} seconds.")
            else:
                st.error(
                    f"Job failed. Return code: {result.return_code}. "
                    f"Duration: {result.duration_seconds} seconds."
                )

            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Success", "YES" if result.success else "NO")
            r2.metric("Return Code", result.return_code)
            r3.metric("Duration", f"{result.duration_seconds}s")
            r4.metric("Job ID", result.job_id)

            st.markdown("#### Command")
            st.code(" ".join(result.command), language="powershell")

            st.markdown("#### Result Metadata")
            st.json(
                {
                    "job_id": result.job_id,
                    "success": result.success,
                    "return_code": result.return_code,
                    "duration_seconds": result.duration_seconds,
                    "started_at": result.started_at,
                    "finished_at": result.finished_at,
                }
            )

            with st.expander("stdout", expanded=result.success):
                st.code(result.stdout if result.stdout else "(empty)")

            with st.expander("stderr", expanded=not result.success):
                st.code(result.stderr if result.stderr else "(empty)")

            st.caption(
                "After a successful job, use the sidebar Refresh Data button if the dashboard metrics do not update immediately."
            )

    # ------------------------------------------------------------
    # Manual checklist kept as reference only
    # ------------------------------------------------------------
    st.divider()
    st.markdown("### Manual Command Reference")
    st.caption("This is kept as a reference. Prefer running registered jobs through the Action Engine above.")

    with st.expander("Daily Slate Prep - Manual Commands"):
        st.code(
            r"""
cd C:\DailyDFS\LoL
.\.venv\Scripts\Activate.ps1

python .\scripts\ingest_dk_lol_slate.py
python .\scripts\build_manual_starters_from_dk.py
notepad .\data\manual_starters.csv

python .\scripts\ingest_oracle_elixir.py

python .\scripts\build_player_games.py
python .\scripts\build_lol_team_game_stats.py
python .\scripts\build_lol_team_series_results.py
python .\scripts\build_lol_team_series_profiles.py
python .\scripts\build_lane_matchups.py
python .\scripts\build_player_lane_matchups.py
python .\scripts\build_player_lane_ratings.py

python .\scripts\build_lol_playbook.py

python -m streamlit run .\app_lol_command_center.py
""".strip(),
            language="powershell",
        )

    with st.expander("Open Lineup Builder - Manual Commands"):
        st.code(
            r"""
cd C:\DailyDFS\LoL
.\.venv\Scripts\Activate.ps1

python -m streamlit run .\app_lol_lineup_builder.py
""".strip(),
            language="powershell",
        )

    with st.expander("Post-Contest Review - Manual Commands"):
        st.code(
            r"""
cd C:\DailyDFS\LoL
.\.venv\Scripts\Activate.ps1

python .\scripts\ingest_dk_lol_contest_standings.py
python .\scripts\transform_dk_lol_lineups.py
python .\scripts\enrich_dk_lol_lineups_from_slate.py

sqlcmd -S "DESKTOP-I9OLS14\SQLEXPRESS" -d "lol_esports" -E -C -i ".\sql\18_populate_lol_bayes_prediction_backtest.sql"

python -m streamlit run .\app_lol_command_center.py
""".strip(),
            language="powershell",
        )
