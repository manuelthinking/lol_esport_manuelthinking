import os
import re
from collections import Counter
from dotenv import load_dotenv

import pandas as pd
import pyodbc


load_dotenv()

SLOTS = ["ADC", "CPT", "JNG", "MID", "SUP", "TEAM", "TOP"]


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


def parse_lineup(lineup_raw: str):
    """
    Example:
    ADC  Ruler CPT  Chovy JNG  Canyon MID  Zeka SUP  Duro TEAM JD Gaming  TOP  Zeus
    """
    if not lineup_raw:
        return []

    pattern = r"\b(ADC|CPT|JNG|MID|SUP|TEAM|TOP)\b\s+(.+?)(?=\s+\b(?:ADC|CPT|JNG|MID|SUP|TEAM|TOP)\b\s+|$)"
    matches = re.findall(pattern, lineup_raw)

    players = []
    for slot, name in matches:
        name = re.sub(r"\s+", " ", name).strip()
        players.append(
            {
                "roster_slot": slot,
                "player_name": name,
                "position": slot,
                "is_captain": 1 if slot == "CPT" else 0,
            }
        )

    return players


def stack_structure(players):
    """
    Placeholder until we map players to teams.
    For now, returns NULL.
    """
    return None


def main():
    conn = get_conn()

    sql = """
        SELECT
            raw_standing_id,
            slate_date,
            slate_name,
            contest_id,
            contest_name,
            entry_id,
            entry_name,
            rank_num,
            points,
            lineup_raw
        FROM raw.dk_lol_contest_standings
        WHERE lineup_raw IS NOT NULL;
    """

    df = pd.read_sql(sql, conn)

    print(f"Raw lineup rows found: {len(df)}")

    cursor = conn.cursor()

    inserted_lineups = 0
    inserted_players = 0
    skipped_existing = 0

    for _, row in df.iterrows():
        raw_standing_id = int(row["raw_standing_id"])

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM lol.fact_lineup_result
            WHERE source_standing_id = ?;
            """,
            raw_standing_id,
        )

        if cursor.fetchone()[0] > 0:
            skipped_existing += 1
            continue

        players = parse_lineup(row["lineup_raw"])

        if len(players) != 7:
            print(f"WARNING: parsed {len(players)} players for raw_standing_id={raw_standing_id}")
            print(row["lineup_raw"])
            continue

        captain = next((p for p in players if p["is_captain"] == 1), None)

        cursor.execute(
            """
            SELECT slate_id
            FROM lol.dim_slate
            WHERE slate_date = ?
              AND slate_name = ?
              AND site = 'DraftKings';
            """,
            row["slate_date"],
            row["slate_name"],
        )

        slate_row = cursor.fetchone()

        if slate_row:
            slate_id = slate_row[0]
        else:
            cursor.execute(
                """
                INSERT INTO lol.dim_slate (slate_date, slate_name, site, sport)
                OUTPUT INSERTED.slate_id
                VALUES (?, ?, 'DraftKings', 'LoL');
                """,
                row["slate_date"],
                row["slate_name"],
            )
            slate_id = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO lol.fact_lineup_result (
                slate_id,
                contest_id,
                contest_name,
                entry_id,
                entry_name,
                username,
                rank_num,
                points,
                winnings,
                salary_used,
                salary_left,
                lineup_raw,
                stack_structure,
                captain_player,
                captain_team,
                captain_position,
                total_ownership,
                avg_ownership,
                source_standing_id
            )
            OUTPUT INSERTED.lineup_result_id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            slate_id,
            row["contest_id"],
            row["contest_name"],
            row["entry_id"],
            row["entry_name"],
            row["entry_name"],
            int(row["rank_num"]) if pd.notna(row["rank_num"]) else None,
            float(row["points"]) if pd.notna(row["points"]) else None,
            None,
            None,
            None,
            row["lineup_raw"],
            stack_structure(players),
            captain["player_name"] if captain else None,
            None,
            None,
            None,
            None,
            raw_standing_id,
        )

        lineup_result_id = cursor.fetchone()[0]
        inserted_lineups += 1

        for p in players:
            cursor.execute(
                """
                INSERT INTO lol.fact_lineup_player (
                    lineup_result_id,
                    roster_slot,
                    player_name,
                    team,
                    position,
                    salary,
                    ownership_pct,
                    actual_fp,
                    is_captain,
                    source_standing_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                lineup_result_id,
                p["roster_slot"],
                p["player_name"],
                None,
                p["position"],
                None,
                None,
                None,
                p["is_captain"],
                raw_standing_id,
            )
            inserted_players += 1

    conn.commit()
    conn.close()

    print("Done.")
    print(f"Inserted lineups: {inserted_lineups}")
    print(f"Inserted lineup players: {inserted_players}")
    print(f"Skipped existing lineups: {skipped_existing}")


if __name__ == "__main__":
    main()