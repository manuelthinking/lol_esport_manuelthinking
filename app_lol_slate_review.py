import os
import pandas as pd
import pyodbc
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="LoL Slate Review",
    layout="wide"
)


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


st.title("LoL DraftKings Slate Review")

slates = query_df("""
    SELECT DISTINCT
        slate_date,
        slate_name
    FROM lol.dim_slate
    ORDER BY slate_date DESC, slate_name;
""")

if slates.empty:
    st.warning("No slates found.")
    st.stop()

slates["label"] = slates["slate_date"].astype(str) + " | " + slates["slate_name"]

selected_label = st.sidebar.selectbox("Slate", slates["label"].tolist())
selected = slates[slates["label"] == selected_label].iloc[0]

slate_date = str(selected["slate_date"])
slate_name = selected["slate_name"]

contests = query_df("""
    SELECT DISTINCT contest_id
    FROM lol.fact_lineup_result lr
    JOIN lol.dim_slate ds
        ON lr.slate_id = ds.slate_id
    WHERE ds.slate_date = ?
      AND ds.slate_name = ?
    ORDER BY contest_id;
""", [slate_date, slate_name])

contest_options = ["All"] + contests["contest_id"].astype(str).tolist()
contest_id = st.sidebar.selectbox("Contest", contest_options)

contest_filter = ""
params = [slate_date, slate_name]

if contest_id != "All":
    contest_filter = " AND lr.contest_id = ? "
    params.append(contest_id)


summary = query_df(f"""
    SELECT
        ds.slate_date,
        ds.slate_name,
        lr.contest_id,
        COUNT(*) AS lineups,
        MIN(lr.rank_num) AS best_rank,
        MAX(lr.rank_num) AS worst_rank,
        MAX(lr.points) AS winning_score,
        AVG(lr.points) AS avg_score,
        AVG(lr.total_ownership) AS avg_total_ownership,
        AVG(lr.salary_left) AS avg_salary_left
    FROM lol.fact_lineup_result lr
    JOIN lol.dim_slate ds
        ON lr.slate_id = ds.slate_id
    WHERE ds.slate_date = ?
      AND ds.slate_name = ?
      {contest_filter}
    GROUP BY ds.slate_date, ds.slate_name, lr.contest_id
    ORDER BY lr.contest_id;
""", params)

st.subheader(f"{slate_date} — {slate_name}")

if summary.empty:
    st.warning("No lineup results found for this slate/filter.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)

c1.metric("Lineups", f"{int(summary['lineups'].sum()):,}")
c2.metric("Best Score", f"{summary['winning_score'].max():.2f}")
c3.metric("Avg Ownership", f"{summary['avg_total_ownership'].mean():.1f}%")
c4.metric("Avg Salary Left", f"${summary['avg_salary_left'].mean():.0f}")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Contest Summary",
    "Finish Buckets",
    "Captain Trends",
    "Stack Trends",
    "Top Lineups",
    "Player Appearances"
])

with tab1:
    st.dataframe(summary, use_container_width=True)

with tab2:
    bucket_params = [slate_date, slate_name]
    bucket_contest_filter = ""

    if contest_id != "All":
        bucket_contest_filter = " AND contest_id = ? "
        bucket_params.append(contest_id)

    buckets = query_df(f"""
        SELECT
            finish_bucket,
            SUM(lineups) AS lineups,
            AVG(avg_points) AS avg_points,
            AVG(avg_total_ownership) AS avg_total_ownership,
            AVG(avg_player_ownership) AS avg_player_ownership,
            AVG(avg_salary_left) AS avg_salary_left
        FROM lol.vw_finish_bucket_summary
        WHERE slate_date = ?
          AND slate_name = ?
          {bucket_contest_filter}
        GROUP BY finish_bucket
        ORDER BY
            CASE finish_bucket
                WHEN 'Top 0.1%' THEN 1
                WHEN 'Top 1%' THEN 2
                WHEN 'Top 5%' THEN 3
                WHEN 'Top 20%' THEN 4
                ELSE 5
            END;
    """, bucket_params)

    st.dataframe(buckets, use_container_width=True)

    if not buckets.empty:
        st.bar_chart(
            buckets.set_index("finish_bucket")[["avg_total_ownership", "avg_salary_left"]]
        )

