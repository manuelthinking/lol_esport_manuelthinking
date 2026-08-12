from __future__ import annotations

from .runner import ActionResult, run_sql_query


def check_latest_slate_rows() -> ActionResult:
    query = """
SET NOCOUNT ON;

SELECT TOP 10
    slate_date,
    slate_name,
    COUNT(*) AS rows_count
FROM dbo.dk_lol_slate_player
GROUP BY slate_date, slate_name
ORDER BY slate_date DESC, slate_name;
"""

    return run_sql_query(
        job_id="health_latest_slate_rows",
        query=query,
        timeout_seconds=60,
    )


def check_starter_gaps() -> ActionResult:
    query = """
SET NOCOUNT ON;

SELECT TOP 20
    p.slate_date,
    p.slate_name,
    p.team_abbrev,
    p.position,
    p.dk_player_name
FROM dbo.dk_lol_slate_player p
WHERE p.position <> 'TEAM'
ORDER BY p.slate_date DESC, p.slate_name, p.team_abbrev, p.position;
"""

    return run_sql_query(
        job_id="health_starter_gaps",
        query=query,
        timeout_seconds=60,
    )


def check_recent_ownership_rows() -> ActionResult:
    query = """
SET NOCOUNT ON;

SELECT TOP 10
    slate_date,
    slate_name,
    COUNT(*) AS ownership_rows
FROM raw.dk_lol_player_ownership
GROUP BY slate_date, slate_name
ORDER BY slate_date DESC, slate_name;
"""

    return run_sql_query(
        job_id="health_recent_ownership_rows",
        query=query,
        timeout_seconds=60,
    )


def run_all_health_checks() -> list[ActionResult]:
    return [
        check_latest_slate_rows(),
        check_starter_gaps(),
        check_recent_ownership_rows(),
    ]