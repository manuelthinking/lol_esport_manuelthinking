import os
import pandas as pd
import pyodbc
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="LoL Player Matchups", layout="wide")


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


@st.cache_data(ttl=300)
def query_df(sql, params=None):
    conn = get_conn()
    try:
        return pd.read_sql(sql, conn, params=params)
    finally:
        conn.close()


st.title("LoL Player Matchup Reports")

positions = query_df("""
    SELECT DISTINCT position
    FROM dbo.fact_lol_player_lane_matchup
    WHERE position IS NOT NULL
    ORDER BY position;
""")

position_options = ["All"] + positions["position"].tolist()
position = st.sidebar.selectbox("Position", position_options)

position_filter = ""
position_params = []

if position != "All":
    position_filter = " AND position = ? "
    position_params.append(position)


players = query_df(f"""
    SELECT DISTINCT player_name
    FROM dbo.fact_lol_player_lane_matchup
    WHERE player_name IS NOT NULL
    {position_filter}
    ORDER BY player_name;
""", position_params)

player_options = players["player_name"].tolist()

if not player_options:
    st.warning("No players found.")
    st.stop()

player_a = st.sidebar.selectbox("Player A", player_options)

player_b = st.sidebar.selectbox(
    "Player B / Comparison Player",
    player_options,
    index=1 if len(player_options) > 1 else 0
)

opponents = query_df(f"""
    SELECT DISTINCT opponent_player
    FROM dbo.fact_lol_player_lane_matchup
    WHERE opponent_player IS NOT NULL
    {position_filter}
    ORDER BY opponent_player;
""", position_params)

opponent_options = opponents["opponent_player"].tolist()
selected_opponent = st.sidebar.selectbox("Common Opponent", opponent_options)

min_games = st.sidebar.slider("Minimum Games", 1, 20, 3)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Direct H2H",
    "Common Opponent Compare",
    "Best vs Opponent",
    "Champion Matchups",
    "Lane Ratings"
])

with tab1:
    st.subheader(f"Direct H2H: {player_a} vs {player_b}")

    h2h_position_filter = ""
    h2h_params = [player_a, player_b, player_b, player_a]

    if position != "All":
        h2h_position_filter = " AND position = ? "
        h2h_params.append(position)

    h2h = query_df(f"""
        SELECT
            player_name,
            opponent_player,
            COUNT(*) AS games,
            AVG(dk_points) AS avg_dk_points,
            AVG(dk_edge) AS avg_dk_edge,
            AVG(kills) AS avg_kills,
            AVG(deaths) AS avg_deaths,
            AVG(assists) AS avg_assists,
            AVG(gold_diff_10) AS avg_gold_diff_10,
            AVG(xp_diff_10) AS avg_xp_diff_10,
            AVG(cs_diff_10) AS avg_cs_diff_10,
            AVG(dpm) AS avg_dpm,
            AVG(damage_share) AS avg_damage_share,
            AVG(vision_score) AS avg_vision_score
        FROM dbo.fact_lol_player_lane_matchup
        WHERE (
                (player_name = ? AND opponent_player = ?)
                OR
                (player_name = ? AND opponent_player = ?)
              )
          {h2h_position_filter}
        GROUP BY player_name, opponent_player
        ORDER BY avg_dk_points DESC;
    """, h2h_params)

    st.dataframe(h2h, use_container_width=True)

with tab2:
    st.subheader(f"{player_a} vs {player_b} against common opponent: {selected_opponent}")

    common_position_filter = ""
    common_params = [selected_opponent, player_a, player_b]

    if position != "All":
        common_position_filter = " AND position = ? "
        common_params.append(position)

    common = query_df(f"""
        SELECT
            player_name,
            opponent_player,
            COUNT(*) AS games,
            AVG(dk_points) AS avg_dk_points,
            AVG(dk_edge) AS avg_dk_edge,
            AVG(kills) AS avg_kills,
            AVG(deaths) AS avg_deaths,
            AVG(assists) AS avg_assists,
            AVG(gold_diff_10) AS avg_gold_diff_10,
            AVG(xp_diff_10) AS avg_xp_diff_10,
            AVG(cs_diff_10) AS avg_cs_diff_10,
            AVG(dpm) AS avg_dpm,
            AVG(damage_share) AS avg_damage_share
        FROM dbo.fact_lol_player_lane_matchup
        WHERE opponent_player = ?
          AND player_name IN (?, ?)
          {common_position_filter}
        GROUP BY player_name, opponent_player
        ORDER BY avg_dk_points DESC;
    """, common_params)

    st.dataframe(common, use_container_width=True)

