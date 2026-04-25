"""
FastAPI Server — Smart City Emergency Dispatch System

Exposes API endpoints for:
  - POST /api/call         — Submit a 911 call transcript for triage
  - GET  /api/incidents    — Get all active incidents
  - GET  /api/status       — System health/status
  - GET  /                 — Serve the web dashboard

This module will be fully wired up as tools and engine are completed.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

app = FastAPI(
    title="Smart City Emergency Dispatch — Agent 1",
    description="Intake & Triage Agent for natural disaster 911 call processing",
    version="1.0.0"
)

# ─── Static files (frontend) ────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@app.get("/")
async def serve_dashboard():
    """Serve the main dashboard HTML."""
    return FileResponse(FRONTEND_DIR / "index.html")


# Mount static assets after the root route
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ─── API: System status ─────────────────────────────────────────────────────
@app.get("/api/status")
async def get_status():
    from .tools import read_incident_memory
    incidents = read_incident_memory()
    return {
        "status": "operational",
        "agent": "Agent 1 — Intake & Triage",
        "active_incidents": len(incidents),
        "version": "1.0.0"
    }


# ─── API: Get all incidents ─────────────────────────────────────────────────
@app.get("/api/incidents")
async def get_incidents():
    from .tools import read_incident_memory
    incidents = read_incident_memory()
    # Strip embeddings from response (they're large and internal-only)
    for inc in incidents:
        inc.pop("embedding", None)
    return {"incidents": incidents}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.server:app", host="0.0.0.0", port=8000, reload=True)
