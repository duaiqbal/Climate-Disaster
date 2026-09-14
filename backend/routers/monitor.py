"""
backend/routers/monitor.py
===========================
API endpoints to trigger and inspect the official alert monitor.

POST /monitor/run        — trigger immediate run (admin)
POST /monitor/run-dry    — dry run, discover only (admin)
GET  /monitor/status     — per-source health + scheduler state (public)
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from core.config import settings
from core.scheduler import get_scheduler_status

router = APIRouter(prefix="/monitor", tags=["Alert Monitor"])

_api_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)

_ROOT       = Path(__file__).resolve().parents[2]
_STATE_FILE = _ROOT / "data" / "alert_monitor_state.json"
_FETCHER    = _ROOT / "fetchers" / "official_alert_monitor.py"


async def require_admin(key: Optional[str] = Security(_api_key_header)) -> None:
    if key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Admin key required.")


# ── Response schemas ──────────────────────────────────────────────────────────

class SourceHealthEntry(BaseModel):
    """Health record for a single source authority."""
    source_id:          str
    source_org:         str
    province:           str
    page_url:           str
    last_attempt:       Optional[str]   # ISO timestamp of most recent attempt
    last_ok:            Optional[str]   # ISO timestamp of last successful fetch
    last_error:         Optional[str]   # error message if last attempt failed
    alerts_contributed: int             # total alerts ever posted from this source
    attempt_count:      int             # total number of fetch attempts


class MonitorStatusResponse(BaseModel):
    # Aggregate fields (backward compatible — existing callers unchanged)
    scheduler_running:  bool
    next_scheduled_run: Optional[str]
    last_run_status:    Optional[str]
    last_run_at:        Optional[str]
    seen_url_count:     int
    fetcher_exists:     bool
    # New: per-source breakdown (Phase 2.2)
    sources:            list[SourceHealthEntry] = []
    sources_integrated: int = 0
    sources_healthy:    int = 0   # sources with last_ok not None
    sources_errored:    int = 0   # sources whose last attempt errored


class MonitorRunResponse(BaseModel):
    triggered:   bool
    mode:        str
    stdout:      str
    stderr:      str
    return_code: int
    timestamp:   str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status", response_model=MonitorStatusResponse)
def monitor_status() -> MonitorStatusResponse:
    """
    Returns scheduler state + per-source health breakdown.

    The `sources` list shows each configured authority independently so a
    single failing source is immediately visible — it won't be hidden inside
    an overall OK status.
    """
    sched = get_scheduler_status()
    state: dict[str, Any] = {}
    if _STATE_FILE.exists():
        with open(_STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)

    source_health_raw: dict = state.get("source_health", {})

    source_entries: list[SourceHealthEntry] = []
    for _key, sh in source_health_raw.items():
        source_entries.append(SourceHealthEntry(
            source_id          = sh.get("source_id", _key),
            source_org         = sh.get("source_org", ""),
            province           = sh.get("province", ""),
            page_url           = sh.get("page_url", ""),
            last_attempt       = sh.get("last_attempt"),
            last_ok            = sh.get("last_ok"),
            last_error         = sh.get("last_error"),
            alerts_contributed = sh.get("alerts_contributed", 0),
            attempt_count      = sh.get("count", 0),
        ))

    healthy  = sum(1 for s in source_entries if s.last_ok is not None)
    errored  = sum(1 for s in source_entries if s.last_error is not None)

    return MonitorStatusResponse(
        scheduler_running  = sched.get("running", False),
        next_scheduled_run = sched.get("next_run"),
        last_run_status    = sched.get("status"),
        last_run_at        = sched.get("run_at"),
        seen_url_count     = len(state.get("seen_urls", [])),
        fetcher_exists     = _FETCHER.exists(),
        sources            = source_entries,
        sources_integrated = len(source_entries),
        sources_healthy    = healthy,
        sources_errored    = errored,
    )


@router.post("/run", response_model=MonitorRunResponse,
             dependencies=[Depends(require_admin)])
def run_monitor() -> MonitorRunResponse:
    return _run_fetcher(dry_run=False)


@router.post("/run-dry", response_model=MonitorRunResponse,
             dependencies=[Depends(require_admin)])
def run_monitor_dry() -> MonitorRunResponse:
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
                "BACKEND_URL":   os.getenv("BACKEND_URL", "http://127.0.0.1:8002"),
                "ADMIN_API_KEY": settings.admin_api_key,
            },
        )
        return MonitorRunResponse(
            triggered   = True,
            mode        = "dry-run" if dry_run else "live",
            stdout      = result.stdout[-3000:],
            stderr      = result.stderr[-1000:],
            return_code = result.returncode,
            timestamp   = datetime.now(timezone.utc).isoformat(),
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Timed out after 120s")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
