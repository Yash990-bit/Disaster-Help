"""
FastAPI Server — Integrated Smart City System (main.py)
"""
import asyncio
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Smart City Dispatch — Integrated")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

class CallRequest(BaseModel):
    transcript: str

# ═══════════════════════════════════════════════════════════════════════════════
# CORE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    print("\n[SYSTEM] 🚀 Warming up AI Engine...")
    from backend.tools import get_model
    # Load model in a thread so it doesn't block server start
    asyncio.create_task(asyncio.to_thread(get_model))
    print("[SYSTEM] ✅ Engine warming up in background.\n")

@app.get("/")
async def serve_dashboard():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.post("/process-call")
async def process_call_endpoint(request: CallRequest):
    from backend.agent import process_call
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, process_call, request.transcript)
    if "incident" in result:
        result["incident"].pop("embedding", None)
    return result

@app.get("/incidents")
async def get_all_incidents():
    from backend.tools import read_incident_memory
    incidents = read_incident_memory()
    # Remove embeddings from response to keep JSON light
    for inc in incidents:
        inc.pop("embedding", None)
    return {"incidents": incidents}

@app.delete("/incidents/clear")
async def clear_incidents():
    from backend.tools import INCIDENTS_FILE, _memory_lock
    import os
    with _memory_lock:
        if os.path.exists(INCIDENTS_FILE):
            INCIDENTS_FILE.write_text("[]")
    return {"status": "success", "message": "Memory cleared"}

# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 2 INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/trigger-agent2")
async def trigger_agent2_endpoint():
    """Manually trigger the Dispatcher Agent (Agent 2) to process active incidents."""
    try:
        from smart_city_dispatch.agent2.run import trigger_dispatch
        # Run the LangGraph cycle in a background thread
        result = await asyncio.to_thread(trigger_dispatch)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/resources")
async def get_resources_endpoint():
    """Get the current status of all city emergency units."""
    try:
        from smart_city_dispatch.agent2.resource_db import get_all_units
        units = get_all_units()
        return {"units": units}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Static Files
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
