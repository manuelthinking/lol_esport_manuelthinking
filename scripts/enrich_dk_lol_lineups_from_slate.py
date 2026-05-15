import os
import re
from pathlib import Path
from collections import Counter

import pandas as pd
import pyodbc
from dotenv import load_dotenv


load_dotenv()

SLATE_DIR = Path(r"C:\DailyDFS\LoL\data\slate_data")


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


def normalize_name(x):
    if pd.isna(x):
        return None
    return re.sub(r"\s+", " ", str(x).strip()).lower()


def find_col(df, candidates):
    cols = {c.lower().strip(): c for c in df.columns}
    for c in candidates:
        if c.lower() in cols:
            return cols[c.lower()]
    return None


def load_all_salaries():
    rows = []

    for path in SLATE_DIR.glob("*.csv"):
        m = re.search(r"dk_lol_(\d{4}-\d{2}-\d{2})_(.+)\.csv$", path.name, re.I)
        if not m:
            continue

        slate_date = m.group(1)
        slate_name = m.group(2).lower()

        df = pd.read_csv(path)
        df.columns = [c.strip() for c in df.columns]

        name_col = find_col(df, ["Name", "Player", "player_name"])
        pos_col = find_col(df, ["Roster Position", "Position", "RosterPosition"])
        salary_col = find_col(df, ["Salary", "salary"])
        team_col = find_col(df, ["TeamAbbrev", "Team", "team", "Team Abbrev"])

        if not name_col or not salary_col:
            print(f"Skipping {path.name}: could not find name/salary columns")
            continue

        for _, r in df.iterrows():
            rows.append({
                "slate_date": slate_date,
                "slate_name": slate_name,
                "player_key": normalize_name(r[name_col]),
                "player_name": str(r[name_col]).strip(),
                "position": str(r[pos_col]).strip().upper() if pos_col and pd.notna(r[pos_col]) else None,
                "salary": int(float(r[salary_col])) if pd.notna(r[salary_col]) else None,
                "team": str(r[team_col]).strip() if team_col and pd.notna(r[team_col]) else None,
            })

    return pd.DataFrame(rows)


def main():
    salary_df = load_all_salaries()

    if salary_df.empty:
        print(f"No DK salary files found in {SLATE_DIR}")
        return

    print(f"Salary rows loaded from CSVs: {len(salary_df)}")

    conn = get_conn()

    lp_sql = """
        SELECT
            lp.lineup_player_id,
            lp.lineup_result_id,
            lp.roster_slot,
            lp.player_name,
            ds.slate_date,
            ds.slate_name
        FROM lol.fact_lineup_player lp
        JOIN lol.fact_lineup_result lr
            ON lp.lineup_result_id = lr.lineup_result_id
        JOIN lol.dim_slate ds
            ON lr.slate_id = ds.slate_id
        WHERE lp.salary IS NULL
           OR lp.team IS NULL;
    """

    lp_df = pd.read_sql(lp_sql, conn)
    print(f"Lineup player rows needing enrichment: {len(lp_df)}")

    cursor = conn.cursor()

    updated = 0
    missed = 0

    for _, row in lp_df.iterrows():
        player_key = normalize_name(row["player_name"])
        slate_date = str(row["slate_date"])
        slate_name = str(row["slate_name"]).lower()
        roster_slot = str(row["roster_slot"]).strip().upper()

        # First try exact slate_date + slate_name + player + roster slot
        matches = salary_df[
            (salary_df["slate_date"] == slate_date)
            & (salary_df["slate_name"] == slate_name)
            & (salary_df["player_key"] == player_key)
            & (salary_df["position"].str.upper() == roster_slot)
        ]

        # Fallback: same date + player + roster slot
        if matches.empty:
            matches = salary_df[
                (salary_df["slate_date"] == slate_date)
                & (salary_df["player_key"] == player_key)
                & (salary_df["position"].str.upper() == roster_slot)
            ]

        # Final fallback: same date + player only
        if matches.empty:
            matches = salary_df[
                (salary_df["slate_date"] == slate_date)
                & (salary_df["player_key"] == player_key)
            ]

        if matches.empty:
            missed += 1
            continue

        match = matches.iloc[0]

        cursor.execute(
            """
            UPDATE lol.fact_lineup_player
            SET
            team = ?,
            salary = ?,
            actual_position = ?
            WHERE lineup_player_id = ?;
            """,
            match["team"],
            int(match["salary"]) if pd.notna(match["salary"]) else None,
            match["position"],
            int(row["lineup_player_id"]),
        )

        updated += 1

    conn.commit()

    # Update captain team/position, salary_used, salary_left, stack structure
    cursor.execute(
        """
        UPDATE lr
        SET
            lr.captain_team = c.team,
            lr.captain_position = c.position
        FROM lol.fact_lineup_result lr
        JOIN lol.fact_lineup_player c
            ON lr.lineup_result_id = c.lineup_result_id
           AND c.is_captain = 1;
        """
    )

    cursor.execute(
        """
        UPDATE lr
        SET
            lr.salary_used = x.salary_used,
            lr.salary_left = 50000 - x.salary_used
        FROM lol.fact_lineup_result lr
        JOIN (
            SELECT lineup_result_id, SUM(salary) AS salary_used
            FROM lol.fact_lineup_player
            GROUP BY lineup_result_id
        ) x
            ON lr.lineup_result_id = x.lineup_result_id;
        """
    )

    conn.commit()

    # Stack structure in Python because it is cleaner.
    lineup_sql = """
        SELECT
            lineup_result_id,
            roster_slot,
            team
        FROM lol.fact_lineup_player
        WHERE team IS NOT NULL;
    """

    team_df = pd.read_sql(lineup_sql, conn)

    stack_updates = []

    for lineup_id, g in team_df.groupby("lineup_result_id"):
        teams = []

        for _, r in g.iterrows():
            slot = r["roster_slot"]
            team = r["team"]

            # TEAM slot counts as part of the stack.
            if pd.notna(team):
                teams.append(team)

        counts = sorted(Counter(teams).values(), reverse=True)
        stack_structure = "-".join(str(x) for x in counts)
        team_summary = ", ".join(
            f"{team}:{cnt}" for team, cnt in Counter(teams).most_common()
        )

        stack_updates.append((stack_structure, team_summary, int(lineup_id)))

    for stack_structure, team_summary, lineup_id in stack_updates:
        cursor.execute(
            """
            UPDATE lol.fact_lineup_result
            SET stack_structure = ?,
                team_stack_summary = ?
            WHERE lineup_result_id = ?;
            """,
            stack_structure,
            team_summary,
            lineup_id,
        )

    conn.commit()
    conn.close()

    print("Done.")
    print(f"Updated lineup player rows: {updated}")
    print(f"Missed lineup player rows: {missed}")
    print(f"Updated stack rows: {len(stack_updates)}")


if __name__ == "__main__":
    main()