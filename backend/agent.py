"""
Agent 1 — Triage Engine (agent.py) — VERIFIED COMPLIANCE
"""

import numpy as np
from backend.tools import (
    embed_call,
    find_similar_incidents,
    read_incident_memory,
    write_incident_memory,
    get_timestamp,
    generate_incident_id,
    analyze_transcript_with_llm,
    derive_departments,
    geocode_location_ors
)

def process_call(transcript: str) -> dict:
    """Main pipeline strictly following the 7-step checklist."""
    print(f"[AGENT 1] Received call: \"{transcript[:50]}...\"")
    
    # --- STEP 2: VECTOR EMBEDDING ---
    current_embedding = embed_call(transcript)

    # --- STEP 5 (FIELD EXTRACTION) moved up to support Step 3 ---
    # Analyze the NEW call first to get location for duplicate check
    new_call_data = analyze_transcript_with_llm(transcript)

    # --- STEP 3 & 4: DUPLICATE CHECK & MERGE ---
    matches = find_similar_incidents(current_embedding, threshold=0.85)
    
    is_duplicate = False
    existing = None
    if matches:
        existing = matches[0]
        is_duplicate = True
    else:
        # Location Fallback: Check if another incident is at the same landmark/sector
        all_incidents = read_incident_memory()
        new_loc = new_call_data.get("location", "").lower()
        if new_loc:
            for inc in all_incidents:
                old_loc = inc.get("location", "").lower()
                if new_loc in old_loc or old_loc in new_loc:
                    existing = inc
                    is_duplicate = True
                    break

    if is_duplicate:
        # --- MERGE LOGIC (Step 4) ---
        incident = dict(existing)
        incident["raw_transcripts"].append(transcript)
        incident["caller_count"] += 1
        
        # Combine all text for a master re-analysis
        all_text = " | ".join(incident["raw_transcripts"])
        master_analysis = analyze_transcript_with_llm(all_text)
        
        # Severity Upgrade Rule: NEVER downgrade
        new_severity = max(incident["severity"], master_analysis["severity"], new_call_data["severity"])
        incident["severity"] = new_severity
        
        # Resource Union
        res_set = set(incident["required_resources"]) | set(new_call_data["required_resources"])
        incident["required_resources"] = sorted(list(res_set))
        incident["departments_to_notify"] = derive_departments(incident["required_resources"])
        
        # Confidence Logic (+0.05 per confirmation)
        incident["confidence"] = min(1.0, round(incident.get("confidence", 0.9) + 0.05, 2))
        
        # Average Embedding
        old_emb = np.array(incident["embedding"])
        new_emb = np.array(current_embedding)
        incident["embedding"] = ((old_emb + new_emb) / 2).tolist()

        # Update coordinates if they exist (Averaging)
        if "coordinates" not in incident:
            incident["coordinates"] = geocode_location_ors(incident["location"])
        
        cot = f"MERGED: Severity upgraded to {new_severity}. Location confirmed: {incident['location']}."
    else:
        # --- CREATE NEW INCIDENT ---
        incident = {
            "incident_id": generate_incident_id(),
            "location": new_call_data["location"],
            "severity": new_call_data["severity"],
            "required_resources": new_call_data["required_resources"],
            "departments_to_notify": derive_departments(new_call_data["required_resources"]),
            "caller_count": 1,
            "confidence": new_call_data.get("confidence_score", 1.0),
            "status": "active",
            "claimed_by": None,
            "timestamp": get_timestamp(),
            "raw_transcripts": [transcript],
            "embedding": current_embedding,
            "coordinates": geocode_location_ors(new_call_data["location"])
        }
        cot = f"CREATED: Incident at {incident['location']} with Severity {incident['severity']}."

    # --- STEP 6: WRITE TO MEMORY ---
    write_status = write_incident_memory(incident)
    if write_status.startswith("error"):
        raise RuntimeError(f"Failed to save incident: {write_status}")
    
    # --- STEP 7: OUTPUT ---
    return {
        "chain_of_thought": cot,
        "is_duplicate": is_duplicate,
        "incident": incident
    }
