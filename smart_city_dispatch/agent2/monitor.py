"""
Monitor — Agent 2 (Dispatcher)

Simulates the lifecycle of an emergency response:
1. Progress units from 'en_route' to 'on_scene'.
2. Transition incidents to 'on_scene' status when all units arrive.
3. Dynamically re-route en-route units if a significantly faster one becomes available.
4. Automatically resolve incidents after 10 minutes on-scene.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from threading import Lock
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from smart_city_dispatch.agent2.resource_db import (
    release_unit, 
    get_all_units, 
    get_available_resources, 
    dispatch_unit,
    UNITS # For updating status to 'on_scene'
)
from smart_city_dispatch.agent2.city_graph import calculate_travel_time

# ═══════════════════════════════════════════════════════════════════════════════
# Setup & Shared Memory
# ═══════════════════════════════════════════════════════════════════════════════

INCIDENTS_FILE = Path(__file__).parent.parent.parent / "data" / "incidents.json"
_file_lock = Lock()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Monitor")

def _read_incidents():
    with _file_lock:
        if not INCIDENTS_FILE.exists(): return []
        return json.loads(INCIDENTS_FILE.read_text())

def _write_incidents(incidents):
    with _file_lock:
        INCIDENTS_FILE.write_text(json.dumps(incidents, indent=2))

# ═══════════════════════════════════════════════════════════════════════════════
# Monitor Logic
# ═══════════════════════════════════════════════════════════════════════════════

def monitor_loop():
    """Main lifecycle simulation loop."""
    logger.info("⏱️ Running monitor cycle...")
    incidents = _read_incidents()
    now = datetime.now(timezone.utc)
    changed = False

    for inc in incidents:
        status = inc.get("status")
        incident_id = inc.get("incident_id")
        destination = inc.get("location_node", "city_mall") # Default fallback

        # ── 1. Handle DISPATCHED Incidents ──
        if status == "dispatched":
            plan = inc.get("dispatch_plan", [])
            units_on_scene = 0
            
            for entry in plan:
                unit_id = entry["unit_id"]
                # Get current unit data
                all_units = {u["unit_id"]: u for u in get_all_units()}
                unit_data = all_units.get(unit_id)
                
                if not unit_data: continue
                
                # A. Progress to On-Scene
                if unit_data["status"] == "en_route":
                    d_time = datetime.fromisoformat(entry["dispatch_time"])
                    elapsed = (now - d_time).total_seconds() / 60
                    
                    # Calculate travel time if not in entry
                    travel_time = entry.get("travel_time_minutes")
                    if travel_time is None:
                        travel_time = calculate_travel_time(unit_data["location_node"], destination)
                    
                    if elapsed >= travel_time:
                        logger.info(f"🚚 Unit {unit_id} has arrived at {incident_id}")
                        unit_data["status"] = "on_scene" # Update in-memory DB
                        entry["status"] = "on_scene"
                        changed = True
                
                if entry.get("status") == "on_scene" or unit_data["status"] == "on_scene":
                    units_on_scene += 1

            # B. Transition Incident to On-Scene
            if len(plan) > 0 and units_on_scene == len(plan):
                logger.info(f"📍 All units on scene for {incident_id}. Status -> on_scene")
                inc["status"] = "on_scene"
                inc["on_scene_time"] = now.isoformat()
                changed = True

            # C. Re-route Check (Optimized pathfinding)
            # (Skipped if all arrived)
            if status == "dispatched" and units_on_scene < len(plan):
                available = get_available_resources()
                for entry in plan:
                    if entry.get("status") == "on_scene": continue
                    
                    old_unit_id = entry["unit_id"]
                    old_unit_type = next((u["type"] for u in get_all_units() if u["unit_id"] == old_unit_id), None)
                    
                    # Calculate current old unit's remaining time
                    d_time = datetime.fromisoformat(entry["dispatch_time"])
                    elapsed = (now - d_time).total_seconds() / 60
                    old_total = calculate_travel_time(entry.get("origin_node", "station_east"), destination)
                    old_remaining = max(0, old_total - elapsed)

                    # Look for better available unit
                    for candidate in available:
                        if candidate["type"] == old_unit_type:
                            new_time = calculate_travel_time(candidate["location_node"], destination)
                            if new_time < (old_remaining - 3):
                                logger.info(f"🔄 RE-ROUTE: Swapping {old_unit_id} for {candidate['unit_id']} (Saves {old_remaining - new_time:.1f}m)")
                                
                                # Perform Swap
                                release_unit(old_unit_id)
                                dispatch_unit(candidate["unit_id"], incident_id, destination)
                                
                                # Update Incident Record
                                if "reroutes" not in inc: inc["reroutes"] = []
                                inc["reroutes"].append({
                                    "old_unit": old_unit_id,
                                    "new_unit": candidate["unit_id"],
                                    "time": now.isoformat()
                                })
                                
                                entry["unit_id"] = candidate["unit_id"]
                                entry["dispatch_time"] = now.isoformat()
                                entry["travel_time_minutes"] = new_time
                                changed = True
                                break

        # ── 2. Handle ON-SCENE Incidents (Resolution) ──
        elif status == "on_scene":
            on_scene_str = inc.get("on_scene_time")
            if on_scene_str:
                on_scene_time = datetime.fromisoformat(on_scene_str)
                if (now - on_scene_time) > timedelta(minutes=10):
                    logger.info(f"✅ Incident {incident_id} RESOLVED. Releasing units.")
                    
                    # Release all units
                    for entry in inc.get("dispatch_plan", []):
                        release_unit(entry["unit_id"])
                    
                    inc["status"] = "resolved"
                    inc["resolved_time"] = now.isoformat()
                    changed = True

    if changed:
        _write_incidents(incidents)

# ═══════════════════════════════════════════════════════════════════════════════
# Scheduler Interface
# ═══════════════════════════════════════════════════════════════════════════════

_scheduler = BackgroundScheduler()

def start_monitor():
    if not _scheduler.running:
        _scheduler.add_job(monitor_loop, 'interval', seconds=30)
        _scheduler.start()
        logger.info("🔍 Monitor Service: STARTED (30s interval)")

def stop_monitor():
    if _scheduler.running:
        _scheduler.shutdown()
        logger.info("🛑 Monitor Service: STOPPED")
