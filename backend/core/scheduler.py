"""
backend/core/scheduler.py
==========================
APScheduler background task that runs the official alert monitor
on a configurable interval (default every 6 hours).

The scheduler is started during FastAPI lifespan startup and
stopped on shutdown. It is disabled in test mode (ENV=test).

Environment variables:
  MONITOR_INTERVAL_HOURS  — polling interval in hours (default: 6)
  MONITOR_ENABLED         — set to "0" to disable (default: enabled)

The scheduler calls fetchers/official_alert_monitor.py as a subprocess
so it doesn't block the async event loop and can be terminated cleanly.
"""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

_ROOT = Path(__file__).resolve().parents[2]
_FETCHER = _ROOT / "fetchers" / "official_alert_monitor.py"

_scheduler: AsyncIOScheduler | None = None

# Last run metadata (in-memory, for /monitor/status)
last_run_result: dict = {}


async def _run_monitor_job() -> None:
    """Async job: spawns the monitor script as a subprocess, then broadcasts results."""
    global last_run_result

    # Import here to avoid circular import at module load time
    from core.ws_manager import ws_manager

    if not _FETCHER.exists():
        last_run_result = {
            "status": "error",
            "message": f"Fetcher not found: {_FETCHER}",
            "run_at": datetime.now(timezone.utc).isoformat(),
        }
        return

    backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8002")
    admin_key   = os.getenv("ADMIN_API_KEY", "disaster-dss-dev-key-change-in-prod")

    try:
        result = subprocess.run(
            [sys.executable, str(_FETCHER)],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(_ROOT),
            env={
                **os.environ,
                "BACKEND_URL": backend_url,
                "ADMIN_API_KEY": admin_key,
            },
        )
        stdout = result.stdout or ""
        # Parse how many new alerts the fetcher posted
        new_count = 0
        for line in stdout.splitlines():
            if "new alert" in line.lower() or "posted" in line.lower():
                # fetcher prints "Posted N new alerts" or similar
                import re
                m = re.search(r'(\d+)', line)
                if m:
                    new_count = int(m.group(1))

        last_run_result = {
            "status":     "ok" if result.returncode == 0 else "error",
            "run_at":     datetime.now(timezone.utc).isoformat(),
            "returncode": result.returncode,
            "new_alerts": new_count,
            "stdout_tail": stdout[-500:] if stdout else "",
            "stderr_tail": result.stderr[-300:] if result.stderr else "",
        }

        # ── Broadcast to all connected WebSocket clients ──────────────────────
        if ws_manager.client_count > 0:
            await ws_manager.broadcast_monitor_done(new_count)

            # If new alerts found, fetch them from DB and push each one
            if new_count > 0:
                await _push_latest_alerts(ws_manager, admin_key, backend_url)

    except subprocess.TimeoutExpired:
        last_run_result = {
            "status":  "timeout",
            "run_at":  datetime.now(timezone.utc).isoformat(),
            "message": "Monitor run timed out after 300s",
        }
    except Exception as e:
        last_run_result = {
            "status":  "exception",
            "run_at":  datetime.now(timezone.utc).isoformat(),
            "message": str(e),
        }


async def _push_latest_alerts(ws_manager, admin_key: str, backend_url: str) -> None:
    """Fetch the latest alerts from our own API and broadcast each one."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{backend_url}/alerts",
                params={"active_only": "true", "limit": "5"},
                headers={"X-Admin-Key": admin_key},
            )
            if resp.status_code == 200:
                data = resp.json()
                for alert in data.get("alerts", []):
                    await ws_manager.broadcast_alert(alert)
    except Exception:
        pass  # silent — WebSocket broadcast is best-effort


def start_scheduler() -> None:
    """Start the background scheduler. Call from FastAPI lifespan."""
    global _scheduler

    env = os.getenv("ENV", "development").lower()
    enabled = os.getenv("MONITOR_ENABLED", "1").strip() != "0"

    if env == "test" or not enabled:
        return  # no scheduler in test mode

    interval_hours = int(os.getenv("MONITOR_INTERVAL_HOURS", "6"))

    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_monitor_job,
        trigger=IntervalTrigger(hours=interval_hours),
        id="alert_monitor",
        name="Official Alert Monitor",
        replace_existing=True,
        max_instances=1,        # never run two monitor jobs simultaneously
        misfire_grace_time=300, # allow up to 5 min late start
    )
    _scheduler.start()


def stop_scheduler() -> None:
    """Stop the background scheduler. Call from FastAPI lifespan shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def get_scheduler_status() -> dict:
    """Return current scheduler state for the /monitor/status endpoint."""
    if _scheduler is None or not _scheduler.running:
        return {"running": False, "next_run": None, **last_run_result}

    job = _scheduler.get_job("alert_monitor")
    next_run = job.next_run_time.isoformat() if job and job.next_run_time else None
    return {"running": True, "next_run": next_run, **last_run_result}
