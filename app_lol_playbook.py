import os
from pathlib import Path

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="LoL Slate Playbook",
    layout="wide",
)


BASE_DIR = Path(r"C:\DailyDFS\LoL")


POSSIBLE_PLAYBOOK_FILES = [
    BASE_DIR / "data" / "outputs" / "lol_playbook.csv",
    BASE_DIR / "data" / "processed" / "lol_playbook.csv",
    BASE_DIR / "output" / "lol_playbook.csv",
    BASE_DIR / "lol_playbook.csv",
]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df


def find_first_existing_file():
    for path in POSSIBLE_PLAYBOOK_FILES:
        if path.exists():
            return path
    return None


@st.cache_data
def load_playbook(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = normalize_columns(df)
    return df


def pick_col(df, options):
    for col in options:
        if col in df.columns:
            return col
    return None


def build_team_overview(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()

    team_col = pick_col(d, ["team", "team_abbr", "dk_team", "org"])
    opp_col = pick_col(d, ["opp", "opponent", "opponent_team", "vs"])
    player_col = pick_col(d, ["player_name", "name", "player"])
    pos_col = pick_col(d, ["position", "pos", "roster_position"])
    salary_col = pick_col(d, ["salary", "dk_salary"])
    proj_col = pick_col(d, ["projection", "proj", "projected_points", "dk_projection", "median_projection"])
    value_col = pick_col(d, ["value", "points_per_1k", "proj_per_1k", "value_score"])
    starter_col = pick_col(d, ["is_starter", "starter", "starting"])

    required = {
        "team": team_col,
        "player": player_col,
        "projection": proj_col,
        "salary": salary_col,
    }

    missing = [k for k, v in required.items() if v is None]
    if missing:
        st.error(f"Missing required columns for Team Overview: {missing}")
        st.write("Available columns:", list(d.columns))
        return pd.DataFrame()

    if opp_col is None:
        d["opp_placeholder"] = ""
        opp_col = "opp_placeholder"

    if value_col is None:
        d["value_calc"] = d[proj_col] / (d[salary_col] / 1000)
        value_col = "value_calc"

    if starter_col is None:
        d["starter_calc"] = 1
        starter_col = "starter_calc"

    d[proj_col] = pd.to_numeric(d[proj_col], errors="coerce").fillna(0)
    d[salary_col] = pd.to_numeric(d[salary_col], errors="coerce").fillna(0)
    d[value_col] = pd.to_numeric(d[value_col], errors="coerce").fillna(0)

    if starter_col in d.columns:
        if d[starter_col].dtype == object:
            d[starter_col] = (
                d[starter_col]
                .astype(str)
                .str.lower()
                .isin(["1", "true", "yes", "y", "starter", "starting"])
                .astype(int)
            )
        else:
            d[starter_col] = pd.to_numeric(d[starter_col], errors="coerce").fillna(0)

    team_df = (
        d.groupby([team_col, opp_col], dropna=False)
        .agg(
            players=(player_col, "count"),
            starters=(starter_col, "sum"),
            total_projection=(proj_col, "sum"),
            avg_projection=(proj_col, "mean"),
            total_salary=(salary_col, "sum"),
            avg_salary=(salary_col, "mean"),
            avg_value=(value_col, "mean"),
        )
        .reset_index()
    )

    top_players = (
        d.sort_values(proj_col, ascending=False)
        .groupby(team_col)
        .head(1)
    )

    keep_cols = [team_col, player_col, proj_col, salary_col]
    if pos_col:
        keep_cols.append(pos_col)

    top_players = top_players[keep_cols].copy()

    rename_map = {
        player_col: "top_player",
        proj_col: "top_player_proj",
        salary_col: "top_player_salary",
    }

    if pos_col:
        rename_map[pos_col] = "top_player_pos"

    top_players = top_players.rename(columns=rename_map)

    team_df = team_df.merge(top_players, on=team_col, how="left")

    team_df["proj_per_1k_salary"] = team_df.apply(
        lambda r: r["total_projection"] / (r["total_salary"] / 1000)
        if r["total_salary"] else 0,
        axis=1,
    )

    team_df = team_df.rename(columns={
        team_col: "team",
        opp_col: "opp",
    })

    display_cols = [
        "team",
        "opp",
        "players",
        "starters",
        "total_projection",
        "avg_projection",
        "total_salary",
        "avg_salary",
        "avg_value",
        "proj_per_1k_salary",
        "top_player",
        "top_player_pos" if "top_player_pos" in team_df.columns else None,
        "top_player_proj",
        "top_player_salary",
    ]

    display_cols = [c for c in display_cols if c and c in team_df.columns]

    team_df = team_df[display_cols].sort_values(
        ["total_projection", "proj_per_1k_salary"],
        ascending=False,
    )

    return team_df


def format_team_df(team_df: pd.DataFrame) -> pd.DataFrame:
    d = team_df.copy()

    for col in [
        "total_projection",
        "avg_projection",
        "avg_value",
        "proj_per_1k_salary",
        "top_player_proj",
    ]:
        if col in d.columns:
            d[col] = d[col].round(2)

    for col in ["total_salary", "avg_salary", "top_player_salary"]:
        if col in d.columns:
            d[col] = d[col].round(0).astype(int)

    return d


st.title("LoL Slate Playbook")

st.sidebar.header("Data Source")

default_file = find_first_existing_file()

uploaded_file = st.sidebar.file_uploader(
    "Upload playbook CSV",
    type=["csv"],
)

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    df = normalize_columns(df)
    source_label = "Uploaded CSV"
elif default_file:
    df = load_playbook(str(default_file))
    source_label = str(default_file)
else:
    st.error("No playbook CSV found. Upload a CSV or check your output path.")
    st.stop()

st.sidebar.success(f"Loaded: {source_label}")

st.sidebar.write("Rows:", len(df))
st.sidebar.write("Columns:", len(df.columns))

tab1, tab2, tab3 = st.tabs([
    "Player Playbook",
    "Team Overview",
    "Raw Data",
])


with tab1:
    st.header("Player Playbook")

    search = st.text_input("Search player/team", "")

    view_df = df.copy()

    if search:
        search_lower = search.lower()
        mask = pd.Series(False, index=view_df.index)

        for col in view_df.columns:
            if view_df[col].dtype == object:
                mask = mask | view_df[col].astype(str).str.lower().str.contains(search_lower, na=False)

        view_df = view_df[mask]

    st.dataframe(
        view_df,
        use_container_width=True,
        hide_index=True,
    )


with tab2:
    st.header("Team Slate Overview")

    team_df = build_team_overview(df)

    if not team_df.empty:
        team_df = format_team_df(team_df)

        sort_options = [
            c for c in [
                "total_projection",
                "proj_per_1k_salary",
                "avg_value",
                "avg_projection",
                "total_salary",
            ]
            if c in team_df.columns
        ]

        sort_by = st.selectbox(
            "Sort teams by",
            sort_options,
            index=0,
        )

        ascending = False
        team_df = team_df.sort_values(sort_by, ascending=ascending)

        st.dataframe(
            team_df,
            use_container_width=True,
            hide_index=True,
        )

        st.subheader("Best Team Values")

        if "proj_per_1k_salary" in team_df.columns:
            value_df = team_df.sort_values("proj_per_1k_salary", ascending=False).head(8)
            st.dataframe(
                value_df,
                use_container_width=True,
                hide_index=True,
            )


with tab3:
    st.header("Raw Data")

    st.write("Available columns:")
    st.write(list(df.columns))

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )