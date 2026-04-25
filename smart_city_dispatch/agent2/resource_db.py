"""
Resource Database — Agent 2 (Dispatcher)

In-memory registry of all city emergency response units.
Each unit tracks its type, current location, status, and active assignment.

Statuses: available | en_route | on_scene | returning
"""

from datetime import datetime, timezone
from threading import Lock

# ═══════════════════════════════════════════════════════════════════════════════
# Unit Registry
# ═══════════════════════════════════════════════════════════════════════════════

_lock = Lock()

UNITS: dict[str, dict] = {
    # ── Ambulances ──────────────────────────────────────────────────────────
    "AMB-01": {
        "unit_id": "AMB-01",
        "type": "ambulance",
        "location_node": "hospital_north",
        "status": "available",
        "dispatched_to": None,
        "destination": None,
        "dispatch_time": None,
    },
    "AMB-02": {
        "unit_id": "AMB-02",
        "type": "ambulance",
        "location_node": "station_east",
        "status": "available",
        "dispatched_to": None,
        "destination": None,
        "dispatch_time": None,
    },
    "AMB-03": {
        "unit_id": "AMB-03",
        "type": "ambulance",
        "location_node": "station_west",
        "status": "available",
        "dispatched_to": None,
        "destination": None,
        "dispatch_time": None,
    },

    # ── Fire Trucks ─────────────────────────────────────────────────────────
    "FIRE-01": {
        "unit_id": "FIRE-01",
        "type": "fire_truck",
        "location_node": "fire_hq",
        "status": "available",
        "dispatched_to": None,
        "destination": None,
        "dispatch_time": None,
    },
    "FIRE-02": {
        "unit_id": "FIRE-02",
        "type": "fire_truck",
        "location_node": "station_north",
        "status": "available",
        "dispatched_to": None,
        "destination": None,
        "dispatch_time": None,
    },

    # ── Police ──────────────────────────────────────────────────────────────
    "POL-01": {
        "unit_id": "POL-01",
        "type": "police",
        "location_node": "police_hq",
        "status": "available",
        "dispatched_to": None,
        "destination": None,
        "dispatch_time": None,
    },
    "POL-02": {
        "unit_id": "POL-02",
        "type": "police",
        "location_node": "patrol_east",
        "status": "available",
        "dispatched_to": None,
        "destination": None,
        "dispatch_time": None,
    },

    # ── Hazmat ──────────────────────────────────────────────────────────────
    "HAZ-01": {
        "unit_id": "HAZ-01",
        "type": "hazmat",
        "location_node": "hazmat_depot",
        "status": "available",
        "dispatched_to": None,
        "destination": None,
        "dispatch_time": None,
    },

    # ── Utilities ───────────────────────────────────────────────────────────
    "UTIL-01": {
        "unit_id": "UTIL-01",
        "type": "utilities",
        "location_node": "utility_yard",
        "status": "available",
        "dispatched_to": None,
        "destination": None,
        "dispatch_time": None,
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def get_available_resources() -> list[dict]:
    """Return only units where status='available'."""
    with _lock:
        return [
            dict(u) for u in UNITS.values()
            if u["status"] == "available"
        ]


def dispatch_unit(unit_id: str, incident_id: str, destination_node: str) -> str:
    """
    Mark a unit as dispatched to an incident.

    Sets:
      status       → 'en_route'
      dispatched_to → incident_id
      destination   → destination_node
      dispatch_time → current UTC timestamp

    Returns 'dispatched' on success, or an error string.
    """
    with _lock:
        unit = UNITS.get(unit_id)
        if unit is None:
            return f"error: unit '{unit_id}' not found"
        if unit["status"] != "available":
            return f"error: unit '{unit_id}' is currently {unit['status']}"

        unit["status"] = "en_route"
        unit["dispatched_to"] = incident_id
        unit["destination"] = destination_node
        unit["dispatch_time"] = datetime.now(timezone.utc).isoformat()
        return "dispatched"


def release_unit(unit_id: str) -> str:
    """
    Release a unit back to 'available' status.

    Clears dispatched_to, destination, and dispatch_time.
    Returns 'released' on success, or an error string.
    """
    with _lock:
        unit = UNITS.get(unit_id)
        if unit is None:
            return f"error: unit '{unit_id}' not found"

        unit["status"] = "available"
        unit["dispatched_to"] = None
        unit["destination"] = None
        unit["dispatch_time"] = None
        return "released"


def get_all_units() -> list[dict]:
    """Return ALL units regardless of status."""
    with _lock:
        return [dict(u) for u in UNITS.values()]
