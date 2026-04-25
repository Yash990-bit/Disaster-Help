"""
Agent 2: Dispatch Commander (dispatch_agent.py) — VERIFIED COMPLIANCE
"""

import json
import os
import requests
from pathlib import Path
from datetime import datetime, timezone
from threading import Lock
from groq import Groq
from dotenv import load_dotenv

from smart_city_dispatch.agent2.resource_db import (
    get_available_resources,
    dispatch_unit as _dispatch_unit,
)
from smart_city_dispatch.agent2.city_graph import (
    calculate_travel_time as _calculate_travel_time,
    location_to_node,
)

load_dotenv()
INCIDENTS_FILE = Path(__file__).parent.parent.parent / "data" / "incidents.json"
_file_lock = Lock()
_groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ═══════════════════════════════════════════════════════════════════════════════
# Shared State Utilities
# ═══════════════════════════════════════════════════════════════════════════════

def _read_incidents() -> list[dict]:
    with _file_lock:
        if not INCIDENTS_FILE.exists(): return []
        raw = INCIDENTS_FILE.read_text().strip()
        if not raw: return []
        return json.loads(raw)

def _write_incidents(incidents: list[dict]):
    with _file_lock:
        INCIDENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        INCIDENTS_FILE.write_text(json.dumps(incidents, indent=2, default=str))

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 & 5: Intelligence Stacking & Report Generation
# ═══════════════════════════════════════════════════════════════════════════════

def generate_commander_intelligence(incident: dict) -> dict:
    """Uses Groq to generate stacked insights and department-specific reports."""
    transcripts = " | ".join(incident.get("raw_transcripts", []))
    resources = ", ".join(incident.get("required_resources", []))
    
    prompt = f"""
    You are the Dispatch Commander for Sonipat. Analyze these emergency transcripts.
    TRANSCRIPTS: "{transcripts}"
    RESOURCES REQUESTED: {resources}

    TASK:
    1. Create a "Stacked Insight" (summary of what, where, how bad, and every specific detail).
    2. Generate specific JSON reports for each department: fire_dept, ems, police, hazmat, utilities.
    
    RULES for Reports:
    - FIRE: what_is_burning, explosion_risk, people_trapped
    - EMS: casualties_count, injury_type, breathing_issues
    - POLICE: crowd_size_estimate, evacuation_needed
    - HAZMAT: substance_type, spread_risk
    - UTILITIES: affected_service
    
    RETURN JSON FORMAT ONLY:
    {{
      "stacked_insight": "<summary>",
      "reports": {{
          "fire_dept": {{ "what_is_burning": "...", ... }},
          "ems": {{ ... }},
          ...
      }}
    }}
    """
    try:
        response = _groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except:
        return {"stacked_insight": "Emergency situation", "reports": {}}

# ═══════════════════════════════════════════════════════════════════════════════
# Main Dispatch Commander Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

def run_dispatch_agent():
    print("[AGENT 2] 🚀 DISPATCH COMMANDER CYCLE START")
    
    # --- STEP 1: READ INCIDENTS ---
    all_incidents = _read_incidents()
    active_incidents = [i for i in all_incidents if i.get("status") == "active"]
    
    if not active_incidents:
        print("[AGENT 2] No active incidents to process.")
        return
    
    # --- STEP 3: BUILD PRIORITY LIST ---
    # Sort: Severity DESC, Caller Count DESC, Timestamp ASC
    active_incidents.sort(key=lambda x: (
        -x.get("severity", 0),
        -x.get("caller_count", 0),
        x.get("timestamp", "")
    ))
    
    print("\n=== PRIORITY LIST ===")
    for idx, inc in enumerate(active_incidents):
        print(f"PRIORITY {idx+1}: {inc['incident_id']} — {inc['location']} — SEV {inc['severity']} — {inc['caller_count']} callers")
    
    dispatch_summary = []
    
    # --- PROCESS EACH INCIDENT IN PRIORITY ORDER ---
    for incident in active_incidents:
        inc_id = incident["incident_id"]
        print(f"\n[AGENT 2] Processing Incident: {inc_id}...")
        
        # Claim Incident
        incident["status"] = "dispatched"
        incident["claimed_by"] = "commander_agent"
        
        # --- STEP 2 & 5: GENERATE REPORTS ---
        intel = generate_commander_intelligence(incident)
        incident["stacked_insight"] = intel.get("stacked_insight")
        incident["department_reports"] = intel.get("reports")
        
        # --- STEP 6: DISPATCH UNITS ---
        available_units = get_available_resources()
        dispatch_plan = []
        gaps = []
        
        dest_node = location_to_node(incident["location"])
        
        for res_type in incident["required_resources"]:
            # Find best unit for this resource
            candidates = [u for u in available_units if u["type"] == res_type]
            if not candidates:
                # Handle utilities type mismatch in naming if any
                if res_type.startswith("utilities"):
                    candidates = [u for u in available_units if u["type"] == "utilities"]
            
            if candidates:
                # Pick unit with LOWEST travel time
                best_unit = None
                min_time = 999
                
                for unit in candidates:
                    travel_time = _calculate_travel_time(unit["location_node"], dest_node)
                    if travel_time < min_time:
                        min_time = travel_time
                        best_unit = unit
                
                # Execute Dispatch
                _dispatch_unit(best_unit["unit_id"], inc_id, dest_node)
                dispatch_plan.append({
                    "unit_id": best_unit["unit_id"],
                    "resource_type": res_type,
                    "eta": min_time
                })
                # Remove from available for this cycle
                available_units = [u for u in available_units if u["unit_id"] != best_unit["unit_id"]]
                
                # Update Department Report with travel time
                for dept_key in incident["department_reports"]:
                    # Simple mapping to add travel time to reports
                    incident["department_reports"][dept_key]["assigned_unit"] = best_unit["unit_id"]
                    incident["department_reports"][dept_key]["travel_time_minutes"] = min_time
            else:
                gaps.append(res_type)
        
        # Escalation Rule
        if gaps and incident["severity"] >= 4:
            incident["escalated"] = True
            incident["status"] = "escalated"
        
        incident["dispatch_plan"] = dispatch_plan
        incident["resource_gaps"] = gaps
        
        dispatch_summary.append({
            "id": inc_id,
            "location": incident["location"],
            "severity": incident["severity"],
            "notified": list(incident["department_reports"].keys()),
            "dispatched": [f"{p['unit_id']} ({p['eta']}m)" for p in dispatch_plan],
            "gaps": gaps,
            "escalated": incident.get("escalated", False)
        })

    # --- FINAL WRITE ---
    _write_incidents(all_incidents)
    
    # --- STEP 7: OUTPUT ---
    print("\n=== DISPATCH SUMMARY ===")
    for s in dispatch_summary:
        print(f"ID: {s['id']} | {s['location']} | SEV {s['severity']}")
        print(f"  Notified: {s['notified']}")
        print(f"  Units: {', '.join(s['dispatched']) if s['dispatched'] else 'NONE'}")
        if s['gaps']: print(f"  GAPS: {s['gaps']}")
        print(f"  Escalated: {'YES' if s['escalated'] else 'NO'}")
    
    return dispatch_summary
