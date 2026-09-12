"""
backend/routers/monitor.py
===========================
API endpoints to trigger and inspect the official alert monitor.

POST /monitor/run        — trigger immediate run (admin)
POST /monitor/run-dry    — dry run, discover only (admin)
GET  /monitor/status     — scheduler + last run state (public)
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from core.config import settings
from core.scheduler import get_scheduler_status

router = APIRouter(prefix="/monitor", tags=["Alert Monitor"])

_api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)

_ROOT        = Path(__file__).resolve().parents[2]
_STATE_FILE  = _ROOT / "data" / "alert_monitor_state.json"
_FETCHER     = _ROOT / "fetchers" / "official_alert_monitor.py"


async def require_admin(key: Optional[str] = Security(_api_key_header)) -> None:
    if key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Admin key required.")


class MonitorStatusResponse(BaseModel):
    scheduler_running: bool
    next_scheduled_run: Optional[str]
    last_run_status: Optional[str]
    last_run_at: Optional[str]
    seen_url_count: int
    fetcher_exists: bool


class MonitorRunResponse(BaseModel):
    triggered: bool
    mode: str
    stdout: str
    stderr: str
    return_code: int
    timestamp: str


@router.get("/status", response_model=MonitorStatusResponse)
def monitor_status():
    """Returns scheduler state + last run info."""
    sched = get_scheduler_status()
    state: dict = {}
    if _STATE_FILE.exists():
        with open(_STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)

    return MonitorStatusResponse(
        scheduler_running=sched.get("running", False),
        next_scheduled_run=sched.get("next_run"),
        last_run_status=sched.get("status"),
        last_run_at=sched.get("run_at"),
        seen_url_count=len(state.get("seen_urls", [])),
        fetcher_exists=_FETCHER.exists(),
    )


@router.post("/run", response_model=MonitorRunResponse,
             dependencies=[Depends(require_admin)])
def run_monitor():
    return _run_fetcher(dry_run=False)


@router.post("/run-dry", response_model=MonitorRunResponse,
             dependencies=[Depends(require_admin)])
def run_monitor_dry():
    return _run_fetcher(dry_run=True)


def _run_fetcher(dry_run: bool) -> MonitorRunResponse:
    if not _FETCHER.exists():
        raise HTTPException(status_code=503,
                            detail=f"Fetcher not found: {_FETCHER}")

    args = [sys.executable, str(_FETCHER)]
    if dry_run:
        args.append("--dry-run")

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(_ROOT),
            env={
                **os.environ,
                "BACKEND_URL":   os.getenv("BACKEND_URL", "http://127.0.0.1:8001"),
                "ADMIN_API_KEY": settings.admin_api_key,
            },
        )
        return MonitorRunResponse(
            triggered=True,
            mode="dry-run" if dry_run else "live",
            stdout=result.stdout[-3000:],
            stderr=result.stderr[-1000:],
            return_code=result.returncode,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Timed out after 120s")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
