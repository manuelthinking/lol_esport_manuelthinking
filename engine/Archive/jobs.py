from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal

from .runner import ActionResult, run_python_script, run_sql_file, run_sql_query


JobType = Literal["python", "sql_file", "sql_query"]


@dataclass(frozen=True)
class JobSpec:
    job_id: str
    label: str
    job_type: JobType
    target: str
    description: str = ""
    default_args: tuple[str, ...] = ()
    timeout_seconds: int = 300


JOBS: dict[str, JobSpec] = {
    # -------------------------
    # Slate / data prep examples
    # -------------------------
    "ingest_dk_slate": JobSpec(
        job_id="ingest_dk_slate",
        label="Ingest DK LoL Slate",
        job_type="python",
        target="scripts/ingest_dk_lol_slate.py",
        description="Loads the DraftKings LoL salary slate into dbo.dk_lol_slate_player.",
        timeout_seconds=300,
    ),

    "build_playbook": JobSpec(
        job_id="build_playbook",
        label="Build LoL Playbook",
        job_type="python",
        target="scripts/build_lol_playbook.py",
        description="Builds the daily LoL playbook output.",
        timeout_seconds=300,
    ),

    "build_manual_starters": JobSpec(
        job_id="build_manual_starters",
        label="Build Manual Starters Sheet",
        job_type="python",
        target="scripts/build_manual_starters_from_dk.py",
        description="Creates or refreshes the manual starters review sheet from DK slate data.",
        timeout_seconds=300,
    ),

    # -------------------------
    # SQL maintenance examples
    # Replace targets with your real SQL file paths as needed.
    # -------------------------
    "refresh_bayes_views": JobSpec(
        job_id="refresh_bayes_views",
        label="Refresh Bayes Views",
        job_type="sql_file",
        target="sql/19_create_vw_lol_bayes_prediction_backtest_match_level.sql",
        description="Runs the Bayes/backtest view SQL file.",
        timeout_seconds=300,
    ),

    # -------------------------
    # Simple validation examples
    # -------------------------
    "check_latest_slate_rows": JobSpec(
        job_id="check_latest_slate_rows",
        label="Check Latest Slate Rows",
        job_type="sql_query",
        target="""
SET NOCOUNT ON;

SELECT TOP 10
    slate_date,
    slate_name,
    COUNT(*) AS rows_count
FROM dbo.dk_lol_slate_player
GROUP BY slate_date, slate_name
ORDER BY slate_date DESC, slate_name;
""",
        description="Shows recent slate row counts by slate date/name.",
        timeout_seconds=60,
    ),

    "check_missing_bayes_rows": JobSpec(
        job_id="check_missing_bayes_rows",
        label="Check Missing Bayes Rows",
        job_type="sql_query",
        target="""
SET NOCOUNT ON;

SELECT TOP 20
    slate_date,
    slate_name,
    COUNT(*) AS rows_count
FROM dbo.dk_lol_slate_player
GROUP BY slate_date, slate_name
ORDER BY slate_date DESC, slate_name;
""",
        description="Starter placeholder for Bayes gap checks. Replace with your final Bayes exception query.",
        timeout_seconds=60,
    ),
}


def list_jobs() -> list[JobSpec]:
    return list(JOBS.values())


def get_job(job_id: str) -> JobSpec:
    if job_id not in JOBS:
        raise KeyError(f"Unknown job_id: {job_id}")

    return JOBS[job_id]


def run_job(
    job_id: str,
    *,
    args: Optional[list[str]] = None,
    timeout_seconds: Optional[int] = None,
) -> ActionResult:
    job = get_job(job_id)

    effective_timeout = timeout_seconds or job.timeout_seconds

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