with tab3:
    st.subheader(f"Best performers vs {selected_opponent}")

    best_position_filter = ""
    best_params = [selected_opponent, min_games]

    if position != "All":
        best_position_filter = " AND position = ? "
        best_params.insert(1, position)

    best = query_df(f"""
        SELECT
            player_name,
            COUNT(*) AS games,
            AVG(dk_points) AS avg_dk_points,
            AVG(dk_edge) AS avg_dk_edge,
            AVG(gold_diff_10) AS avg_gold_diff_10,
            AVG(xp_diff_10) AS avg_xp_diff_10,
            AVG(cs_diff_10) AS avg_cs_diff_10,
            AVG(dpm) AS avg_dpm,
            AVG(damage_share) AS avg_damage_share
        FROM dbo.fact_lol_player_lane_matchup
        WHERE opponent_player = ?
          {best_position_filter}
        GROUP BY player_name
        HAVING COUNT(*) >= ?
        ORDER BY avg_dk_points DESC;
    """, best_params)

    st.dataframe(best, use_container_width=True)

with tab4:
    st.subheader("Champion matchup history")

    champ_data = query_df(f"""
        SELECT DISTINCT champion
        FROM dbo.fact_lol_player_lane_matchup
        WHERE player_name = ?
        {position_filter}
        ORDER BY champion;
    """, [player_a] + position_params)

    opp_champ_data = query_df(f"""
        SELECT DISTINCT opponent_champion
        FROM dbo.fact_lol_player_lane_matchup
        WHERE opponent_player = ?
        {position_filter}
        ORDER BY opponent_champion;
    """, [player_b] + position_params)

    col1, col2 = st.columns(2)

    champ = col1.selectbox(
        f"{player_a} Champion",
        champ_data["champion"].dropna().tolist()
    )

    opp_champ = col2.selectbox(
        f"{player_b} Champion",
        opp_champ_data["opponent_champion"].dropna().tolist()
    )

    champ_position_filter = ""
    champ_params = [player_a, champ, player_b, opp_champ]

    if position != "All":
        champ_position_filter = " AND position = ? "
        champ_params.append(position)

    champ_report = query_df(f"""
        SELECT
            player_name,
            champion,
            opponent_player,
            opponent_champion,
            COUNT(*) AS games,
            AVG(dk_points) AS avg_dk_points,
            AVG(dk_edge) AS avg_dk_edge,
            AVG(gold_diff_10) AS avg_gold_diff_10,
            AVG(xp_diff_10) AS avg_xp_diff_10,
            AVG(cs_diff_10) AS avg_cs_diff_10,
            AVG(dpm) AS avg_dpm,
            AVG(damage_share) AS avg_damage_share
        FROM dbo.fact_lol_player_lane_matchup
        WHERE player_name = ?
          AND champion = ?
          AND opponent_player = ?
          AND opponent_champion = ?
          {champ_position_filter}
        GROUP BY
            player_name,
            champion,
            opponent_player,
            opponent_champion;
    """, champ_params)

    st.dataframe(champ_report, use_container_width=True)

with tab5:
    st.subheader("Lane dominance ratings")

    ratings_position_filter = ""
    ratings_params = [min_games]

    if position != "All":
        ratings_position_filter = " WHERE position = ? "
        ratings_params.insert(0, position)

    ratings = query_df(f"""
        SELECT
            position,
            player_name,
            COUNT(*) AS games,
            AVG(dk_points) AS avg_dk_points,
            AVG(dk_edge) AS avg_dk_edge,
            AVG(gold_diff_10) AS avg_gold_diff_10,
            AVG(xp_diff_10) AS avg_xp_diff_10,
            AVG(cs_diff_10) AS avg_cs_diff_10,
            AVG(dpm) AS avg_dpm,
            AVG(damage_share) AS avg_damage_share,
            AVG(vision_score) AS avg_vision_score
        FROM dbo.fact_lol_player_lane_matchup
        {ratings_position_filter}
        GROUP BY position, player_name
        HAVING COUNT(*) >= ?
        ORDER BY avg_dk_edge DESC;
    """, ratings_params)

    st.dataframe(ratings, use_container_width=True)