"""
Agent 1 Tools — Core tool functions for the Intake & Triage Agent.
"""

import os
# SILENCE HF WARNINGS
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"

import json
import random
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

DATA_DIR = Path(__file__).parent.parent / "data"
INCIDENTS_FILE = DATA_DIR / "incidents.json"

# Model name — loaded once at startup
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384 

# Thread locks for safe concurrent access
_model_lock = threading.Lock()
_memory_lock = threading.RLock() # Re-entrant to prevent deadlocks


# ═══════════════════════════════════════════════════════════════════════════════
# Shared State & Singletons
# ═══════════════════════════════════════════════════════════════════════════════

_model = None  # SentenceTransformer
_groq_client = None  # Groq Client


def get_model():
    """Load the sentence-transformer model exactly once and cache it."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(MODEL_NAME)
    return _model


def _ensure_data_dir():
    """Create the data directory and incidents.json if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not INCIDENTS_FILE.exists():
        INCIDENTS_FILE.write_text("[]")


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 1: embed_call
# ═══════════════════════════════════════════════════════════════════════════════

def embed_call(transcript: str) -> list[float]:
    """Convert a raw 911 call transcript into a vector embedding."""
    print("[AGENT 1] Embedding transcript...")
    if not transcript or not transcript.strip():
        return [0.0] * EMBEDDING_DIM

    model = get_model()
    embedding = model.encode(transcript, normalize_embeddings=True)
    return embedding.tolist()


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 2: find_similar_incidents (Precision 0.85)
# ═══════════════════════════════════════════════════════════════════════════════

def find_similar_incidents(
    embedding: list[float],
    threshold: float = 0.85
) -> list[dict]:
    """Search active incident memory for duplicates (Checklist Step 3)."""
    print("[AGENT 1] Checking for duplicates...")
    incidents = read_incident_memory()
    if not incidents:
        return []

    query_vec = np.array(embedding)
    matches = []

    for incident in incidents:
        stored_embedding = incident.get("embedding")
        if not stored_embedding:
            continue

        inc_vec = np.array(stored_embedding)
        similarity = np.dot(query_vec, inc_vec)

        if similarity >= threshold:
            match = dict(incident)
            match["similarity_score"] = round(float(similarity), 4)
            matches.append(match)

    matches.sort(key=lambda x: x["similarity_score"], reverse=True)
    return matches


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 3: read_incident_memory
# ═══════════════════════════════════════════════════════════════════════════════

def read_incident_memory() -> list[dict]:
    """Read all incidents from data/incidents.json."""
    try:
        _ensure_data_dir()
        with _memory_lock:
            if not INCIDENTS_FILE.exists(): return []
            raw = INCIDENTS_FILE.read_text().strip()
            if not raw: return []
            return json.loads(raw)
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 4: write_incident_memory
# ═══════════════════════════════════════════════════════════════════════════════

def write_incident_memory(incident: dict) -> str:
    """Write or update an incident in data/incidents.json."""
    try:
        _ensure_data_dir()
        with _memory_lock:
            incidents = read_incident_memory()
            incident_id = incident.get("incident_id")
            
            existing_idx = next((i for i, inc in enumerate(incidents) if inc.get("incident_id") == incident_id), None)
            if existing_idx is not None:
                incidents[existing_idx] = incident
            else:
                incidents.append(incident)

            fd, tmp_path = tempfile.mkstemp(dir=str(DATA_DIR), suffix=".json.tmp")
            try:
                with os.fdopen(fd, "w") as tmp_file:
                    json.dump(incidents, tmp_file, indent=2, default=str)
                os.replace(tmp_path, str(INCIDENTS_FILE))
            except Exception:
                if os.path.exists(tmp_path): os.unlink(tmp_path)
                raise
        return "written"
    except Exception as e:
        return f"error: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 5 & 6: Utils
# ═══════════════════════════════════════════════════════════════════════════════

