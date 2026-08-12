from __future__ import annotations

import os
import sys
import time
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Sequence

from click import command


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class ActionResult:
    job_id: str
    success: bool
    command: list[str]
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    started_at: str
    finished_at: str

    def as_dict(self) -> dict:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _run_command(
    *,
    job_id: str,
    command: Sequence[str],
    cwd: Optional[Path] = None,
    timeout_seconds: Optional[int] = None,
) -> ActionResult:
    started_at = _now_iso()
    start = time.perf_counter()

    cmd_list = [str(x) for x in command]

    try:
        proc = subprocess.run(
            cmd_list,
            cwd=str(cwd or PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )

        duration = round(time.perf_counter() - start, 3)

        return ActionResult(
            job_id=job_id,
            success=proc.returncode == 0,
            command=cmd_list,
            return_code=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            duration_seconds=duration,
            started_at=started_at,
            finished_at=_now_iso(),
        )

    except subprocess.TimeoutExpired as exc:
        duration = round(time.perf_counter() - start, 3)

        return ActionResult(
            job_id=job_id,
            success=False,
            command=cmd_list,
            return_code=-1,
            stdout=exc.stdout or "",
            stderr=f"Command timed out after {timeout_seconds} seconds.\n{exc.stderr or ''}",
            duration_seconds=duration,
            started_at=started_at,
            finished_at=_now_iso(),
        )

    except Exception as exc:
        duration = round(time.perf_counter() - start, 3)

        return ActionResult(
            job_id=job_id,
            success=False,
            command=cmd_list,
            return_code=-999,
            stdout="",
            stderr=f"{type(exc).__name__}: {exc}",
            duration_seconds=duration,
            started_at=started_at,
            finished_at=_now_iso(),
        )


def run_python_script(
    *,
    job_id: str,
    script_path: str | Path,
    args: Optional[Sequence[str]] = None,
    timeout_seconds: Optional[int] = None,
    cwd: Optional[str | Path] = None,
) -> ActionResult:
    script = Path(script_path)

    if not script.is_absolute():
        script = PROJECT_ROOT / script

    command = [sys.executable, str(script)]

    if args:
        command.extend([str(a) for a in args])

    return _run_command(
        job_id=job_id,
        command=command,
        cwd=Path(cwd) if cwd else PROJECT_ROOT,
        timeout_seconds=timeout_seconds,
    )


def _get_sqlcmd_server() -> str:
    return os.getenv("DB_SERVER", r"DESKTOP-I9OLS14\SQLEXPRESS")


def _get_sqlcmd_database() -> str:
    return os.getenv("DB_DATABASE", "lol_esports")


def run_sql_file(
    *,
    job_id: str,
    sql_file_path: str | Path,
    server: Optional[str] = None,
    database: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
    cwd: Optional[str | Path] = None,
) -> ActionResult:
    sql_file = Path(sql_file_path)

    if not sql_file.is_absolute():
        sql_file = PROJECT_ROOT / sql_file

    command = [
        "sqlcmd",
        "-S",
        server or _get_sqlcmd_server(),
        "-d",
        database or _get_sqlcmd_database(),
        "-E",
        "-b",
        "-C",
        "-i",
        str(sql_file),
    ]

    return _run_command(
        job_id=job_id,
        command=command,
        cwd=Path(cwd) if cwd else PROJECT_ROOT,
        timeout_seconds=timeout_seconds,
    )


def run_sql_query(
    *,
    job_id: str,
    query: str,
    server: Optional[str] = None,
    database: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
    cwd: Optional[str | Path] = None,
) -> ActionResult:
    command = [
        "sqlcmd",
        "-S",
        server or _get_sqlcmd_server(),
        "-d",
        database or _get_sqlcmd_database(),
        "-E",
        "-b",
        "-C",
        "-Q",
        query,
    ]

    return _run_command(
        job_id=job_id,
        command=command,
        cwd=Path(cwd) if cwd else PROJECT_ROOT,
        timeout_seconds=timeout_seconds,
    )