from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Literal

from .runner import ActionResult, run_python_script, run_sql_file, run_sql_query


JobType = Literal["python", "sql_file", "sql_query", "chain"]


@dataclass(frozen=True)
class JobSpec:
    job_id: str
    label: str
    job_type: JobType
    target: str
    description: str = ""
    default_args: tuple[str, ...] = ()
    timeout_seconds: int = 300
    category: str = "General"
    chain_job_ids: tuple[str, ...] = ()


# ============================================================
# Job Registry
# ============================================================
# The Command Center should call these jobs through run_job().
# Add new scripts/SQL checks here instead of wiring subprocess
# calls directly inside Streamlit.
# ============================================================

JOBS: dict[str, JobSpec] = {
    # ========================================================
    # Slate Prep
    # ========================================================
    "ingest_dk_slate": JobSpec(
        job_id="ingest_dk_slate",
        label="Ingest DK LoL Slate",
        job_type="python",
        target="scripts/ingest_dk_lol_slate.py",
        description="Loads the DraftKings LoL salary slate into dbo.dk_lol_slate_player.",
        timeout_seconds=300,
        category="Slate Prep",
    ),

    "build_manual_starters": JobSpec(
        job_id="build_manual_starters",
        label="Build Manual Starters Sheet",
        job_type="python",
        target="scripts/build_manual_starters_from_dk.py",
        description="Creates or refreshes data/manual_starters.csv from the DK slate.",
        timeout_seconds=300,
        category="Slate Prep",
    ),

    "build_playbook": JobSpec(
        job_id="build_playbook",
        label="Build LoL Playbook",
        job_type="python",
        target="scripts/build_lol_playbook.py",
        description="Builds the daily LoL playbook output after slate, starter, and ratings data are ready.",
        timeout_seconds=300,
        category="Slate Prep",
    ),

    # ========================================================
    # Oracle / Historical Data Refresh
    # ========================================================
    "ingest_oracle_elixir": JobSpec(
        job_id="ingest_oracle_elixir",
        label="Ingest Oracle Elixir",
        job_type="python",
        target="scripts/ingest_oracle_elixir.py",
        description="Downloads/refreshes Oracle Elixir match data used by LoL historical models.",
        timeout_seconds=900,
        category="Historical Refresh",
    ),

    "build_player_games": JobSpec(
        job_id="build_player_games",
        label="Build Player Games",
        job_type="python",
        target="scripts/build_player_games.py",
        description="Builds or refreshes dbo.fact_lol_player_game from raw Oracle Elixir data.",
        timeout_seconds=900,
        category="Historical Refresh",
    ),

    "build_team_game_stats": JobSpec(
        job_id="build_team_game_stats",
        label="Build Team Game Stats",
        job_type="python",
        target="scripts/build_lol_team_game_stats.py",
        description="Refreshes team-level per-game stats used for team profiles and matchup logic.",
        timeout_seconds=600,
        category="Historical Refresh",
    ),

    "build_team_series_results": JobSpec(
        job_id="build_team_series_results",
        label="Build Team Series Results",
        job_type="python",
        target="scripts/build_lol_team_series_results.py",
        description="Refreshes team series outcomes such as 2-0, 2-1, 1-2, and 0-2.",
        timeout_seconds=600,
        category="Historical Refresh",
    ),

    "build_team_series_profiles": JobSpec(
        job_id="build_team_series_profiles",
        label="Build Team Series Profiles",
        job_type="python",
        target="scripts/build_lol_team_series_profiles.py",
        description="Refreshes team outcome profiles used by slate review, Bayes logic, and projections.",
        timeout_seconds=600,
        category="Historical Refresh",
    ),

    # ========================================================
    # Lane / Player Ratings
    # ========================================================
    "build_lane_matchups": JobSpec(
        job_id="build_lane_matchups",
        label="Build Lane Matchups",
        job_type="python",
        target="scripts/build_lane_matchups.py",
        description="Refreshes lane matchup tables by team, opponent, league, and position.",
        timeout_seconds=600,
        category="Ratings Refresh",
    ),

    "build_player_lane_matchups": JobSpec(
        job_id="build_player_lane_matchups",
        label="Build Player Lane Matchups",
        job_type="python",
        target="scripts/build_player_lane_matchups.py",
        description="Refreshes player-vs-lane matchup history.",
        timeout_seconds=600,
        category="Ratings Refresh",
    ),

    "build_player_lane_ratings": JobSpec(
        job_id="build_player_lane_ratings",
        label="Build Player Lane Ratings",
        job_type="python",
        target="scripts/build_player_lane_ratings.py",
        description="Refreshes player lane ratings, rating_score, avg_dk, dk_value, and related slate rating data.",
        timeout_seconds=600,
        category="Ratings Refresh",
    ),

    # ========================================================
    # Bayes / SQL Refresh
    # ========================================================
    "populate_bayes_backtest": JobSpec(
        job_id="populate_bayes_backtest",
        label="Populate Bayes Backtest",
        job_type="sql_file",
        target="sql/18_populate_lol_bayes_prediction_backtest.sql",
        description="Populates or refreshes the Bayes prediction backtest table.",
        timeout_seconds=600,
        category="Bayes Refresh",
    ),

    "refresh_bayes_backtest_view": JobSpec(
        job_id="refresh_bayes_backtest_view",
        label="Refresh Bayes Backtest View",
        job_type="sql_file",
        target="sql/19_create_vw_lol_bayes_prediction_backtest_match_level.sql",
        description="Creates or refreshes the match-level Bayes prediction backtest view.",
        timeout_seconds=300,
        category="Bayes Refresh",
    ),

    # Keep old ID as an alias so existing Command Center references do not break.
    "refresh_bayes_views": JobSpec(
        job_id="refresh_bayes_views",
        label="Refresh Bayes Views",
        job_type="sql_file",
        target="sql/19_create_vw_lol_bayes_prediction_backtest_match_level.sql",
        description="Alias for refreshing the Bayes match-level backtest view.",
        timeout_seconds=300,
        category="Bayes Refresh",
    ),

    # ========================================================
    # Post-Contest Review
    # ========================================================
    "ingest_contest_standings": JobSpec(
        job_id="ingest_contest_standings",
        label="Ingest Contest Standings",
        job_type="python",
        target="scripts/ingest_dk_lol_contest_standings.py",
        description="Loads DraftKings LoL contest standings into raw contest tables.",
        timeout_seconds=900,
        category="Post-Contest",
    ),

    "transform_dk_lineups": JobSpec(
        job_id="transform_dk_lineups",
        label="Transform DK Lineups",
        job_type="python",
        target="scripts/transform_dk_lol_lineups.py",
        description="Parses raw DraftKings lineup strings into structured lineup records.",
        timeout_seconds=900,
        category="Post-Contest",
    ),

    "enrich_dk_lineups_from_slate": JobSpec(
        job_id="enrich_dk_lineups_from_slate",
        label="Enrich DK Lineups From Slate",
        job_type="python",
        target="scripts/enrich_dk_lol_lineups_from_slate.py",
        description="Adds slate salary, team, player, and position metadata to parsed contest lineups.",
        timeout_seconds=900,
        category="Post-Contest",
    ),

    # ========================================================
    # Validation / Health Checks
    # ========================================================
    "check_latest_slate_rows": JobSpec(
        job_id="check_latest_slate_rows",
        label="Check Latest Slate Rows",
        job_type="sql_query",
        target="""
SET NOCOUNT ON;

SELECT TOP 10
    slate_date,
    slate_name,
    COUNT(*) AS rows_count,
    COUNT(DISTINCT team_abbrev) AS teams,
    SUM(CASE WHEN LOWER(ISNULL(dk_position, '')) = 'team' THEN 1 ELSE 0 END) AS team_rows,
    SUM(CASE WHEN LOWER(ISNULL(dk_position, '')) <> 'team' THEN 1 ELSE 0 END) AS player_rows,
    MAX(loaded_at) AS last_loaded_at
FROM dbo.dk_lol_slate_player
GROUP BY slate_date, slate_name
ORDER BY slate_date DESC, slate_name;
""",
        description="Shows recent DK slate row counts by slate date and slate name.",
        timeout_seconds=60,
        category="Validation",
    ),

    "check_manual_starter_file_current_slate": JobSpec(
        job_id="check_manual_starter_file_current_slate",
        label="Check Manual Starter History Current Slate",
        job_type="sql_query",
        target="""
SET NOCOUNT ON;

DECLARE @slate_date date;
DECLARE @slate_name varchar(100);

SELECT TOP 1
    @slate_date = slate_date,
    @slate_name = slate_name
FROM dbo.dk_lol_slate_player
GROUP BY slate_date, slate_name
ORDER BY slate_date DESC, slate_name DESC;

SELECT
    p.slate_date,
    p.slate_name,
    p.team_abbrev,
    COUNT(*) AS slate_player_rows,
    SUM(CASE WHEN LOWER(ISNULL(p.dk_position, '')) = 'team' THEN 1 ELSE 0 END) AS team_rows,
    SUM(CASE WHEN LOWER(ISNULL(p.dk_position, '')) <> 'team' THEN 1 ELSE 0 END) AS player_rows
FROM dbo.dk_lol_slate_player p
WHERE p.slate_date = @slate_date
  AND p.slate_name = @slate_name
GROUP BY p.slate_date, p.slate_name, p.team_abbrev
ORDER BY p.team_abbrev;
""",
        description="Shows team-level slate row counts for the latest slate as a starter-review sanity check.",
        timeout_seconds=60,
        category="Validation",
    ),

    "check_missing_bayes_rows": JobSpec(
        job_id="check_missing_bayes_rows",
        label="Check Missing Bayes Rows",
        job_type="sql_query",
        target="""
SET NOCOUNT ON;

DECLARE @slate_date date;
DECLARE @slate_name varchar(100);

SELECT TOP 1
    @slate_date = slate_date,
    @slate_name = slate_name
FROM dbo.vw_lol_ownership_training
GROUP BY slate_date, slate_name
ORDER BY slate_date DESC, slate_name DESC;

SELECT
    slate_date,
    slate_name,
    COUNT(*) AS rows_count,
    SUM(CASE WHEN bayes_win_pct IS NULL THEN 1 ELSE 0 END) AS missing_bayes_rows,
    SUM(CASE WHEN bayes_win_pct IS NOT NULL THEN 1 ELSE 0 END) AS matched_bayes_rows
FROM dbo.vw_lol_ownership_training
WHERE slate_date = @slate_date
  AND slate_name = @slate_name
GROUP BY slate_date, slate_name;
""",
        description="Checks whether the latest ownership-training slate has missing Bayes values.",
        timeout_seconds=60,
        category="Validation",
    ),

    "check_bayes_gaps_detail": JobSpec(
        job_id="check_bayes_gaps_detail",
        label="Check Bayes Gaps Detail",
        job_type="sql_query",
        target="""
SET NOCOUNT ON;

DECLARE @slate_date date;
DECLARE @slate_name varchar(100);

SELECT TOP 1
    @slate_date = slate_date,
    @slate_name = slate_name
FROM dbo.vw_lol_ownership_training
GROUP BY slate_date, slate_name
ORDER BY slate_date DESC, slate_name DESC;

SELECT TOP 100
    slate_date,
    slate_name,
    dk_player_name,
    ownership_roster_position,
    team_abbrev,
    opponent_abbrev,
    rating_team_name,
    league,
    position,
    salary,
    ownership_pct,
    bayes_sample_type,
    bayes_win_pct,
    bayes_suggested_path,
    team_strength_bucket,
    opponent_strength_bucket,
    salary_tier,
    ownership_slot_type
FROM dbo.vw_lol_ownership_training
WHERE slate_date = @slate_date
  AND slate_name = @slate_name
  AND bayes_win_pct IS NULL
ORDER BY team_abbrev, position, dk_player_name;
""",
        description="Lists player rows from the latest ownership-training slate where Bayes values are missing.",
        timeout_seconds=60,
        category="Validation",
    ),

    "check_recent_ownership_rows": JobSpec(
        job_id="check_recent_ownership_rows",
        label="Check Recent Ownership Rows",
        job_type="sql_query",
        target="""
SET NOCOUNT ON;

SELECT TOP 10
    slate_date,
    slate_name,
    COUNT(*) AS raw_ownership_rows,
    COUNT(DISTINCT contest_id) AS contests,
    MAX(loaded_at) AS last_loaded_at
FROM raw.dk_lol_player_ownership
GROUP BY slate_date, slate_name
ORDER BY slate_date DESC, slate_name;
""",
        description="Shows recent raw DraftKings player ownership row counts.",
        timeout_seconds=60,
        category="Validation",
    ),

    "check_recent_contest_rows": JobSpec(
        job_id="check_recent_contest_rows",
        label="Check Recent Contest Rows",
        job_type="sql_query",
        target="""
SET NOCOUNT ON;

SELECT TOP 10
    slate_date,
    slate_name,
    COUNT(*) AS raw_contest_rows,
    COUNT(DISTINCT contest_id) AS contests,
    MAX(loaded_at) AS last_loaded_at
FROM raw.dk_lol_contest_standings
GROUP BY slate_date, slate_name
ORDER BY slate_date DESC, slate_name;
""",
        description="Shows recent raw DraftKings contest standings row counts.",
        timeout_seconds=60,
        category="Validation",
    ),

    "check_top_1pct_ready": JobSpec(
        job_id="check_top_1pct_ready",
        label="Check Top 1% Lineups Ready",
        job_type="sql_query",
        target="""
SET NOCOUNT ON;

SELECT TOP 10
    slate_date,
    slate_name,
    COUNT(*) AS top_1pct_rows,
    MIN(rank_num) AS best_rank,
    MAX(points) AS best_score,
    AVG(points) AS avg_points
FROM lol.vw_top_1pct_lineups
GROUP BY slate_date, slate_name
ORDER BY slate_date DESC, slate_name;
""",
        description="Checks whether top 1% lineup review rows are available by slate.",
        timeout_seconds=60,
        category="Validation",
    ),

    "check_bayes_backtest_recent": JobSpec(
        job_id="check_bayes_backtest_recent",
        label="Check Recent Bayes Backtest",
        job_type="sql_query",
        target="""
SET NOCOUNT ON;

SELECT TOP 50
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
""",
        description="Displays recent Bayes backtest rows for model review.",
        timeout_seconds=60,
        category="Validation",
    ),

    # -------------------------
    # Workflow Chains
    # -------------------------
    "run_prelock_refresh": JobSpec(
        job_id="run_prelock_refresh",
        label="Run Pre-Lock Refresh",
        job_type="chain",
        target="workflow",
        description=(
            "Runs the main pre-lock data refresh chain: Oracle data, player/team tables, "
            "lane/rating builds, and playbook."
        ),
        timeout_seconds=1800,
        category="Workflow",
        chain_job_ids=(
            "ingest_oracle_elixir",
            "build_player_games",
            "build_team_game_stats",
            "build_team_series_results",
            "build_team_series_profiles",
            "build_lane_matchups",
            "build_player_lane_matchups",
            "build_player_lane_ratings",
            "build_playbook",
        ),
    ),

    "run_postcontest_refresh": JobSpec(
        job_id="run_postcontest_refresh",
        label="Run Post-Contest Refresh",
        job_type="chain",
        target="workflow",
        description=(
            "Runs the post-contest refresh chain: contest standings ingest, lineup transform, "
            "lineup enrichment, Bayes backtest refresh, and top 1% readiness check."
        ),
        timeout_seconds=1800,
        category="Workflow",
        chain_job_ids=(
            "ingest_contest_standings",
            "transform_dk_lineups",
            "enrich_dk_lineups_from_slate",
            "populate_bayes_backtest",
            "refresh_bayes_backtest_view",
            "check_top_1pct_ready",
        ),
    ),

}