with tab3:
    captain_params = [slate_date, slate_name]
    captain_contest_filter = ""

    if contest_id != "All":
        captain_contest_filter = " AND contest_id = ? "
        captain_params.append(contest_id)

    captains = query_df(f"""
        SELECT
            captain_position,
            COUNT(*) AS top_1pct_lineups,
            AVG(points) AS avg_points,
            AVG(total_ownership) AS avg_total_ownership,
            AVG(salary_left) AS avg_salary_left
        FROM lol.vw_top_1pct_lineups
        WHERE slate_date = ?
          AND slate_name = ?
          {captain_contest_filter}
        GROUP BY captain_position
        ORDER BY top_1pct_lineups DESC;
    """, captain_params)

    st.dataframe(captains, use_container_width=True)

    if not captains.empty:
        st.bar_chart(captains.set_index("captain_position")["top_1pct_lineups"])

with tab4:
    stack_params = [slate_date, slate_name]
    stack_contest_filter = ""

    if contest_id != "All":
        stack_contest_filter = " AND contest_id = ? "
        stack_params.append(contest_id)

    stacks = query_df(f"""
        SELECT
            stack_structure,
            COUNT(*) AS top_1pct_lineups,
            AVG(points) AS avg_points,
            AVG(total_ownership) AS avg_total_ownership,
            AVG(salary_left) AS avg_salary_left
        FROM lol.vw_top_1pct_lineups
        WHERE slate_date = ?
          AND slate_name = ?
          {stack_contest_filter}
        GROUP BY stack_structure
        ORDER BY top_1pct_lineups DESC;
    """, stack_params)

    st.dataframe(stacks, use_container_width=True)

    if not stacks.empty:
        st.bar_chart(stacks.set_index("stack_structure")["top_1pct_lineups"])

with tab5:
    top_params = [slate_date, slate_name]
    top_contest_filter = ""

    if contest_id != "All":
        top_contest_filter = " AND contest_id = ? "
        top_params.append(contest_id)

    top_lineups = query_df(f"""
        SELECT TOP 200
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
          {top_contest_filter}
        ORDER BY contest_id, rank_num, points DESC;
    """, top_params)

    st.dataframe(top_lineups, use_container_width=True)

with tab6:
    player_params = [slate_date, slate_name]
    player_contest_filter = ""

    if contest_id != "All":
        player_contest_filter = " AND lr.contest_id = ? "
        player_params.append(contest_id)

    players = query_df(f"""
        WITH ranked AS (
            SELECT
                lr.lineup_result_id,
                lr.contest_id,
                lr.rank_num,
                COUNT(*) OVER (PARTITION BY lr.contest_id) AS field_size
            FROM lol.fact_lineup_result lr
            JOIN lol.dim_slate ds
                ON lr.slate_id = ds.slate_id
            WHERE ds.slate_date = ?
              AND ds.slate_name = ?
              {player_contest_filter}
        )
        SELECT
            lp.roster_slot,
            lp.actual_position,
            lp.player_name,
            lp.team,
            COUNT(*) AS top_1pct_appearances,
            AVG(lp.ownership_pct) AS avg_ownership,
            AVG(lp.actual_fp) AS avg_actual_fp,
            AVG(lp.salary) AS avg_salary
        FROM ranked r
        JOIN lol.fact_lineup_player lp
            ON r.lineup_result_id = lp.lineup_result_id
        WHERE r.rank_num <= CEILING(r.field_size * 0.01)
        GROUP BY
            lp.roster_slot,
            lp.actual_position,
            lp.player_name,
            lp.team
        ORDER BY top_1pct_appearances DESC, avg_actual_fp DESC;
    """, player_params)

    st.dataframe(players, use_container_width=True)