def get_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def generate_incident_id() -> str:
    existing_incidents = read_incident_memory()
    existing_ids = {inc.get("incident_id") for inc in existing_incidents}
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    for _ in range(100):
        new_id = f"INC-{date_str}-{random.randint(0, 999):03d}"
        if new_id not in existing_ids: return new_id
    return f"INC-{date_str}-{datetime.now(timezone.utc).strftime('%H%M%S')}"


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 7: analyze_transcript_with_llm (Strict Checklist Step 5)
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_transcript_with_llm(transcript: str) -> dict:
    """Sends the transcript to Groq for structured analysis based on Checklist Rules."""
    global _groq_client
    if _groq_client is None:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not found in .env")
        _groq_client = Groq(api_key=GROQ_API_KEY)

    prompt = f"""
    Analyze this 911 transcript based on STRICT DISPATCH RULES.
    
    TRANSCRIPT: "{transcript}"
    
    LOCATION RULES:
    - Extract street names, landmarks, and Sonipat-specific neighborhoods.
    - If location is vague, set confidence adjustment notes accordingly.

    SEVERITY RULES (1-5):
    1: Minor (spills, noise)
    2: Moderate (small fire, minor injury)
    3: Serious (structure fire, single injury)
    4: Critical (explosion, people trapped)
    5: Catastrophic (collapse, mass casualties)

    RESOURCE MAPPING RULES:
    - fire mentioned -> [fire_truck]
    - injury/medical -> [ambulance]
    - crowd/violence -> [police]
    - gas smell/leak -> [utilities_gas, hazmat]
    - power lines down -> [utilities_power]
    - flooding -> [utilities_water]
    - explosion + fire -> [fire_truck, ambulance, hazmat]
    - building collapse -> [fire_truck, ambulance, hazmat, police]

    REQUIRED JSON FORMAT:
    {{
      "severity": <int 1-5>,
      "location": "<string>",
      "required_resources": ["<resource1>", ...],
      "reasoning": "<justification>",
      "confidence_score": <float 0.0-1.0 (start 1.0, adjust -0.5 if vague)>
    }}
    """

    try:
        response = _groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.1,
            response_format={"type": "json_object"},
            timeout=15.0
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return {"severity": 2, "location": "Unknown", "required_resources": ["police"], "reasoning": "Fallback active.", "confidence_score": 0.5}

# ═══════════════════════════════════════════════════════════════════════════════
# TOOL 8: geocode_location_ors (Real-World API)
# ═══════════════════════════════════════════════════════════════════════════════

def geocode_location_ors(location_text: str) -> list[float]:
    """Converts an address or landmark into [lon, lat] using ORS API."""
    import requests
    ors_key = os.getenv("ORS_API_KEY")
    
    # Fallback coordinates for Sonipat City Center
    SONIPAT_CENTER = [77.0176, 28.9948]

    if not ors_key or not location_text or location_text.lower() == "unknown":
        return SONIPAT_CENTER

    try:
        # Search specifically within Sonipat/Haryana region for better accuracy
        url = f"https://api.openrouteservice.org/geocode/search?api_key={ors_key}&text={location_text}&size=1&boundary.country=IN"
        res = requests.get(url, timeout=5)
        data = res.json()
        
        if data.get("features"):
            coords = data["features"][0]["geometry"]["coordinates"] # [lon, lat]
            print(f"[GEOCODER] Found coordinates for '{location_text}': {coords}")
            return coords
    except Exception as e:
        print(f"[GEOCODER ERROR] {e}")

    return SONIPAT_CENTER


def derive_departments(resources: list) -> list:
    mapping = {
        "ambulance": "EMS",
        "fire_truck": "fire_dept",
        "police": "police_dept",
        "hazmat": "hazmat_team",
        "utilities_gas": "utilities_team",
        "utilities_power": "utilities_team",
        "utilities_water": "utilities_team"
    }
    return sorted(list(set(mapping.get(r, "general_response") for r in resources)))