# ============================================================
# Registry Helpers
# ============================================================

def list_jobs() -> list[JobSpec]:
    return list(JOBS.values())


def list_jobs_by_category() -> dict[str, list[JobSpec]]:
    grouped: dict[str, list[JobSpec]] = {}

    for job in list_jobs():
        grouped.setdefault(job.category, []).append(job)

    return grouped


def get_job(job_id: str) -> JobSpec:
    if job_id not in JOBS:
        raise KeyError(f"Unknown job_id: {job_id}")

    return JOBS[job_id]

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def run_chain_job(
    job: JobSpec,
    *,
    timeout_seconds: Optional[int] = None,
) -> ActionResult:
    """
    Runs a chain of existing jobs.

    Behavior:
    - Runs jobs in chain_job_ids order.
    - Stops on first failure.
    - Returns one ActionResult for the full chain.
    - stdout contains step-by-step summaries.
    - stderr contains the failed step stderr, if any.
    """

    started_at = _now_iso()
    chain_start = datetime.now()

    stdout_parts = []
    stderr_parts = []
    command_parts = []

    total_duration = 0.0
    failed_result: Optional[ActionResult] = None

    if not job.chain_job_ids:
        finished_at = _now_iso()

        return ActionResult(
            job_id=job.job_id,
            success=False,
            command=["CHAIN", job.job_id],
            return_code=-10,
            stdout="",
            stderr=f"Chain job {job.job_id} has no chain_job_ids configured.",
            duration_seconds=0.0,
            started_at=started_at,
            finished_at=finished_at,
        )

    stdout_parts.append("=" * 80)
    stdout_parts.append(f"CHAIN START: {job.label} ({job.job_id})")
    stdout_parts.append(f"Started at: {started_at}")
    stdout_parts.append(f"Steps: {len(job.chain_job_ids)}")
    stdout_parts.append("=" * 80)

    for idx, child_job_id in enumerate(job.chain_job_ids, start=1):
        stdout_parts.append("")
        stdout_parts.append("-" * 80)
        stdout_parts.append(f"STEP {idx}/{len(job.chain_job_ids)}: {child_job_id}")
        stdout_parts.append("-" * 80)

        try:
            child_result = run_job(child_job_id)
        except Exception as exc:
            finished_at = _now_iso()
            duration_seconds = round((datetime.now() - chain_start).total_seconds(), 3)

            stderr = f"Failed to run child job {child_job_id}: {type(exc).__name__}: {exc}"

            return ActionResult(
                job_id=job.job_id,
                success=False,
                command=["CHAIN", job.job_id, *job.chain_job_ids],
                return_code=-20,
                stdout="\n".join(stdout_parts),
                stderr=stderr,
                duration_seconds=duration_seconds,
                started_at=started_at,
                finished_at=finished_at,
            )

        total_duration += float(child_result.duration_seconds)
        command_parts.append(" ".join(child_result.command))

        stdout_parts.append(f"Child job: {child_result.job_id}")
        stdout_parts.append(f"Success: {child_result.success}")
        stdout_parts.append(f"Return code: {child_result.return_code}")
        stdout_parts.append(f"Duration seconds: {child_result.duration_seconds}")
        stdout_parts.append("")
        stdout_parts.append("Command:")
        stdout_parts.append(" ".join(child_result.command))
        stdout_parts.append("")
        stdout_parts.append("stdout:")
        stdout_parts.append(child_result.stdout if child_result.stdout else "(empty)")

        if child_result.stderr:
            stdout_parts.append("")
            stdout_parts.append("stderr:")
            stdout_parts.append(child_result.stderr)

        if not child_result.success:
            failed_result = child_result
            stderr_parts.append(
                f"Chain stopped at step {idx}/{len(job.chain_job_ids)}: {child_job_id}"
            )
            stderr_parts.append("")
            stderr_parts.append(child_result.stderr if child_result.stderr else "(no stderr)")
            break

    finished_at = _now_iso()
    duration_seconds = round((datetime.now() - chain_start).total_seconds(), 3)

    stdout_parts.append("")
    stdout_parts.append("=" * 80)

    if failed_result:
        stdout_parts.append(f"CHAIN FAILED: {job.label} ({job.job_id})")
        stdout_parts.append(f"Failed child job: {failed_result.job_id}")
        stdout_parts.append(f"Finished at: {finished_at}")
        stdout_parts.append(f"Wall duration seconds: {duration_seconds}")
        stdout_parts.append("=" * 80)

        return ActionResult(
            job_id=job.job_id,
            success=False,
            command=["CHAIN", job.job_id, *job.chain_job_ids],
            return_code=failed_result.return_code,
            stdout="\n".join(stdout_parts),
            stderr="\n".join(stderr_parts),
            duration_seconds=duration_seconds,
            started_at=started_at,
            finished_at=finished_at,
        )

    stdout_parts.append(f"CHAIN SUCCESS: {job.label} ({job.job_id})")
    stdout_parts.append(f"Finished at: {finished_at}")
    stdout_parts.append(f"Wall duration seconds: {duration_seconds}")
    stdout_parts.append(f"Child duration total seconds: {round(total_duration, 3)}")
    stdout_parts.append("=" * 80)

    return ActionResult(
        job_id=job.job_id,
        success=True,
        command=["CHAIN", job.job_id, *job.chain_job_ids],
        return_code=0,
        stdout="\n".join(stdout_parts),
        stderr="",
        duration_seconds=duration_seconds,
        started_at=started_at,
        finished_at=finished_at,
    )

def run_job(
    job_id: str,
    *,
    args: Optional[list[str]] = None,
    timeout_seconds: Optional[int] = None,
) -> ActionResult:
    job = get_job(job_id)

    effective_timeout = timeout_seconds or job.timeout_seconds

    if job.job_type == "chain":
        return run_chain_job(
            job,
            timeout_seconds=effective_timeout,
        )

    if job.job_type == "python":
        final_args = list(job.default_args)

        if args:
            final_args.extend(args)

        return run_python_script(
            job_id=job.job_id,
            script_path=job.target,
            args=final_args,
            timeout_seconds=effective_timeout,
        )

    if job.job_type == "sql_file":
        return run_sql_file(
            job_id=job.job_id,
            sql_file_path=job.target,
            timeout_seconds=effective_timeout,
        )

    if job.job_type == "sql_query":
        return run_sql_query(
            job_id=job.job_id,
            query=job.target,
            timeout_seconds=effective_timeout,
        )

    raise ValueError(f"Unsupported job_type: {job.job_type}")
