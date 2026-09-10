"""
backend/routers/monitor.py
===========================
API endpoint to trigger / inspect the official alert monitor.

POST /monitor/run        — trigger a monitor run (admin only)
POST /monitor/run-dry    — dry run (discover only, do not post) (admin only)
GET  /monitor/status     — last run timestamp + stats (public)

The actual scraping logic lives in fetchers/official_alert_monitor.py.
The backend calls it as a subprocess so the FastAPI event loop is not blocked.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

router = APIRouter(prefix="/monitor", tags=["Alert Monitor"])

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "disaster-dss-dev-key-change-in-prod")
_api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)

_ROOT = Path(__file__).resolve().parents[2]
_STATE_FILE = _ROOT / "data" / "alert_monitor_state.json"
_FETCHER    = _ROOT / "fetchers" / "official_alert_monitor.py"


async def require_admin(key: Optional[str] = Security(_api_key_header)) -> None:
    if key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Admin key required.")


class MonitorStatusResponse(BaseModel):
    last_run: Optional[str]
    seen_url_count: int
    fetcher_exists: bool
    state_file_exists: bool


class MonitorRunResponse(BaseModel):
    triggered: bool
    mode: str
    stdout: str
    stderr: str
    return_code: int
    timestamp: str


@router.get("/status", response_model=MonitorStatusResponse)
def monitor_status():
    """Returns current monitor state — last run time, number of tracked URLs."""
    state = {}
    if _STATE_FILE.exists():
        with open(_STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)

    return MonitorStatusResponse(
        last_run=state.get("last_run"),
        seen_url_count=len(state.get("seen_urls", [])),
        fetcher_exists=_FETCHER.exists(),
        state_file_exists=_STATE_FILE.exists(),
    )


@router.post("/run", response_model=MonitorRunResponse,
             dependencies=[Depends(require_admin)])
def run_monitor():
    """Trigger a live monitor run — discovers new advisories and posts them."""
    return _run_fetcher(dry_run=False)


@router.post("/run-dry", response_model=MonitorRunResponse,
             dependencies=[Depends(require_admin)])
def run_monitor_dry():
    """Dry run — discovers new links but does NOT post to backend."""
    return _run_fetcher(dry_run=True)


def _run_fetcher(dry_run: bool) -> MonitorRunResponse:
    if not _FETCHER.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Fetcher not found at {_FETCHER}",
        )

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
                "BACKEND_URL": os.getenv("BACKEND_URL", "http://127.0.0.1:8001"),
                "ADMIN_API_KEY": ADMIN_API_KEY,
            },
        )
        return MonitorRunResponse(
            triggered=True,
            mode="dry-run" if dry_run else "live",
            stdout=result.stdout[-3000:],  # last 3000 chars
            stderr=result.stderr[-1000:],
            return_code=result.returncode,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Monitor run timed out after 120s",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
